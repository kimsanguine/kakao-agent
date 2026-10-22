import asyncio

import pytest

from kakao_agent.core import AccessDenied, CollectionError, Service, Settings


class Backend:
    kind = "clipboard"

    def __init__(self, capture):
        self.capture = capture
        self.calls = []

    async def read(self, room):
        self.calls.append(room)
        return self.capture


def run(coro):
    return asyncio.run(coro)


def test_unallowed_room_never_reads_clipboard():
    backend = Backend({})
    with pytest.raises(AccessDenied):
        run(Service(Settings({}), backend).read("개인"))
    assert backend.calls == []


def test_only_room_aliases_are_listed_not_kakao_rooms():
    result = Service(Settings({"업무": True, "개인": True}), Backend({})).rooms()
    assert result == {"rooms": ["개인", "업무"], "source": "clipboard"}


def test_clipboard_text_minimizes_contact_and_hides_backend_fields():
    backend = Backend(
        {
            "text": "메일 a@example.com 전화 010-1234-5678",
            "captured_at": "2026-10-22T00:00:00+00:00",
            "source": "clipboard",
            "window_id": "private",
        }
    )
    result = run(Service(Settings({"업무": True}), backend).read("업무"))
    assert result["text"] == "메일 [EMAIL] 전화 [PHONE]"
    assert "window_id" not in result
    assert result["room_verified"] is False


@pytest.mark.parametrize("max_chars", [True, 0, 300_001])
def test_invalid_character_limit_is_rejected(max_chars):
    with pytest.raises(ValueError):
        Settings({}, max_chars=max_chars)


@pytest.mark.parametrize(
    "capture",
    [
        {},
        {"text": 1, "captured_at": "now", "source": "clipboard"},
        {"text": "a", "captured_at": 1, "source": "clipboard"},
        {"text": "a", "captured_at": "now", "source": "other"},
    ],
)
def test_bad_capture_is_not_returned_to_agent(capture):
    with pytest.raises(CollectionError):
        run(Service(Settings({"업무": True}), Backend(capture)).read("업무"))


def test_overlong_clipboard_text_is_rejected_not_silently_cut():
    backend = Backend(
        {
            "text": "가" * 11,
            "captured_at": "2026-10-22T00:00:00+00:00",
            "source": "clipboard",
        }
    )
    with pytest.raises(CollectionError, match="너무 깁니다"):
        run(Service(Settings({"업무": True}, max_chars=10), backend).read("업무"))
