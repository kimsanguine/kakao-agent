"""표준 MCP 입구. 화면 자동 조작·설정 변경·발송 도구는 제공하지 않는다."""

from mcp.server.mcpserver import MCPServer

from .core import Service


def create_server(settings, backend):
    service = Service(settings, backend)
    server = MCPServer("habix-kakao-agent")

    @server.tool()
    def kakao_rooms() -> dict:
        """사용자가 로컬 설정에서 허용한 방 별칭만 표시합니다."""
        return service.rooms()

    @server.tool()
    async def kakao_read(room: str) -> dict:
        """현재 클립보드의 카카오톡 복사 내용을 허용 방으로 읽습니다. 발송하지 않습니다."""
        return await service.read(room)

    return server
