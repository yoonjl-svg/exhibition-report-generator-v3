"""
Exhibition Workspace KB Store — 전시 레코드 영구 저장소 어댑터.

두 가지 모드를 자동 전환:
- local: 로컬 v5 클론 디렉터리에서 직접 읽기·쓰기 (개발용)
- github: GitHub API로 읽기·쓰기 (Streamlit Cloud 배포용)

설정:
  Streamlit secrets 또는 환경 변수:
    KB_MODE:          "local" | "github"  (미설정 시 PAT 유무로 auto)
    KB_LOCAL_PATH:    로컬 v5 디렉터리   (기본 "../exhibition-report-generator-v5")
    KB_GITHUB_REPO:   "yoonjl-svg/exhibition-report-generator-v5"
    KB_GITHUB_PAT:    GitHub Personal Access Token (github 모드 필수)
    KB_GITHUB_BRANCH: 대상 브랜치 (기본 "main")

기본 동작:
  - PAT가 설정되어 있으면 github 모드, 아니면 local 모드.
  - 따라서 로컬 dev에서는 PAT 없이 ../exhibition-report-generator-v5/data/...를 사용,
    Streamlit Cloud에서는 secrets로 PAT 설정 시 자동 github 모드.

레코드 형식: schema.py 참조.
"""

import os
import json
import base64
import time
from typing import Optional

import requests


DATA_SUBPATH = "data/exhibitions"


# ──────────────────────────────────────────────
# 설정 로드 — Streamlit secrets > 환경 변수 > 기본값
# ──────────────────────────────────────────────

def _config(key: str, default: str = "") -> str:
    """secrets에서 우선 조회, 없으면 env var, 없으면 default."""
    # Streamlit secrets는 import 시점에 항상 가능하지 않으므로 lazy
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


def get_mode() -> str:
    """현재 모드 결정. 'local' | 'github'."""
    explicit = _config("KB_MODE", "").strip().lower()
    if explicit in ("local", "github"):
        return explicit
    # auto: PAT가 있으면 github, 아니면 local
    if _config("KB_GITHUB_PAT", "").strip():
        return "github"
    return "local"


def _local_dir() -> str:
    base = _config("KB_LOCAL_PATH", os.path.join("..", "exhibition-report-generator-v5"))
    return os.path.join(base, DATA_SUBPATH)


def _github_repo() -> str:
    return _config("KB_GITHUB_REPO", "yoonjl-svg/exhibition-report-generator-v5")


def _github_branch() -> str:
    return _config("KB_GITHUB_BRANCH", "main")


def _github_pat() -> str:
    pat = _config("KB_GITHUB_PAT", "").strip()
    if not pat:
        raise RuntimeError(
            "KB_GITHUB_PAT가 설정되지 않았습니다. "
            "Streamlit secrets 또는 환경 변수에 GitHub Personal Access Token을 추가하세요."
        )
    return pat


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {_github_pat()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_url(filename: str = "") -> str:
    repo = _github_repo()
    base = f"https://api.github.com/repos/{repo}/contents/{DATA_SUBPATH}"
    if filename:
        # GitHub API는 경로 segment 안의 한글도 URL-encode 필요 없이 받아줌
        return f"{base}/{filename}"
    return base


# ──────────────────────────────────────────────
# 캐시 (단일 프로세스 메모리, 30초 TTL)
# ──────────────────────────────────────────────

_CACHE: dict = {"list": (0, None), "items": {}}
_CACHE_TTL = 30  # seconds


def _cache_clear():
    _CACHE["list"] = (0, None)
    _CACHE["items"] = {}


# ──────────────────────────────────────────────
# 공용 API
# ──────────────────────────────────────────────

def list_exhibitions(use_cache: bool = True) -> list[dict]:
    """모든 전시 레코드 반환 (메타데이터 + data 포함, 전체).

    목록 화면에서는 dict의 일부 필드만 표시. 별도 슬림 모드 없음.
    """
    if use_cache:
        ts, cached = _CACHE["list"]
        if cached is not None and time.time() - ts < _CACHE_TTL:
            return cached

    if get_mode() == "local":
        result = _list_local()
    else:
        result = _list_github()

    _CACHE["list"] = (time.time(), result)
    return result


def get_exhibition(slug: str, use_cache: bool = True) -> Optional[dict]:
    """slug에 해당하는 전시 레코드 전체 반환. 없으면 None."""
    if use_cache and slug in _CACHE["items"]:
        ts, cached = _CACHE["items"][slug]
        if time.time() - ts < _CACHE_TTL:
            return cached

    if get_mode() == "local":
        result = _get_local(slug)
    else:
        result = _get_github(slug)

    if result is not None:
        _CACHE["items"][slug] = (time.time(), result)
    return result


def save_exhibition(record: dict, commit_message: Optional[str] = None) -> dict:
    """전시 레코드 저장. id가 같으면 덮어쓰기.

    commit_message: github 모드에서 커밋 메시지 (기본 자동 생성)
    Returns: 저장된 레코드 (modified_at 갱신됨)
    """
    from schema import now_iso, validate
    issues = validate(record)
    if issues:
        raise ValueError(f"레코드 검증 실패: {issues}")

    record["modified_at"] = now_iso()

    if get_mode() == "local":
        _save_local(record)
    else:
        _save_github(record, commit_message)

    _cache_clear()  # 다음 list/get은 fresh
    return record


def delete_exhibition(slug: str) -> bool:
    """전시 레코드 삭제. 성공 시 True. 신중히 사용."""
    if get_mode() == "local":
        ok = _delete_local(slug)
    else:
        ok = _delete_github(slug)
    if ok:
        _cache_clear()
    return ok


# ──────────────────────────────────────────────
# Local 모드 구현
# ──────────────────────────────────────────────

def _list_local() -> list[dict]:
    dir_path = _local_dir()
    if not os.path.isdir(dir_path):
        return []
    results = []
    for filename in sorted(os.listdir(dir_path)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(dir_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _get_local(slug: str) -> Optional[dict]:
    filepath = os.path.join(_local_dir(), f"{slug}.json")
    if not os.path.isfile(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_local(record: dict) -> None:
    os.makedirs(_local_dir(), exist_ok=True)
    filepath = os.path.join(_local_dir(), f"{record['id']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def _delete_local(slug: str) -> bool:
    filepath = os.path.join(_local_dir(), f"{slug}.json")
    if not os.path.isfile(filepath):
        return False
    os.remove(filepath)
    return True


# ──────────────────────────────────────────────
# GitHub API 모드 구현
# ──────────────────────────────────────────────

def _list_github() -> list[dict]:
    """GitHub repo의 data/exhibitions/ 디렉터리 파일 목록을 가져온 뒤 각 파일 본문 다운로드.

    GitHub API: GET /repos/{repo}/contents/{path}?ref={branch}
    """
    r = requests.get(
        _gh_url(),
        headers=_gh_headers(),
        params={"ref": _github_branch()},
        timeout=30,
    )
    r.raise_for_status()
    files = r.json()
    results = []
    for f in files:
        if f.get("type") != "file" or not f.get("name", "").endswith(".json"):
            continue
        # 파일 본문은 별도 호출
        slug = f["name"][:-5]
        rec = _get_github(slug)
        if rec is not None:
            results.append(rec)
    return results


def _get_github(slug: str) -> Optional[dict]:
    r = requests.get(
        _gh_url(f"{slug}.json"),
        headers=_gh_headers(),
        params={"ref": _github_branch()},
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    info = r.json()
    encoding = info.get("encoding", "base64")
    if encoding == "base64":
        text = base64.b64decode(info["content"]).decode("utf-8")
    else:
        text = info.get("content", "")
    return json.loads(text)


def _save_github(record: dict, commit_message: Optional[str] = None) -> None:
    """레코드를 v5 저장소에 PUT.

    기존 파일이 있으면 sha 필요. GitHub API 자동 처리.
    """
    slug = record["id"]
    text = json.dumps(record, ensure_ascii=False, indent=2)
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")

    # 기존 파일 sha 조회
    sha = None
    existing = requests.get(
        _gh_url(f"{slug}.json"),
        headers=_gh_headers(),
        params={"ref": _github_branch()},
        timeout=30,
    )
    if existing.status_code == 200:
        sha = existing.json().get("sha")

    if not commit_message:
        action = "Update" if sha else "Create"
        commit_message = f"{action} exhibition: {slug}"

    payload = {
        "message": commit_message,
        "content": encoded,
        "branch": _github_branch(),
        "committer": {
            "name": "Exhibition Workspace",
            "email": "noreply@ilminmuseum.local",
        },
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(
        _gh_url(f"{slug}.json"),
        headers=_gh_headers(),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def _delete_github(slug: str) -> bool:
    """GitHub 파일 삭제. DELETE /repos/{repo}/contents/{path}"""
    # sha 필요
    existing = requests.get(
        _gh_url(f"{slug}.json"),
        headers=_gh_headers(),
        params={"ref": _github_branch()},
        timeout=30,
    )
    if existing.status_code == 404:
        return False
    existing.raise_for_status()
    sha = existing.json().get("sha")

    r = requests.delete(
        _gh_url(f"{slug}.json"),
        headers=_gh_headers(),
        json={
            "message": f"Delete exhibition: {slug}",
            "sha": sha,
            "branch": _github_branch(),
        },
        timeout=30,
    )
    return r.status_code in (200, 204)
