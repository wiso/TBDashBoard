# syntax=docker/dockerfile:1
# ── TB2026 Monitoring Offline ──
# Multi-stage build using uv for fast Python dependency management.

# ---------- Stage 1: build ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# Copy source and install the project itself
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the virtual environment and config from the builder
COPY --from=builder /app/.venv /app/.venv
COPY config.toml .

# Place venv on PATH so `tb-monitor` is directly available
ENV PATH="/app/.venv/bin:$PATH"

# Default data directory (mount your ROOT files here)
VOLUME /data

EXPOSE 8050

ENTRYPOINT ["tb-monitor"]
CMD ["--config", "/app/config.toml", "--data-dir", "/data", "--host", "0.0.0.0"]
