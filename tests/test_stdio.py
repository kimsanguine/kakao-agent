import asyncio
import json
import os
import platform
import subprocess
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def test_real_stdio_server_lists_only_read_tools_and_denies_before_backend(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {"mode": "native", "rooms": {"업무": "123"}, "max_chars": 100_000},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "kakao_agent", "--config", str(config), "serve"],
            env={**os.environ},
        )
        async with Client(params) as client:
            tools = await client.list_tools()
            rooms = await client.call_tool("kakao_rooms", {})
            denied = await client.call_tool("kakao_read", {"room": "미허용"})
            removed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "kakao_agent",
                    "--config",
                    str(config),
                    "remove",
                    "업무",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env={**os.environ},
            )
            rooms_after_remove = await client.call_tool("kakao_rooms", {})
            denied_after_remove = await client.call_tool("kakao_read", {"room": "업무"})
            return tools, rooms, denied, removed, rooms_after_remove, denied_after_remove

    tools, rooms, denied, removed, rooms_after_remove, denied_after_remove = asyncio.run(
        exercise()
    )
    assert {tool.name for tool in tools.tools} == {"kakao_rooms", "kakao_read"}
    assert json.loads(rooms.content[0].text) == {
        "rooms": ["업무"],
        "source": (
            "macos-local-db" if platform.system() == "Darwin" else "windows-visible-ui"
        ),
    }
    assert denied.is_error
    assert "허용 목록에 없는 방" in denied.content[0].text
    assert "unexpected exception" not in denied.content[0].text.lower()
    assert removed.returncode == 0, removed.stderr
    assert json.loads(rooms_after_remove.content[0].text)["rooms"] == []
    assert denied_after_remove.is_error
    assert "허용 목록에 없는 방" in denied_after_remove.content[0].text
