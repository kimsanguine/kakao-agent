import json

import pytest

from kakao_agent.config import load


def test_mac_account_ids_are_private_config_and_not_room_aliases(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "mode": "native",
                "rooms": {"업무": "123"},
                "max_chars": 100_000,
                "mac_account_ids": [42, 47],
            }
        ),
        encoding="utf-8",
    )
    raw, settings = load(path)
    assert raw["mac_account_ids"] == [42, 47]
    assert settings.rooms == {"업무": "123"}
    assert settings.mac_account_ids == (42, 47)


def test_text_mac_account_id_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "mode": "native",
                "rooms": {},
                "max_chars": 100_000,
                "mac_account_ids": ["42"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load(path)
