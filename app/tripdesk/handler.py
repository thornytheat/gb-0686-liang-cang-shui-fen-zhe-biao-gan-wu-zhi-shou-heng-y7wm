import json
from flask import Blueprint, request, jsonify, render_template, Response
from app.config import COLUMNS, MODULES, DEFAULTS, SAMPLES, MAX_BYTES
from app.errors import DomainError
from app.normalize import serial
from . import service
bp = Blueprint("tripdesk", __name__)
@bp.get("/trips")
def page():
    snap = service.snapshot()
    samples = {name: (SAMPLES / f"weigh_{name}.csv").read_text(encoding="utf-8-sig") for name in ("day1", "day2")}
    defaults = snap["params"] or {**DEFAULTS, "default_tare_kg": ""}
    return render_template("trips.html", snap=snap, samples=samples, columns=COLUMNS,
                           modules=MODULES, defaults=defaults)
@bp.get("/api/trips")
def api_snapshot():
    return jsonify(serial(service.snapshot()))
@bp.post("/api/trips/uploads")
def api_upload():
    if request.files:
        file = request.files.get("file")
        if file is None: raise DomainError("FILE", "请选择文件")
        raw = file.read(MAX_BYTES + 1)
        try: params = json.loads(request.form.get("params", "{}"))
        except ValueError: raise DomainError("PARAMS", "参数格式错误")
    else:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict): raise DomainError("BODY", "请求必须是对象")
        raw = payload.get("text")
        if raw is not None and not isinstance(raw, str): raise DomainError("TEXT", "数据必须为文本")
        params = payload.get("params")
    if raw is None: raise DomainError("FILE", "请选择文件")
    return jsonify(serial(service.upload(raw, params)))
@bp.get("/api/trips/export.csv")
def api_export():
    return Response("\ufeff" + service.export_csv(), content_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=tickets.csv"})
