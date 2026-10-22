"""운영체제별, 읽기 전용 카카오톡 입력 backend."""

import base64
import hashlib
import json
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .core import CollectionError


class MacDatabaseBackend:
    """내 Mac의 카카오톡 로컬 DB를 읽기 전용으로 여는 backend."""

    kind = "macos-local-db"

    def __init__(
        self,
        runner=subprocess.run,
        *,
        container_root=None,
        account_ids=(),
        identity_probe=None,
    ):
        self.runner = runner
        self.container_root = Path(container_root or self._default_container_root())
        self.account_ids = tuple(account_ids)
        self.identity_probe = identity_probe

    @staticmethod
    def _default_container_root():
        return (
            Path.home()
            / "Library/Containers/com.kakao.KakaoTalkMac/Data/Library/Application Support"
            / "com.kakao.KakaoTalkMac"
        )

    @staticmethod
    def derive_key(device_uuid, account_id):
        """기기와 로그인 계정에 묶인 SQLCipher 키 문자열을 계산한다."""
        if not isinstance(device_uuid, str) or not device_uuid:
            raise CollectionError("이 Mac의 기기 식별값을 확인하지 못했습니다.")
        if type(account_id) is not int or account_id < 0:
            raise CollectionError("로컬 계정 식별값을 확인하지 못했습니다.")
        encoded_hashes = base64.b64encode(
            hashlib.sha1(device_uuid.encode()).digest()
            + hashlib.sha256(device_uuid.encode()).digest()
        ).decode()
        password = "F".join(
            [
                "A",
                encoded_hashes,
                "|",
                "F",
                device_uuid[:5],
                "H",
                str(account_id),
                "|",
                device_uuid[7:],
            ]
        )[::-1]
        salt = device_uuid[int(len(device_uuid) * 0.3) :]
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), 100_000, dklen=128
        ).hex()

    def device_uuid(self):
        try:
            completed = self.runner(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            raise CollectionError("이 Mac의 기기 식별값을 읽지 못했습니다.") from None
        matched = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', completed.stdout)
        if not matched:
            raise CollectionError("이 Mac의 기기 식별값 형식을 확인하지 못했습니다.")
        return matched.group(1)

    @staticmethod
    def database_name(device_uuid, account_id):
        """사용자 ID와 Mac 기기값으로 현재 계정 DB의 파일명을 계산한다."""
        encoded_hashes = base64.b64encode(
            hashlib.sha1(device_uuid.encode()).digest()
            + hashlib.sha256(device_uuid.encode()).digest()
        ).decode()
        password = ".".join(
            [".", "F", str(account_id), "A", "F", device_uuid[::-1], ".", "|"]
        )
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            encoded_hashes[::-1].encode(),
            100_000,
            dklen=128,
        ).hex()[28:106]

    @staticmethod
    def _probe_source():
        return Path(__file__).with_name("mac_identity_probe.swift")

    @staticmethod
    def _probe_binary():
        return Path.home() / "Library/Caches/habix-kakao/mac_identity_probe"

    def _compile_identity_probe(self):
        source = self._probe_source()
        binary = self._probe_binary()
        if not source.is_file():
            raise CollectionError(
                "Mac 계정 확인 도구를 찾지 못했습니다. uv sync를 다시 실행하세요."
            )
        binary.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.runner(
                ["swiftc", "-O", str(source), "-o", str(binary)],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            raise CollectionError(
                "Mac 계정 확인 도구를 준비하지 못했습니다. Xcode Command Line Tools를 확인하세요."
            ) from None
        return binary

    def recover_account_id(self):
        """대화 원문 없이 활성 계정의 내부 숫자 ID만 찾는다."""
        if self.identity_probe is not None:
            candidate = self.identity_probe()
        else:
            binary = self._probe_binary()
            source = self._probe_source()
            if not binary.is_file() or binary.stat().st_mtime < source.stat().st_mtime:
                binary = self._compile_identity_probe()
            try:
                completed = self.runner(
                    [str(binary)],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=130,
                )
            except (OSError, subprocess.SubprocessError):
                raise CollectionError(
                    "활성 카카오톡 계정을 확인하지 못했습니다. 카카오톡 로그인 상태를 확인하세요."
                ) from None
            candidate = completed.stdout.strip()
        if isinstance(candidate, str) and candidate.isdigit():
            candidate = int(candidate)
        if type(candidate) is not int or candidate <= 0:
            raise CollectionError("활성 카카오톡 계정을 확인하지 못했습니다.")
        return candidate

    def recover_account_ids(self):
        return [self.recover_account_id()]

    def candidates(self):
        if not self.container_root.exists():
            raise CollectionError("카카오톡 로컬 저장소를 찾지 못했습니다.")
        return sorted(
            path
            for path in self.container_root.iterdir()
            if path.is_file() and re.fullmatch(r"[0-9a-f]{78}", path.name)
        )

    def database_path(self, account_id):
        path = self.container_root / self.database_name(self.device_uuid(), account_id)
        if not path.is_file():
            raise CollectionError("활성 카카오톡의 로컬 DB를 찾지 못했습니다.")
        return path

    @staticmethod
    def _quote_identifier(name):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise CollectionError("로컬 DB 구조를 안전하게 읽지 못했습니다.")
        return f'"{name}"'

    @classmethod
    def _message_query(cls, connection, chat_id):
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            if "chat" not in table.lower():
                continue
            quoted_table = cls._quote_identifier(table)
            columns = {
                row[1].lower(): row[1]
                for row in connection.execute(f"PRAGMA table_info({quoted_table})")
            }
            room_column = next(
                (
                    columns[name]
                    for name in ("chat_id", "chatid", "room_id")
                    if name in columns
                ),
                None,
            )
            text_column = next(
                (
                    columns[name]
                    for name in ("message", "text", "contents", "content")
                    if name in columns
                ),
                None,
            )
            time_column = next(
                (
                    columns[name]
                    for name in (
                        "created_at",
                        "createdat",
                        "sent_at",
                        "sentat",
                        "timestamp",
                        "time",
                    )
                    if name in columns
                ),
                None,
            )
            if not room_column or not text_column:
                continue
            selected_time = (
                cls._quote_identifier(time_column) if time_column else "NULL"
            )
            rows = connection.execute(
                f"SELECT {selected_time}, {cls._quote_identifier(text_column)} "
                f"FROM {quoted_table} WHERE {cls._quote_identifier(room_column)} = ? "
                "ORDER BY rowid DESC LIMIT 500",
                (str(chat_id),),
            ).fetchall()
            if rows:
                return list(reversed(rows))
        raise CollectionError("선택한 방의 텍스트 기록을 찾지 못했습니다.")

    @classmethod
    def _room_query(cls, connection):
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        ]
        for table in tables:
            if "chat" not in table.lower():
                continue
            quoted_table = cls._quote_identifier(table)
            columns = {
                row[1].lower(): row[1]
                for row in connection.execute(f"PRAGMA table_info({quoted_table})")
            }
            room_column = next(
                (
                    columns[name]
                    for name in ("chat_id", "chatid", "room_id", "id")
                    if name in columns
                ),
                None,
            )
            title_column = next(
                (
                    columns[name]
                    for name in ("title", "chat_name", "chatname", "name")
                    if name in columns
                ),
                None,
            )
            if room_column and title_column:
                rows = connection.execute(
                    f"SELECT {cls._quote_identifier(room_column)}, "
                    f"{cls._quote_identifier(title_column)} FROM {quoted_table} "
                    "WHERE "
                    f"{cls._quote_identifier(title_column)} IS NOT NULL "
                    "ORDER BY rowid DESC LIMIT 100"
                ).fetchall()
                if rows:
                    return rows
        raise CollectionError("연결할 카카오톡 방 목록을 찾지 못했습니다.")

    @staticmethod
    def _connect(path, key):
        try:
            from sqlcipher3 import dbapi2 as sqlcipher
        except ImportError:
            raise CollectionError(
                "로컬 DB 읽기 구성 요소를 준비하지 못했습니다. uv sync를 다시 실행하세요."
            ) from None
        if not re.fullmatch(r"[0-9a-f]{256}", key):
            raise CollectionError("카카오톡 로컬 DB 키 형식을 확인하지 못했습니다.")
        for compatibility in (3, 4):
            connection = None
            try:
                connection = sqlcipher.connect(f"file:{path}?mode=ro", uri=True)
                connection.execute(
                    f"PRAGMA cipher_default_compatibility = {compatibility}"
                )
                connection.execute(f"PRAGMA key = '{key}'")
                connection.execute("PRAGMA query_only = ON")
                connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
                return connection
            except Exception:
                if connection is not None:
                    connection.close()
        raise CollectionError("카카오톡 로컬 DB를 읽기 전용으로 열지 못했습니다.")

    def prepare(self):
        """원문을 읽지 않고, 실제 읽기 전용 DB 개방 가능 여부만 확인한다."""
        account_ids = self.account_ids or tuple(self.recover_account_ids())
        device_uuid = self.device_uuid()
        for account_id in account_ids:
            key = self.derive_key(device_uuid, account_id)
            try:
                connection = self._connect(self.database_path(account_id), key)
            except CollectionError:
                continue
            connection.close()
            self.account_ids = (account_id,)
            return self.account_ids
        raise CollectionError(
            "Mac 로컬 DB 읽기 준비를 확인하지 못했습니다. "
            "카카오톡을 최신 상태로 연 뒤 다시 시도하세요."
        )

    async def read(self, _alias, target):
        if not str(target).isdigit():
            raise CollectionError("Mac에서는 방을 숫자 식별값으로 연결해야 합니다.")
        account_ids = self.account_ids or tuple(self.recover_account_ids())
        device_uuid = self.device_uuid()
        for account_id in account_ids:
            key = self.derive_key(device_uuid, account_id)
            try:
                connection = self._connect(self.database_path(account_id), key)
            except CollectionError:
                continue
            try:
                messages = self._message_query(connection, target)
                connection.close()
            except CollectionError:
                connection.close()
                continue
            text = "\n".join(str(message) for _, message in messages if message)
            if text:
                return {
                    "text": text,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "source": self.kind,
                    "coverage": "local-database",
                    "room_verified": True,
                }
        raise CollectionError("선택한 방의 로컬 기록을 읽지 못했습니다.")

    def discover_rooms(self):
        """설정 전용 CLI에서만 방 ID와 제목을 확인한다. MCP에는 노출하지 않는다."""
        account_ids = self.account_ids
        if not account_ids:
            raise CollectionError("먼저 prepare로 Mac 로컬 DB 읽기를 준비하세요.")
        device_uuid = self.device_uuid()
        for account_id in account_ids:
            key = self.derive_key(device_uuid, account_id)
            try:
                connection = self._connect(self.database_path(account_id), key)
            except CollectionError:
                continue
            try:
                rooms = self._room_query(connection)
                connection.close()
            except CollectionError:
                connection.close()
                continue
            return [
                {"target": str(room_id), "title": str(title)}
                for room_id, title in rooms
            ]
        raise CollectionError("연결할 카카오톡 방 목록을 읽지 못했습니다.")


class WindowsUiBackend:
    """열려 있는 카카오톡 창의 접근성 텍스트만 읽는 Windows backend."""

    kind = "windows-visible-ui"

    def __init__(self, runner=subprocess.run):
        self.runner = runner

    @staticmethod
    def command(target):
        encoded_target = base64.b64encode(str(target).encode("utf-8")).decode()
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$target = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{encoded_target}'))
$windows = @(Get-Process KakaoTalk -ErrorAction Stop | Where-Object {{$_.MainWindowHandle -ne 0}} | ForEach-Object {{ [System.Windows.Automation.AutomationElement]::FromHandle($_.MainWindowHandle) }})
$matches = @($windows | Where-Object {{$_.Current.Name -eq $target}})
if ($matches.Count -eq 0) {{ @{{status='missing'}} | ConvertTo-Json -Compress; exit 0 }}
if ($matches.Count -ne 1) {{ @{{status='ambiguous'}} | ConvertTo-Json -Compress; exit 0 }}
$textNodes = $matches[0].FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$lines = @($textNodes | ForEach-Object {{ if ($_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text -and $_.Current.Name) {{ $_.Current.Name }} }} | Select-Object -Unique)
if ($lines.Count -eq 0) {{ @{{status='empty'}} | ConvertTo-Json -Compress; exit 0 }}
@{{status='ok'; text=($lines -join [Environment]::NewLine); captured_at=[DateTime]::UtcNow.ToString('o')}} | ConvertTo-Json -Compress
""".strip()
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]

    async def read(self, _alias, target):
        try:
            completed = self.runner(
                self.command(target),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            payload = json.loads(completed.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            raise CollectionError("열려 있는 카카오톡 창을 읽지 못했습니다.") from None
        status = payload.get("status")
        if status == "ambiguous":
            raise CollectionError("같은 이름의 카카오톡 창은 하나만 열어 두세요.")
        if status == "missing":
            raise CollectionError("연결한 이름의 카카오톡 창을 찾지 못했습니다.")
        if (
            status != "ok"
            or not isinstance(payload.get("text"), str)
            or not payload["text"].strip()
        ):
            raise CollectionError("카카오톡 창에 읽을 텍스트가 없습니다.")
        captured_at = payload.get("captured_at")
        if not isinstance(captured_at, str):
            raise CollectionError("카카오톡 창 읽기 시각을 확인하지 못했습니다.")
        return {
            "text": payload["text"].strip(),
            "captured_at": captured_at,
            "source": self.kind,
            "coverage": "visible-window",
            "room_verified": True,
        }


def create_backend(system=None, **kwargs):
    selected = system or platform.system()
    if selected == "Darwin":
        return MacDatabaseBackend(**kwargs)
    if selected == "Windows":
        kwargs.pop("account_ids", None)
        return WindowsUiBackend(**kwargs)
    raise CollectionError(
        "macOS 또는 Windows에서만 카카오톡 로컬 기록을 읽을 수 있습니다."
    )
