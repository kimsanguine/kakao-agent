import json
import os
import subprocess
import sys


def command(config, *args):
    return subprocess.run(
        [sys.executable, "-m", "kakao_agent", "--config", str(config), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ},
    )


def test_init_does_not_overwrite_and_defaults_to_no_rooms(tmp_path):
    config = tmp_path / "settings.json"
    first = command(config, "init")
    assert first.returncode == 0, first.stderr
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data == {"mode": "clipboard", "rooms": {}, "max_chars": 100_000}
    assert command(config, "init").returncode != 0
    assert json.loads(config.read_text(encoding="utf-8")) == data


def test_allow_keeps_only_local_alias_not_room_id_or_title(tmp_path):
    config = tmp_path / "settings.json"
    command(config, "init")
    result = command(config, "allow", "업무")
    assert result.returncode == 0, result.stderr
    assert json.loads(config.read_text(encoding="utf-8"))["rooms"] == {"업무": True}
    assert command(config, "allow", "업무").returncode != 0


def test_cli_missing_config_errors_without_fake_success(tmp_path):
    result = command(tmp_path / "missing.json", "rooms")
    assert result.returncode != 0
    assert not result.stdout


def test_removed_backend_switch_is_not_a_supported_setup_choice(tmp_path):
    config = tmp_path / "settings.json"
    assert command(config, "init", "--backend", "legacy").returncode != 0
