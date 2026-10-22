"""카카오톡 화면에서 사용자가 복사한 텍스트만 읽는 자체 backend."""

import platform
import subprocess
from datetime import datetime, timezone

from .core import CollectionError


class ClipboardBackend:
    kind = "clipboard"

    def __init__(self, runner=subprocess.run):
        self.runner = runner

    def command(self):
        if platform.system() == "Darwin":
            return ["pbpaste"]
        if platform.system() == "Windows":
            return ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
        raise CollectionError("macOS 또는 Windows에서만 화면 복사를 읽을 수 있습니다.")

    async def read(self, _room):
        try:
            completed = self.runner(
                self.command(),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            raise CollectionError(
                "클립보드를 읽지 못했습니다. 카카오톡에서 내용을 복사한 뒤 다시 시도하세요."
            ) from None
        text = completed.stdout.strip()
        if not text:
            raise CollectionError(
                "복사된 텍스트가 없습니다. 카카오톡에서 읽을 내용을 먼저 복사하세요."
            )
        return {
            "text": text,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "clipboard",
        }
