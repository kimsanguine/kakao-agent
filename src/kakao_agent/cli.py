"""카카오톡 화면 복사를 읽는 자체 CLI. 자동 조작·DB 접근·발송은 하지 않는다."""

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from .backends import ClipboardBackend
from .config import default_path, initial, load, save
from .core import Service


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="화면 복사 기반 읽기 전용 카카오톡 MCP"
    )
    parser.add_argument("--config", type=Path, default=default_path())
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("init", help="개인 허용 목록 생성, 기존 설정 덮어쓰기 없음")
    allow = subs.add_parser("allow", help="복사해 읽을 방의 별칭 추가")
    allow.add_argument("alias")
    subs.add_parser("rooms")
    subs.add_parser("doctor", help="클립보드 명령과 설정만 점검. 카카오톡은 읽지 않음")
    subs.add_parser("serve")
    read = subs.add_parser("read", help="현재 클립보드의 복사 내용을 허용 방으로 읽기")
    read.add_argument("room")
    args = parser.parse_args()
    try:
        if args.action == "init":
            save(args.config, initial(), create=True)
            print("개인 허용 목록을 생성했습니다. 허용한 방은 아직 없습니다.")
            return
        raw, settings = load(args.config)
        if args.action == "allow":
            if not args.alias.strip() or args.alias in raw["rooms"]:
                raise ValueError("비어 있거나 중복된 별칭입니다.")
            raw["rooms"][args.alias] = True
            save(args.config, raw)
            print("허용 방을 추가했습니다.")
            return
        backend = ClipboardBackend()
        if args.action == "serve":
            from .server import create_server

            create_server(settings, backend).run()
            return
        service = Service(settings, backend)
        if args.action == "rooms":
            result = service.rooms()
        elif args.action == "doctor":
            command = backend.command()
            result = {
                "configured_rooms": len(settings.rooms),
                "source": "clipboard",
                "clipboard_command_found": shutil.which(command[0]) is not None,
                "live_kakao_read": "not_tested",
                "send_tools": False,
            }
        else:
            result = asyncio.run(service.read(args.room))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "실패: 설정, 허용 방 또는 클립보드 상태를 확인하세요. 원문 오류는 출력하지 않습니다.",
            file=sys.stderr,
        )
        raise SystemExit(1)
