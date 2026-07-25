FROM python:3.14.6-slim-bookworm@sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace

RUN python -m pip install --no-cache-dir uv==0.11.32

COPY pyproject.toml uv.lock ./
COPY apps/control-api/pyproject.toml apps/control-api/pyproject.toml
COPY libs/python/agent_kernel/pyproject.toml libs/python/agent_kernel/pyproject.toml
COPY libs/python/platform_store/pyproject.toml libs/python/platform_store/pyproject.toml
COPY workers/runtime/pyproject.toml workers/runtime/pyproject.toml
COPY apps/control-api apps/control-api
COPY libs/python libs/python
COPY workers/runtime workers/runtime
COPY infra/migrations infra/migrations

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --all-packages

ENV PATH="/workspace/.venv/bin:${PATH}"

CMD ["uvicorn", "universal_agent_studio_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
