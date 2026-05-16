FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
# Ops scripts (repair_mojibake, seed_model_deps, backfill_*, purge_*)
# baked in so they can be invoked as ``python -m scripts.X`` from a
# running container.
COPY scripts /app/scripts

RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python -e .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8003
CMD ["uvicorn", "discovery.main:app", "--host", "0.0.0.0", "--port", "8003"]
