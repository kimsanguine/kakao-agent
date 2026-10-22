# Kakao Agent

- 한국어 비개발자용, 읽기 전용 카카오톡 MCP·수집 도구다.
- macOS는 자체 구현한 로컬 DB backend, Windows는 자체 구현한 열린 창 접근성 backend를 사용한다. 외부 MCP·CLI를 실행하거나 등록하지 않는다.
- 공개 저장소에는 실제 대화, 방 제목, 방 ID, 계정 식별값, 키, 원문 로그를 넣지 않는다.
- 발송, 자동 로그인, 외부 전달, 카카오톡 데이터 변경, OS 권한 자동 변경은 구현 범위 밖이다.
- 설정의 방 allowlist는 코드에서 검사하고, 미허용 별칭은 backend를 호출하기 전에 차단한다.
- Mac `discover`는 로컬 CLI에만 두고 MCP 도구로 방 목록을 탐색하지 않는다.
- 테스트: `uv run pytest -q`, 정적 검사: `uv run ruff check src tests`.
- 실제 Mac DB와 Windows 화면 검증은 fixture·MCP subprocess 테스트와 구분해 기록한다.
- 변경은 `docs/progress.md`에 구현, 검증, 잔여를 기록한다.
