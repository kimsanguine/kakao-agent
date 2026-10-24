"""표준 MCP 입구. 설정 변경·발송 도구는 제공하지 않는다."""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .backends import create_backend
from .config import load
from .core import AccessDenied, CollectionError, Service


def create_server(config_path):
    def current_service():
        # 허용 목록은 요청마다 다시 읽는다. remove 뒤 이미 열린 MCP 세션에도
        # 철회가 즉시 반영돼야 한다.
        try:
            _, settings = load(config_path)
            backend = create_backend(account_ids=settings.mac_account_ids)
            return Service(settings, backend)
        except (OSError, ValueError, KeyError, TypeError):
            raise ToolError("로컬 설정을 다시 확인하세요. 원문은 읽지 않았습니다.") from None

    server = MCPServer("habix-kakao-agent")

    @server.tool()
    def kakao_rooms() -> dict:
        """사용자가 로컬 설정에서 허용한 방 별칭만 표시합니다."""
        return current_service().rooms()

    @server.tool()
    async def kakao_read(room: str) -> dict:
        """허용한 카카오톡 로컬 기록을 읽습니다. 발송하지 않습니다."""
        try:
            return await current_service().read(room)
        except (AccessDenied, CollectionError) as error:
            # 사용자가 복구할 수 있는 차단은 MCP가 crash로 기록하지 않게 한다.
            raise ToolError(str(error)) from None

    return server
