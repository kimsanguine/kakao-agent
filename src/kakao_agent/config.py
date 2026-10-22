"""개인 허용 목록만 저장한다. 카카오 DB·외부 MCP·OS 권한을 설정하지 않는다."""

import json
import os
import tempfile
from pathlib import Path

from .core import Settings


def default_path():
    if os.name == "nt":
        return (
            Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
            / "HabixKakao"
            / "config.json"
        )
    return Path.home() / ".config" / "habix-kakao" / "config.json"


def initial():
    return {"mode": "clipboard", "rooms": {}, "max_chars": 100_000}


def load(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) - {"mode", "rooms", "max_chars"}:
        raise ValueError("알 수 없는 설정 항목입니다.")
    if raw.get("mode") != "clipboard":
        raise ValueError("지원하지 않는 입력 방식입니다.")
    return raw, Settings(raw["rooms"], raw.get("max_chars", 100_000))


def save(path, raw, *, create=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    if create:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
        if os.name != "nt":
            path.chmod(0o600)
        return
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".kakao-config-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
