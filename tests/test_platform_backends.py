import asyncio
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from kakao_agent.backends import MacDatabaseBackend, WindowsUiBackend, create_backend
from kakao_agent.core import CollectionError


def run(coro):
    return asyncio.run(coro)


def test_backend_factory_selects_the_native_mac_database_reader():
    backend = create_backend(system="Darwin")
    assert isinstance(backend, MacDatabaseBackend)
    assert backend.kind == "macos-local-db"


def test_backend_factory_selects_the_native_windows_visible_window_reader():
    backend = create_backend(system="Windows")
    assert isinstance(backend, WindowsUiBackend)
    assert backend.kind == "windows-visible-ui"


def test_windows_factory_ignores_mac_only_private_account_value():
    assert isinstance(
        create_backend(system="Windows", account_ids=(42,)), WindowsUiBackend
    )


def test_macos_key_derivation_has_a_fixed_known_result():
    backend = MacDatabaseBackend(runner=lambda *_args, **_kwargs: None)
    assert backend.derive_key("12345678-1234-1234-1234-1234567890AB", 42) == (
        "db6d8737ba0d69ba55b0687520c194fef2b2bea592809bcf416eeb1812575691"
        "2d667fee5c13a5d44521c2faa0bd305124fee50053c93c28179675ccc5397f300"
        "02b10d6ab4676fa80e77af0359d0bd6a573a8cfad0212247b28d236e90bff31e"
        "8e149f00231735ca1a32a0b9ca52c6e7b4e0533f8bebf15354802e2b6350762"
    )


def test_macos_recovers_the_active_account_through_its_native_probe():
    backend = MacDatabaseBackend(identity_probe=lambda: 42)
    assert backend.recover_account_id() == 42
    assert backend.recover_account_ids() == [42]


def test_macos_database_name_has_the_expected_encrypted_filename_shape():
    name = MacDatabaseBackend.database_name("12345678-1234-1234-1234-1234567890AB", 42)
    assert len(name) == 78
    assert name.isalnum()


def test_macos_prepare_fails_if_no_candidate_database_opens():
    backend = MacDatabaseBackend(
        runner=lambda *_args, **_kwargs: None, account_ids=(3,)
    )
    backend.device_uuid = lambda: "12345678-1234-1234-1234-1234567890AB"
    backend.database_path = lambda _account_id: Path("candidate")
    backend._connect = lambda _path, _key: (_ for _ in ()).throw(
        CollectionError("closed")
    )
    with pytest.raises(CollectionError, match="준비를 확인하지 못했습니다"):
        backend.prepare()


def test_macos_prepare_saves_all_recovered_accounts_only_after_read_only_open():
    backend = MacDatabaseBackend(
        runner=lambda *_args, **_kwargs: None, account_ids=(3, 7)
    )
    backend.device_uuid = lambda: "12345678-1234-1234-1234-1234567890AB"
    backend.database_path = lambda _account_id: Path("candidate")
    connection = sqlite3.connect(":memory:")
    backend._connect = lambda _path, _key: connection
    assert backend.prepare() == (3,)
    assert backend.account_ids == (3,)


def test_macos_room_discovery_reads_only_room_id_and_title():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE chat_rooms (chat_id INTEGER, title TEXT, hidden TEXT)"
    )
    connection.execute("INSERT INTO chat_rooms VALUES (123, '프로젝트', 'private')")
    assert MacDatabaseBackend._room_query(connection) == [(123, "프로젝트")]


def test_macos_room_discovery_supports_the_current_camel_case_room_title_column():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE NTChatRoom (chatId INTEGER, chatName TEXT)")
    connection.execute("INSERT INTO NTChatRoom VALUES (123, '프로젝트')")
    assert MacDatabaseBackend._room_query(connection) == [(123, "프로젝트")]


def test_windows_reader_refuses_an_ambiguous_window_match_without_copying():
    backend = WindowsUiBackend(
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps({"status": "ambiguous"}),
            stderr="",
        )
    )
    with pytest.raises(CollectionError, match="하나만 열어"):
        run(backend.read("업무", "프로젝트"))


def test_windows_reader_returns_only_text_from_the_exact_visible_window():
    backend = WindowsUiBackend(
        runner=lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [],
            0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "text": "확인할 내용",
                    "captured_at": "2026-10-22T00:00:00+00:00",
                }
            ),
            stderr="",
        )
    )
    assert run(backend.read("업무", "프로젝트")) == {
        "text": "확인할 내용",
        "captured_at": "2026-10-22T00:00:00+00:00",
        "source": "windows-visible-ui",
        "coverage": "visible-window",
        "room_verified": True,
    }
