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
# Bake alembic config + migrations into the image so the same image
# can serve uvicorn AND run `alembic upgrade head` as a one-shot
# migrate container in cloud deployments.
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

RUN uv venv /app/.venv && uv pip install --python /app/.venv/bin/python -e .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8001
CMD ["uvicorn", "agenttape_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
