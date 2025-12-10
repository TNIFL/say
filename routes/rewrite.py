# routes/rewrite.py
from flask import Blueprint, request, jsonify
from guards import require_feature, enforce_quota

bp = Blueprint("rewrite", __name__, url_prefix="/api")

@bp.post("/rewrite/single")
@require_feature("rewrite.single")
@enforce_quota("rewrite")
def rewrite_single():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty_text"}), 400
    # === 실제 리라이트 로직 자리 ===
    output = f"[single] refined: {text}"
    return jsonify({"ok": True, "output": output})

@bp.post("/rewrite/multi")
@require_feature("rewrite.multi")
@enforce_quota("rewrite")
def rewrite_multi():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"error": "empty_items"}), 400
    outputs = [f"[multi] refined: {str(x).strip()}" for x in items[:10]]  # 데모
    return jsonify({"ok": True, "outputs": outputs})

@bp.post("/preview/compare3")
@require_feature("preview.compare3")
@enforce_quota("preview")
def preview_compare3():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty_text"}), 400
    candidates = [
        f"[c1] {text} (정중)",
        f"[c2] {text} (캐주얼)",
        f"[c3] {text} (비즈니스)"
    ]
    return jsonify({"ok": True, "candidates": candidates})
