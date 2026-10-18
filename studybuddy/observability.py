"""ARC-08: request IDs, structured access logs.

- Every request gets a UUID request_id (or reuses the incoming X-Request-ID).
- The id is returned in the X-Request-ID response header and attached to
  error payloads so users can quote it in bug reports.
- One JSON-ish access log line per request: method, route, status, latency,
  user hash. NEVER payloads (PII) — see _safe_user_ref().
- In production (FLASK_ENV=production or RENDER set) the root logger emits
  JSON lines; in dev it stays human-readable.
"""
import hashlib
import json
import logging
import time
import uuid

from flask import g, request

log = logging.getLogger("studybuddy.access")


def _safe_user_ref():
    """Hashed user id for logs — never the raw id/email."""
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            raw = str(current_user.get_id()).encode()
            return hashlib.sha256(raw).hexdigest()[:12]
    except Exception:
        pass
    return "anon"


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app):
    """JSON logs in production, readable logs in dev."""
    prod = (app.config.get("ENV") == "production"
            or __import__("os").environ.get("RENDER"))
    handler = logging.StreamHandler()
    if prod:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO if prod else logging.DEBUG)
    # noisy libs stay quiet
    for noisy in ("werkzeug", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def register_request_tracking(app):
    @app.before_request
    def _assign_request_id():
        g.request_id = (request.headers.get("X-Request-ID")
                        or uuid.uuid4().hex[:16])
        g._t0 = time.perf_counter()

    @app.after_request
    def _log_request(resp):
        resp.headers["X-Request-ID"] = g.get("request_id", "-")
        try:
            latency_ms = int((time.perf_counter() - g.get("_t0", 0)) * 1000)
        except Exception:
            latency_ms = -1
        # Never log query args / form / JSON bodies (PII).
        log.info("%s %s -> %s (%dms) user=%s",
                 request.method, request.path, resp.status_code,
                 latency_ms, _safe_user_ref(),
                 extra={"request_id": g.get("request_id", "-")})
        return resp
