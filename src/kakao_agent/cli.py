"""운영체제의 카카오톡 로컬 기록을 읽는 자체 CLI. 발송은 하지 않는다."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .backends import create_backend
from .config import default_path, initial, load, save
from .core import CollectionError, Service


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description="운영체제별 읽기 전용 카카오톡 MCP")
    parser.add_argument("--config", type=Path, default=default_path())
    subs = parser.add_subparsers(dest="action", required=True)
    subs.add_parser("init", help="개인 허용 목록 생성, 기존 설정 덮어쓰기 없음")
    allow = subs.add_parser("allow", help="로컬에서 읽을 방의 별칭 추가")
    allow.add_argument("alias")
    allow.add_argument(
        "--target", required=True, help="Mac은 방 숫자 ID, Windows는 열린 창 이름"
    )
    remove = subs.add_parser("remove", help="로컬 허용 목록에서 방 별칭 제거")
    remove.add_argument("alias")
    subs.add_parser("rooms")
    subs.add_parser(
        "discover", help="Mac에서만 로컬 방 ID와 제목을 확인. MCP에는 노출하지 않음"
    )
    subs.add_parser(
        "doctor", help="설정과 로컬 backend만 점검. 카카오톡 원문은 읽지 않음"
    )
    subs.add_parser("serve")
    subs.add_parser("prepare", help="Mac 로컬 DB 읽기 준비. 대화 원문은 읽지 않음")
    read = subs.add_parser("read", help="허용한 방의 로컬 기록을 읽기")
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
            raw["rooms"][args.alias] = args.target
            save(args.config, raw)
            print("허용 방을 추가했습니다.")
            return
        if args.action == "remove":
            if args.alias not in raw["rooms"]:
                raise ValueError("허용 목록에 없는 별칭입니다.")
            del raw["rooms"][args.alias]
            save(args.config, raw)
            print("허용 방을 제거했습니다.")
            return
        if args.action == "serve":
            from .server import create_server

            create_server(args.config).run()
            return

        backend = create_backend(account_ids=settings.mac_account_ids)
        if args.action == "prepare":
            if backend.kind != "macos-local-db":
                raise ValueError("Mac에서만 로컬 DB 준비를 실행할 수 있습니다.")
            account_ids = backend.prepare()
            raw["mac_account_ids"] = list(account_ids)
            save(args.config, raw)
            print(
                "Mac 로컬 DB 읽기 준비를 저장했습니다. 계정 식별값은 출력하지 않습니다."
            )
            return
        if args.action == "discover":
            if backend.kind != "macos-local-db":
                raise ValueError("Mac에서만 로컬 방 목록 확인을 실행할 수 있습니다.")
            print(
                json.dumps(
                    {"rooms": backend.discover_rooms()}, ensure_ascii=False, indent=2
                )
            )
            return
        service = Service(settings, backend)
        if args.action == "rooms":
            result = service.rooms()
        elif args.action == "doctor":
            result = {
                "configured_rooms": len(settings.rooms),
                "source": backend.kind,
                "live_kakao_read": "not_tested",
                "send_tools": False,
            }
        else:
            result = asyncio.run(service.read(args.room))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except CollectionError as error:
        print(f"실패: {error}", file=sys.stderr)
        raise SystemExit(1)
    except (OSError, ValueError, KeyError, TypeError):
        print(
            "실패: 설정, 허용 방 또는 로컬 카카오톡 상태를 확인하세요. 원문 오류는 출력하지 않습니다.",
            file=sys.stderr,
        )
        raise SystemExit(1)
