"""JSON logging + OpenTelemetry bootstrap.

Identical helper across api / realtime / discovery / ingestion / scoring —
copied rather than shared because the services don't have a common Python
package yet. Keep them in lockstep when changing anything here.

Logging:
    - Single JSON line per record. Standard fields (ts, level, logger,
      message, service) plus any ``extra={...}`` you pass at the call site.
    - Trace-ID + span-ID fields are auto-injected when an OTEL span is
      active, so log lines correlate with traces in Tempo / Honeycomb /
      whichever backend is consuming them.

OpenTelemetry:
    - Off by default. Activates when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.
    - Auto-instruments FastAPI, SQLAlchemy, asyncpg, redis, httpx — covers
      every external call our services make. No per-call wrapping required.
    - Service name comes from the ``SERVICE_NAME`` arg below; resource
      attributes pick up version + env from env vars.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """Single-line JSON per log record. Stable schema for log shippers."""

    SERVICE: str = "agenttape"

    # The standard logging attributes we pass through; everything else
    # the caller put on the record (via ``extra={}``) ends up in extras.
    _BUILTIN = frozenset(
        {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "message", "module",
            "msecs", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        # Python's formatTime doesn't expand %f — build the timestamp by hand
        # so we get millisecond precision in ISO8601 form.
        from datetime import datetime, timezone

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        payload: dict[str, Any] = {
            "ts": ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "service": self.SERVICE,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        extras = {k: v for k, v in record.__dict__.items() if k not in self._BUILTIN}
        # Trace correlation: opentelemetry stamps trace_id/span_id on
        # records via its LogRecordFactory, where available.
        for k in ("otelTraceID", "otelSpanID", "otelServiceName"):
            v = extras.pop(k, None)
            if v:
                payload[k.replace("otel", "otel_")] = v
        if extras:
            payload["extra"] = extras

        # default=str so UUIDs, datetimes, etc. don't blow up serialization.
        return json.dumps(payload, default=str)


def setup_logging(service: str, level: str = "INFO") -> None:
    JsonFormatter.SERVICE = service
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replace any handlers (uvicorn / pytest may have installed their own).
    root.handlers = [handler]
    root.setLevel(level)
    # Route uvicorn's own loggers through the same JSON pipe — without
    # this, uvicorn keeps its default colorized handler and you get
    # mixed plaintext + JSON output.
    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
    ):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    # Quiet down noisy libs.
    for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def setup_tracing(service: str) -> None:
    """Best-effort OTEL bootstrap — no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return  # OTEL libs not installed in this venv; treat as no-op.

    resource = Resource.create(
        {
            "service.name": service,
            "service.version": os.environ.get("SERVICE_VERSION", "0.0.0"),
            "deployment.environment": os.environ.get("DEPLOY_ENV", "local"),
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    # Auto-instrument: every supported client library that's imported
    # elsewhere will emit spans without us touching call sites.
    _instrument_optional("opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor")
    _instrument_optional("opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor")
    _instrument_optional("opentelemetry.instrumentation.asyncpg", "AsyncPGInstrumentor")
    _instrument_optional("opentelemetry.instrumentation.redis", "RedisInstrumentor")
    _instrument_optional("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor")

    # Inject trace_id / span_id onto every log record.
    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception:  # noqa: BLE001
        pass


def _instrument_optional(module: str, attr: str) -> None:
    try:
        mod = __import__(module, fromlist=[attr])
        getattr(mod, attr)().instrument()
    except Exception:  # noqa: BLE001
        # OTEL deps missing or instrument() already called — both fine.
        pass


def init(service: str, level: str = "INFO") -> None:
    """One-call init — most callers should use this."""
    setup_logging(service, level)
    setup_tracing(service)
