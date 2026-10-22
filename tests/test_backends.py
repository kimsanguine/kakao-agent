import asyncio
import subprocess

import pytest

from kakao_agent.backends import ClipboardBackend
from kakao_agent.core import CollectionError


def run(coro):
    return asyncio.run(coro)


def test_clipboard_backend_uses_runner_and_never_receives_room_name():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="복사한 화면", stderr="")

    backend = ClipboardBackend(runner=runner)
    backend.command = lambda: ["clipboard-reader"]
    result = run(backend.read("민감한 방 이름"))
    assert result["text"] == "복사한 화면"
    assert calls[0][0] == ["clipboard-reader"]
    assert "민감한 방 이름" not in str(calls)


@pytest.mark.parametrize("stdout", ["", "   \n"])
def test_empty_clipboard_fails_loudly(stdout):
    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

    backend = ClipboardBackend(runner=runner)
    backend.command = lambda: ["clipboard-reader"]
    with pytest.raises(CollectionError, match="복사된 텍스트"):
        run(backend.read("업무"))


def test_clipboard_command_error_hides_system_error_text():
    def runner(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["clipboard"], stderr="PRIVATE_PATH")

    backend = ClipboardBackend(runner=runner)
    backend.command = lambda: ["clipboard-reader"]
    with pytest.raises(CollectionError) as exc:
        run(backend.read("업무"))
    assert "PRIVATE_PATH" not in str(exc.value)
