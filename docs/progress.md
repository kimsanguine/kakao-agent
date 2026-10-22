# kakao-agent 작업 현황

## 2026-10-22

### 구현

- 클립보드 backend를 제거했다. macOS는 자체 로컬 DB backend, Windows는 자체 열린 창 접근성 backend로 분리했다.
- macOS backend는 기기·로컬 계정 표식으로 읽기 키를 만들고, 후보 DB를 읽기 전용으로 연 뒤 선택한 방의 텍스트만 찾는다. `prepare`는 계정 식별값을 로컬 설정에만 저장하고 출력하지 않는다.
- macOS의 `discover`는 사용자가 직접 실행한 CLI에서만 방 ID와 제목을 보여 준다. MCP에는 `kakao_rooms`, `kakao_read`만 남겨 전체 방 탐색을 막는다.
- Windows backend는 지정한 제목과 정확히 일치하는 열린 카카오톡 창 하나의 접근성 텍스트만 읽는다. 클릭, 입력, 복사, 전송을 하지 않는다.
- 허용 목록 검사, 미허용 방의 backend 선차단, 과도한 길이 차단, 연락처 일부 치환을 유지했다.

### 검증

- 자체 테스트: `uv run pytest -q`에서 24개 통과.
- 정적 검사: `uv run ruff check src tests` 통과.
- `sqlcipher3`를 실제 설치하고 메모리 DB의 읽기·쓰기 기본 동작을 확인했다. 카카오 DB에는 연결하지 않았다.
- GitHub Actions: macOS·Windows와 Python 3.11·3.13 조합 4개 행에서 설치, 테스트, 정적 검사를 실행한다.
- 실제 MCP subprocess로 도구 목록과 미허용 방의 backend 선차단을 확인한다.

### 남은 검증과 공개 기준

- Mac: 비민감 방 하나에서 `prepare → discover → allow → read`를 실제로 확인한다. 이 단계는 아직 하지 않았고, 실제 대화를 열지 않았다.
- Windows: 같은 제목의 창 하나를 열어 `allow → read`로 접근성 텍스트가 실제 보이는 범위와 맞는지 확인한다. Windows 실기기는 아직 없다.
- 공개 전: 예제 설정·테스트 출력·Git 이력에 실제 방 이름, 대화, 계정 식별값, 키가 없는지 다시 검사한다.
- 자동화 테스트는 개인 Mac DB와 실제 Windows 카카오톡 창의 결과를 보증하지 않는다.
