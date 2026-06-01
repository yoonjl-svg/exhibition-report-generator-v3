"""이미지 저장·지속 레이어 (옵션 B: 로컬 캐시 + 보고서 base64 내장).

설계
- 업로드 사진을 프로젝트 내 data/images/<폴더>/ 에 다운스케일·압축해 저장하고,
  세션/레코드에는 **상대 경로 문자열**만 보관한다(JSON 안전).
- 보고서 생성 시점에 경로 → base64 data URI 로 변환해 HTML에 내장하므로,
  생성된 보고서는 사진이 사라져도 그대로 열린다(자체 완결).
- file_id 로 중복 저장을 막아 rerun 마다 다시 쓰지 않는다.
- Streamlit Cloud는 파일시스템이 휘발성 → 같은 세션 안에서는 동작, 재시작 후엔
  경로가 비어 placeholder 로 폴백(요구사항: 보관 불필요, 보고서만 안정 생성).

경로는 BASE_DIR 기준 상대경로로 저장해 리포 이동에도 비교적 견고.
"""

import os
import io
import uuid
import base64

import streamlit as st

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_ROOT = os.path.join(BASE_DIR, "data", "images")

MAX_DIM = 1600      # 최장 변 픽셀 상한 (보고서 용량 안정화)
JPEG_Q = 82


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _safe(s: str) -> str:
    s = "".join(c for c in str(s) if c.isalnum() or c in "-_")
    return s or "x"


def _folder_id() -> str:
    """현재 작업 전시의 이미지 폴더 id. 저장된 전시는 id, 미저장은 세션 uuid."""
    s = st.session_state
    eid = s.get("current_exhibition_id")
    if eid:
        return _safe(eid)
    if not s.get("_image_session_id"):
        s["_image_session_id"] = "sess-" + uuid.uuid4().hex[:10]
    return s["_image_session_id"]


def _dir() -> str:
    d = os.path.join(IMAGES_ROOT, _folder_id())
    os.makedirs(d, exist_ok=True)
    return d


def _resample():
    if hasattr(Image, "Resampling"):
        return Image.Resampling.LANCZOS
    return Image.LANCZOS


def _downscale(data: bytes):
    """바이트 → (다운스케일 JPEG 바이트, 확장자). PIL 없으면 원본 그대로."""
    if not _HAS_PIL:
        return data, "png"
    try:
        im = Image.open(io.BytesIO(data))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        elif im.mode == "L":
            im = im.convert("RGB")
        w, h = im.size
        scale = min(1.0, MAX_DIM / float(max(w, h)))
        if scale < 1.0:
            im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                           _resample())
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=JPEG_Q, optimize=True)
        return out.getvalue(), "jpg"
    except Exception:
        return data, "png"


def _rel(path: str) -> str:
    try:
        return os.path.relpath(path, BASE_DIR).replace("\\", "/")
    except Exception:
        return path


def _abs(rel):
    if not rel:
        return None
    return rel if os.path.isabs(rel) else os.path.join(BASE_DIR, rel)


def _save_bytes(data: bytes, slot: str) -> str:
    small, ext = _downscale(data)
    path = os.path.join(_dir(), f"{_safe(slot)}.{ext}")
    with open(path, "wb") as f:
        f.write(small)
    return _rel(path)


def _sig(uploaded) -> str:
    fid = getattr(uploaded, "file_id", None)
    if fid:
        return str(fid)
    return f"{getattr(uploaded, 'name', '')}:{getattr(uploaded, 'size', '')}"


def _fids() -> dict:
    return st.session_state.setdefault("_img_fids", {})


# ──────────────────────────────────────────────
# 공개 API — 저장(경로 보관)
# ──────────────────────────────────────────────

def persist_single(uploaded, container: dict, key: str, slot: str) -> None:
    """단일 업로더 결과를 저장하고 container[key]=상대경로 설정.

    uploaded 가 None 이면 기존 경로 보존(로드 후 재업로드 불필요).
    file_id 가 직전과 같으면 다시 저장하지 않음.
    """
    if uploaded is None:
        return
    sig = _sig(uploaded)
    fids = _fids()
    if fids.get(slot) == sig and container.get(key):
        return
    container[key] = _save_bytes(uploaded.getvalue(), slot)
    fids[slot] = sig


def persist_multi(uploaded_list, container: dict, key: str, slot: str) -> None:
    """다중 업로더 결과를 저장하고 container[key]=[상대경로...] 설정.

    빈 리스트/None 이면 기존 경로 보존.
    """
    if not uploaded_list:
        return
    sig = ",".join(_sig(u) for u in uploaded_list)
    fids = _fids()
    if fids.get(slot) == sig and container.get(key):
        return
    paths = [_save_bytes(u.getvalue(), f"{slot}_{idx}")
             for idx, u in enumerate(uploaded_list)]
    container[key] = paths
    fids[slot] = sig


# ──────────────────────────────────────────────
# 공개 API — 보고서 내장(base64)
# ──────────────────────────────────────────────

def to_data_uri(rel):
    """상대경로 → base64 data URI. 파일이 없으면 None(→ placeholder)."""
    p = _abs(rel)
    if not p or not os.path.exists(p):
        return None
    try:
        with open(p, "rb") as f:
            data = f.read()
    except Exception:
        return None
    ext = "jpeg" if p.lower().endswith((".jpg", ".jpeg")) else "png"
    return f"data:image/{ext};base64,{base64.b64encode(data).decode('ascii')}"


def uris(rel_list):
    """경로 리스트 → 유효한 data URI 리스트(없는 항목 제외)."""
    out = []
    for r in (rel_list or []):
        u = to_data_uri(r)
        if u:
            out.append(u)
    return out


def count(rel) -> bool:
    """경로(또는 리스트)에 실제 파일이 존재하는지."""
    if isinstance(rel, (list, tuple)):
        return any(count(r) for r in rel)
    p = _abs(rel)
    return bool(p and os.path.exists(p))


def clear_uploader_state() -> None:
    """전시 전환(로드/신규) 시 업로더 위젯값·file_id 추적을 초기화.

    위젯에 직전 전시의 업로드가 남아 다른 전시 폴더로 새는 것을 방지.
    """
    s = st.session_state
    for k in list(s.keys()):
        if (k.startswith(("room_floor_", "room_photos_", "mat_image_"))
                or k in ("poster_file", "program_photos_up", "promo_photos_up")):
            s.pop(k, None)
    s.pop("_img_fids", None)
