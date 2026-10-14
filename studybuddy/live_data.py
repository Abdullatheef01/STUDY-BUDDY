"""Live Data Engine — shared freshness infrastructure for STUDY-BUDDY.

Every dataset that claims to reflect "the current world" gets:
- meta.last_updated (ISO date) tracked in its JSON bank
- is_stale(): True when older than the dataset's STALE_AFTER_DAYS
- atomic_write(): temp file + os.replace, never leaves partial data
- refresh lock: file-based, prevents overlapping refreshes
- background_refresh(): daemon thread, never raises, never blocks requests

Datasets that are genuinely live (opportunities, trending research) refresh
from external sources. Curated banks (salary, certs) expose the same
freshness API so pages can show honest "last updated" badges and warn
when data is stale — with static fallback always available.
"""

import json
import logging
import os
import tempfile
import threading
from datetime import date

log = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")


def data_path(filename):
    return os.path.join(DATA_DIR, filename)


def lock_path(filename):
    return os.path.join(DATA_DIR, f".{filename}.refresh.lock")


def is_stale(last_updated, stale_after_days):
    """True if last_updated (ISO YYYY-MM-DD) is older than stale_after_days."""
    try:
        y, m, d = (int(p) for p in str(last_updated or "").split("-"))
        updated = date(y, m, d)
    except (ValueError, TypeError):
        return True
    return (date.today() - updated).days >= stale_after_days


def atomic_write(path, data):
    """Write JSON atomically: temp file in same dir + os.replace."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def acquire_lock(path):
    """File-based refresh lock. Returns True if we got it."""
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def release_lock(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def touch_updated(meta):
    """Return a copy of meta with last_updated = today."""
    meta = dict(meta or {})
    meta["last_updated"] = date.today().isoformat()
    return meta


def freshness_badge(meta, stale_after_days):
    """Template helper: {label, stale, last_updated} for freshness pills."""
    last = (meta or {}).get("last_updated", "")
    stale = is_stale(last, stale_after_days)
    if stale:
        label = f"Updated {last or 'never'} — may be stale" if last else "Update date unknown"
    else:
        label = f"Updated {last}"
    return {"label": label, "stale": stale, "last_updated": last}


def background_refresh(name, refresh_fn):
    """Run refresh_fn in a daemon thread. Never raises, never blocks."""
    def _run():
        try:
            refresh_fn()
        except Exception as exc:
            log.warning("Live refresh '%s' failed: %s", name, exc)
    t = threading.Thread(target=_run, name=f"live-refresh-{name}", daemon=True)
    t.start()
    return t


def maybe_refresh(name, filename, stale_after_days, refresh_fn, cache_clear=None):
    """Kick off a background refresh if the dataset is stale.

    Call from load paths. Returns True if a refresh was started.
    Disabled entirely when LIVE_REFRESH_DISABLED=1 (tests/operators).
    """
    if os.environ.get("LIVE_REFRESH_DISABLED") == "1":
        return False
    path = data_path(filename)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        meta = raw.get("meta", {}) if isinstance(raw, dict) else {}
    except Exception:
        meta = {}
    if not is_stale(meta.get("last_updated"), stale_after_days):
        return False
    lp = lock_path(filename)
    if not acquire_lock(lp):
        return False  # another refresh already running
    def _wrapped():
        try:
            ok = refresh_fn()
            if ok and cache_clear:
                cache_clear()
        finally:
            release_lock(lp)
    background_refresh(name, _wrapped)
    return True
