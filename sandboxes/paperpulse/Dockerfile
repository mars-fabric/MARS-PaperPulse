# syntax=docker/dockerfile:1.4

# SPDX-FileCopyrightText: Copyright (c) 2025-2026 MARS Research. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

# PaperPulse sandbox image for OpenShell
#
# One image running the whole app end-to-end, just like the gemini sandbox:
#   - FastAPI backend  (the deep-research agent)   -> :8000
#   - Next.js frontend (standalone server bundle)  -> :3000
#
# Build (from the repo root — context needs backend/ AND frontend/):
#   docker build -t openshell-paperpulse -f sandboxes/paperpulse/Dockerfile .
# Run:
#   openshell sandbox create --from paperpulse
#   # then, inside the sandbox shell:
#   start-paperpulse

ARG BASE_IMAGE=ghcr.io/nvidia/openshell-community/sandboxes/base:latest
FROM ${BASE_IMAGE}

USER root

# Browser-facing URLs are inlined into the JS bundle at BUILD time (NEXT_PUBLIC_*
# are compile-time). Override with --build-arg if the sandbox is reached via a
# host other than localhost.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Minimal build deps for compiling scientific wheels (numpy/scipy/statsmodels).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gfortran \
    && rm -rf /var/lib/apt/lists/*

# ── Backend: venv on Python 3.12 + deps ──────────────────────────────────────
COPY backend/requirements.txt /app/backend/requirements.txt
RUN uv venv --clear --python 3.12 /sandbox/.venv \
    && uv pip install --python /sandbox/.venv/bin/python --upgrade pip \
    && uv pip install --python /sandbox/.venv/bin/python -r /app/backend/requirements.txt

# ── Frontend: build the self-contained standalone server ─────────────────────
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd /app/frontend && npm ci
COPY frontend/ /app/frontend/
RUN cd /app/frontend \
    && NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
       NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL} \
       npm run build \
    && cp -r .next/static .next/standalone/.next/static \
    && if [ -d public ]; then cp -r public .next/standalone/public; fi \
    && mkdir -p /sandbox/next-cache \
    && rm -rf .next/standalone/.next/cache \
    && ln -s /sandbox/next-cache .next/standalone/.next/cache \
    && rm -rf /app/frontend/node_modules

# ── Backend code + launcher + policy ─────────────────────────────────────────
COPY backend/ /app/backend/
COPY sandboxes/paperpulse/start-paperpulse.sh /usr/local/bin/start-paperpulse
RUN chmod +x /usr/local/bin/start-paperpulse
COPY sandboxes/paperpulse/policy.yaml /etc/openshell/policy.yaml

# ── Writable runtime state (under /sandbox, per the policy) ──────────────────
ENV CMBAGENT_DEFAULT_WORK_DIR=/sandbox/cmbdir \
    PORT=8000 \
    PATH=/sandbox/.venv/bin:$PATH
RUN mkdir -p /sandbox/cmbdir \
    && chown -R sandbox:sandbox /sandbox/cmbdir /sandbox/next-cache /sandbox/.venv

USER sandbox

EXPOSE 8000 3000

# OpenShell convention: land in a shell; run `start-paperpulse` to launch both.
ENTRYPOINT ["/bin/bash"]
