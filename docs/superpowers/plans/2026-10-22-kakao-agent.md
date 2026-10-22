# Kakao Agent Implementation Plan

**Goal:** Mac·Windows에서 같은 화면 복사 방식으로 동작하는 읽기 전용 카카오톡 MCP.

## Constraints

발송 없음. 실데이터 공개 금지. 카카오 DB·외부 수집기·화면 자동 조작 없음.

- [x] Task1: 허용 목록 선차단, 일부 연락처 치환, 과도한 텍스트 차단을 구현하고 테스트한다.
- [x] Task2: 자체 MCP에 방 별칭 확인과 클립보드 읽기만 노출한다.
- [x] Task3: 개인 설정 생성·별칭 허용·CLI·Codex/Claude/Hermes 연결 안내를 작성한다.
- [ ] Task4: 새 환경 설치, 전체 테스트, 빌드, 비밀·원문 검사와 Mac·Windows의 실제 화면 복사 확인을 끝낸다.
