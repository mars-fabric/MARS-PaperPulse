"""
Auth endpoint tests.

Covers: signup, login, token refresh, logout, me, change-password,
password policy enforcement, and account lockout.
"""

import pytest


# ──────────────────────────────────────────────────────────────────────────────
# Signup
# ──────────────────────────────────────────────────────────────────────────────

class TestSignup:
    def test_signup_creates_pending_user(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "new@example.com",
            "password": "Valid@1234!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        assert "waiting for admin approval" in resp.json()["message"].lower()

    def test_signup_weak_password_rejected(self, client):
        resp = client.post("/api/auth/signup", json={
            "email": "weak@example.com",
            "password": "password",  # no uppercase, digit, special
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_signup_duplicate_email_rejected(self, client, normal_user):
        resp = client.post("/api/auth/signup", json={
            "email": "user@example.com",  # already exists
            "password": "Valid@1234!",
        })
        assert resp.status_code == 400

    @pytest.mark.parametrize("password,reason", [
        ("Sh0rt!", "too short"),
        ("alllowercase1!", "no uppercase"),
        ("ALLUPPERCASE1!", "no lowercase"),
        ("NoDigits!", "no digit"),
        ("NoSpecial1A", "no special char"),
    ])
    def test_password_policy(self, client, password, reason):
        resp = client.post("/api/auth/signup", json={
            "email": f"test_{reason.replace(' ', '')}@example.com",
            "password": password,
        })
        assert resp.status_code == 422, f"Expected rejection for: {reason}"


# ──────────────────────────────────────────────────────────────────────────────
# Login
# ──────────────────────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_approved_user_returns_tokens(self, client, normal_user):
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "User@1234!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_pending_user_returns_403(self, client, pending_user):
        resp = client.post("/api/auth/login", json={
            "email": "pending@example.com",
            "password": "User@1234!",
        })
        assert resp.status_code == 403
        assert "pending" in resp.json()["detail"].lower()

    def test_login_wrong_password_returns_401(self, client, normal_user):
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "WrongPass@1!",
        })
        assert resp.status_code == 401

    def test_login_unknown_email_returns_401(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "Valid@1234!",
        })
        assert resp.status_code == 401

    def test_account_lockout_after_5_failures(self, client, normal_user):
        for _ in range(5):
            client.post("/api/auth/login", json={
                "email": "user@example.com",
                "password": "Wrong@123!",
            })
        # 6th attempt — account should be locked
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "User@1234!",  # correct password
        })
        assert resp.status_code == 429


# ──────────────────────────────────────────────────────────────────────────────
# Token refresh & logout
# ──────────────────────────────────────────────────────────────────────────────

class TestRefreshAndLogout:
    def test_refresh_returns_new_access_token(self, client, normal_user):
        login = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        }).json()
        resp = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_with_invalid_token_returns_401(self, client):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "invalid-token"})
        assert resp.status_code == 401

    def test_logout_revokes_refresh_token(self, client, normal_user):
        login = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        }).json()
        # Logout
        client.post("/api/auth/logout", json={"refresh_token": login["refresh_token"]})
        # Refresh should now fail
        resp = client.post("/api/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# /me and change-password
# ──────────────────────────────────────────────────────────────────────────────

class TestMe:
    def test_me_returns_user_profile(self, client, user_headers, normal_user):
        resp = client.get("/api/auth/me", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert data["role"] == "user"

    def test_me_without_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_change_password(self, client, normal_user):
        # Login to get token
        token = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        }).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/auth/change-password", headers=headers, json={
            "current_password": "User@1234!",
            "new_password": "NewPass@9!",
        })
        assert resp.status_code == 200

        # Old password no longer works
        resp2 = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        })
        assert resp2.status_code == 401

    def test_change_password_wrong_current_returns_400(self, client, user_headers):
        resp = client.post("/api/auth/change-password", headers=user_headers, json={
            "current_password": "Wrong@1234!",
            "new_password": "NewPass@9!",
        })
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# Admin approval
# ──────────────────────────────────────────────────────────────────────────────

class TestAdminApproval:
    def test_admin_can_approve_pending_user(self, client, admin_headers, pending_user, db):
        resp = client.post(
            f"/api/admin/users/{pending_user.id}/approve",
            headers=admin_headers,
            json={"reason": "Looks good"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["status"] == "approved"

        # Approved user can now log in
        login = client.post("/api/auth/login", json={
            "email": "pending@example.com",
            "password": "User@1234!",
        })
        assert login.status_code == 200

    def test_non_admin_cannot_approve(self, client, user_headers, pending_user):
        resp = client.post(
            f"/api/admin/users/{pending_user.id}/approve",
            headers=user_headers,
        )
        assert resp.status_code == 403

    def test_admin_can_suspend_user(self, client, admin_headers, normal_user):
        resp = client.post(
            f"/api/admin/users/{normal_user.id}/suspend",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["status"] == "suspended"

    def test_suspended_user_cannot_login(self, client, admin_headers, normal_user):
        client.post(f"/api/admin/users/{normal_user.id}/suspend", headers=admin_headers)
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        })
        assert resp.status_code == 403

    def test_admin_reinstate_allows_login(self, client, admin_headers, normal_user):
        client.post(f"/api/admin/users/{normal_user.id}/suspend", headers=admin_headers)
        client.post(f"/api/admin/users/{normal_user.id}/reinstate", headers=admin_headers)
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com", "password": "User@1234!"
        })
        assert resp.status_code == 200

    def test_admin_lists_pending_users(self, client, admin_headers, pending_user):
        resp = client.get("/api/admin/users?status=pending", headers=admin_headers)
        assert resp.status_code == 200
        emails = [u["email"] for u in resp.json()]
        assert "pending@example.com" in emails

    def test_admin_audit_logs_not_empty_after_actions(self, client, admin_headers, pending_user, db):
        client.post(f"/api/admin/users/{pending_user.id}/approve", headers=admin_headers)
        resp = client.get("/api/admin/audit-logs", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) > 0
