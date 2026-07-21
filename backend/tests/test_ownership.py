"""
Session-isolation / ownership tests.

Verifies that users can only see and mutate their own tasks,
while admins can access all tasks.
"""

import pytest


def _create_task_for_user(client, headers: dict) -> str:
    """Helper: create a task and return its task_id."""
    resp = client.post(
        "/api/deepresearch/create",
        headers=headers,
        json={
            "task": "Investigate dark energy implications",
            "data_description": "Some cosmological data",
        },
    )
    assert resp.status_code == 200, f"Task creation failed: {resp.text}"
    return resp.json()["task_id"]


# ──────────────────────────────────────────────────────────────────────────────
# Task creation
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskCreation:
    def test_authenticated_user_can_create_task(self, client, user_headers):
        task_id = _create_task_for_user(client, user_headers)
        assert task_id

    def test_unauthenticated_request_returns_401(self, client):
        resp = client.post(
            "/api/deepresearch/create",
            json={"task": "test", "data_description": ""},
        )
        assert resp.status_code == 401

    def test_task_session_has_user_id(self, client, user_headers, normal_user):
        task_id = _create_task_for_user(client, user_headers)

        # WorkflowRun/Session are stored in cmbagent's own DB (not the test DB)
        from cmbagent.database.base import get_db_session
        from cmbagent.database.models import WorkflowRun, Session as DBSession
        cdb = get_db_session()
        try:
            run = cdb.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            assert run is not None
            session = cdb.query(DBSession).filter(DBSession.id == run.session_id).first()
            assert session.user_id == normal_user.id
        finally:
            cdb.close()


# ──────────────────────────────────────────────────────────────────────────────
# Task listing (user sees only their own)
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskListing:
    def test_user_sees_only_own_tasks(self, client, user_headers, user_b_headers):
        task_a = _create_task_for_user(client, user_headers)

        # User B should NOT see User A's task
        resp = client.get(
            "/api/deepresearch/recent?include_all=true",
            headers=user_b_headers,
        )
        assert resp.status_code == 200
        task_ids = [t["task_id"] for t in resp.json()]
        assert task_a not in task_ids

    def test_admin_sees_all_tasks(self, client, user_headers, user_b_headers, admin_headers):
        task_a = _create_task_for_user(client, user_headers)
        task_b = _create_task_for_user(client, user_b_headers)

        resp = client.get(
            "/api/deepresearch/recent?include_all=true",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        task_ids = [t["task_id"] for t in resp.json()]
        assert task_a in task_ids
        assert task_b in task_ids

    def test_unauthenticated_list_returns_401(self, client):
        resp = client.get("/api/deepresearch/recent?include_all=true")
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Task read (GET /{task_id})
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskRead:
    def test_owner_can_read_task(self, client, user_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.get(f"/api/deepresearch/{task_id}", headers=user_headers)
        assert resp.status_code == 200

    def test_other_user_cannot_read_task(self, client, user_headers, user_b_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.get(f"/api/deepresearch/{task_id}", headers=user_b_headers)
        assert resp.status_code == 403

    def test_admin_can_read_any_task(self, client, user_headers, admin_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.get(f"/api/deepresearch/{task_id}", headers=admin_headers)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Task mutation (stop, delete)
# ──────────────────────────────────────────────────────────────────────────────

class TestTaskMutation:
    def test_other_user_cannot_stop_task(self, client, user_headers, user_b_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.post(f"/api/deepresearch/{task_id}/stop", headers=user_b_headers)
        assert resp.status_code == 403

    def test_owner_can_stop_task(self, client, user_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.post(f"/api/deepresearch/{task_id}/stop", headers=user_headers)
        assert resp.status_code == 200

    def test_other_user_cannot_delete_task(self, client, user_headers, user_b_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.delete(f"/api/deepresearch/{task_id}", headers=user_b_headers)
        assert resp.status_code == 403

    def test_owner_can_delete_task(self, client, user_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.delete(f"/api/deepresearch/{task_id}", headers=user_headers)
        assert resp.status_code == 200

    def test_admin_can_delete_any_task(self, client, user_headers, admin_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.delete(f"/api/deepresearch/{task_id}", headers=admin_headers)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────────────
# Stage execution ownership
# ──────────────────────────────────────────────────────────────────────────────

class TestStageOwnership:
    def test_other_user_cannot_execute_stage(self, client, user_headers, user_b_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.post(
            f"/api/deepresearch/{task_id}/stages/1/execute",
            headers=user_b_headers,
        )
        assert resp.status_code == 403

    def test_unauthenticated_execute_returns_401(self, client, user_headers):
        task_id = _create_task_for_user(client, user_headers)
        resp = client.post(f"/api/deepresearch/{task_id}/stages/1/execute")
        assert resp.status_code == 401
