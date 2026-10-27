# syntax=docker/dockerfile:1
FROM node:22.17.1-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.8.22 AS uv
FROM python:3.11.14-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    FRAMEWISE_DATA_DIR=/data FRAMEWISE_PHOTO_ROOTS='["/photos"]' \
    HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 OMP_NUM_THREADS=4 \
    HOME=/data XDG_CACHE_HOME=/data/cache-runtime PATH="/app/backend/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends libimage-exiftool-perl libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 framewise && useradd --uid 1000 --gid framewise --no-create-home framewise \
    && mkdir -p /data /photos && chown framewise:framewise /data
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/tmp/uv-cache uv sync --frozen --no-dev --no-install-project --extra ai --extra raw
COPY backend/framewise ./framewise
RUN --mount=type=cache,target=/tmp/uv-cache uv sync --frozen --no-dev --extra ai --extra raw
COPY scripts/install_models.py /app/scripts/install_models.py
COPY --from=frontend /build/dist /app/frontend/dist
USER framewise
EXPOSE 8765
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=4)"
CMD ["python", "-m", "uvicorn", "framewise.api.app:app", "--host", "0.0.0.0", "--port", "8765"]
