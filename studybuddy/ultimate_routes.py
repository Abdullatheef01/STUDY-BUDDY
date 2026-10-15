"""Ultimate Lab API dispatcher: serves all 91 ultimate tools via JSON.

Endpoints (registered by register_ultimate_routes):
  GET  /api/ultimate/tools          -> metadata for every tool (id, feature, name, description, fields)
  POST /api/ultimate/run/<tool_id>  -> run a tool; JSON body = {field: value}; returns {ok, result} or {ok:false, error}
  GET  /ultimate/lab               -> the interactive dashboard page
"""
import importlib
import json
from datetime import date, datetime

from flask import jsonify, request, render_template

from studybuddy.ultimate_reg_a import TOOLS_A
from studybuddy.ultimate_reg_b import TOOLS_B
from studybuddy.ultimate_reg_c import TOOLS_C

ALL_TOOLS = TOOLS_A + TOOLS_B + TOOLS_C
_TOOL_INDEX = {t["id"]: t for t in ALL_TOOLS}

# Fields that arrive as YYYY-MM-DD strings but must be date objects.
_DATE_FIELDS = {"last_active", "date", "start_date", "end_date"}


def _jsonable(obj):
    """Recursively convert to JSON-safe types."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _coerce_value(field, raw):
    """Apply field-type coercion: JSON parse, number cast, checkbox bool, dates."""
    ftype = field.get("type")
    name = field["name"]
    if raw is None or raw == "":
        return None
    if field.get("json"):
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{name}' must be valid JSON.")
    if ftype == "number":
        try:
            return int(raw) if "." not in str(raw) else float(raw)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{name}' must be a number.")
    if ftype == "checkbox":
        return raw in (True, "true", "on", "1", 1)
    if name in _DATE_FIELDS and isinstance(raw, str):
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            raise ValueError(f"Field '{name}' must be YYYY-MM-DD.")
    # "one per line" textareas -> list of strings
    if ftype == "textarea" and "one per line" in field.get("label", "").lower():
        if isinstance(raw, str):
            return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    # comma-separated
    if ftype == "text" and "comma" in field.get("label", "").lower():
        if isinstance(raw, str):
            return [p.strip() for p in raw.split(",") if p.strip()]
    return raw


def _load_fn(tool):
    mod = importlib.import_module(tool["module"])
    fn = getattr(mod, tool["function"])
    return fn


def run_tool(tool_id, payload):
    """Execute one registered tool. Returns (result_dict, error_str)."""
    tool = _TOOL_INDEX.get(tool_id)
    if not tool:
        return None, f"Unknown tool '{tool_id}'."
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."
    kwargs = {}
    try:
        for field in tool.get("fields", []):
            name = field["name"]
            raw = payload.get(name)
            if raw is None or raw == "":
                if field.get("required"):
                    return None, f"Field '{field.get('label', name)}' is required."
                continue
            kwargs[name] = _coerce_value(field, raw)
    except ValueError as e:
        return None, str(e)
    try:
        fn = _load_fn(tool)
        result = fn(**kwargs)
    except (ValueError, TypeError) as e:
        return None, str(e) or "Invalid input."
    except Exception as e:  # never leak tracebacks
        return None, f"Tool failed: {type(e).__name__}."
    return _jsonable(result), None


def public_tools():
    """Metadata for the frontend (no function refs)."""
    out = []
    for t in ALL_TOOLS:
        out.append({k: t[k] for k in ("id", "feature", "name", "description", "fields")})
    return out


def register_ultimate_routes(app):
    @app.route("/api/ultimate/tools", methods=["GET"])
    def _ultimate_tools():
        return jsonify({"ok": True, "count": len(ALL_TOOLS), "tools": public_tools()})

    @app.route("/api/ultimate/run/<path:tool_id>", methods=["POST"])
    def _ultimate_run(tool_id):
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"ok": False, "error": "Send a JSON body."}), 400
        result, error = run_tool(tool_id, payload)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True, "result": result})

    @app.route("/ultimate/lab", methods=["GET"])
    def _ultimate_lab():
        return render_template("ultimate_lab.html")
