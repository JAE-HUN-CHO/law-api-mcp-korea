# law-api-mcp-korea

법제처 국가법령정보 공동활용 OPEN API를 감싸는 **CLI + MCP 서버** Python 패키지입니다.

191개 API 문서를 정본으로 유지하면서, 법령 약어 해석·판례 통합 검색·AI 인용 검증 기능을 추가로 제공합니다.

공식 배포 채널: **GitHub Releases only** (PyPI 미지원)

---

## 설치

**공개 배포용 (wheel):**

```bash
pip install law_api_mcp_korea-0.1.0-py3-none-any.whl
```

wheel 파일은 [GitHub Releases](https://github.com/JAE-HUN-CHO/law-api-mcp-korea/releases)에서 내려받습니다.

**로컬 개발용:**

```bash
uv sync          # 의존성 설치
pip install -e . # 또는 editable 설치
```

---

## 설정

법제처 OPEN API는 `OC`(사용자 이메일 ID) 파라미터가 필수입니다.

```bash
export LAW_API_OC=your_oc_value
# 또는
echo LAW_API_OC=your_oc_value > .env
```

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `LAW_API_OC` | — | API 인증키 (이메일 ID) |
| `LAW_API_TIMEOUT` | `30` | 요청 타임아웃(초) |
| `LAW_API_FORCE_HTTPS` | — | `true`/`1`이면 http → https 강제 변환 |

`.env`는 로컬 전용이며 저장소에 커밋하지 않습니다.

---

## 주요 기능

### 법령 약어 자동 해석

`search_current_law`, `list_apis`, `search_decisions` 등에서 약어를 정식 법령명으로 자동 변환합니다.

```
화관법  → 화학물질관리법
근기법  → 근로기준법
개보법  → 개인정보 보호법
공정거래법 → 독점규제 및 공정거래에 관한 법률
```

### 판례·결정례 통합 검색 (`search_decisions`)

9개 도메인을 하나의 도구로 검색합니다. 코드 또는 한국어 약어를 모두 지원합니다.

| 코드 | 한국어 약어 | 도메인 |
| --- | --- | --- |
| `prec` | 판례, 대법원 | 대법원 판례 |
| `detc` | 헌재, 헌법재판소 | 헌법재판소 결정례 |
| `decc` | 행심, 행정심판 | 행정심판례 |
| `expc` | 법령해석, 유권해석 | 법령해석례 |
| `tt` | 조심, 조세심판 | 조세심판원 |
| `kmst` | 해심, 해양심판 | 해양안전심판원 |
| `nlrc` | 노위, 노동위원회 | 노동위원회 |
| `acr` | 권익위, 국민권익위 | 국민권익위원회 |
| `moleg` | 법제처 | 법제처 법령해석 |

### AI 법령 인용 검증 (`verify_citations`)

AI가 생성한 법률 텍스트에서 법령 인용을 추출하고 실제 DB와 대조해 환각 여부를 마킹합니다.

| 마커 | 의미 |
| --- | --- |
| `[VERIFIED]` | 법령 존재 확인 |
| `[HALLUCINATION_DETECTED]` | 존재하지 않는 법령 (AI 환각) |
| `[SKIPPED]` | OC 인증키 없어 검증 생략 |
| `[ERROR]` | 검증 중 오류 발생 |

---

## 빠른 사용 (CLI)

```bash
# API 카탈로그 탐색
law-openapi-cli catalog --search 법령해석
law-openapi-cli doc cgmExpcMolegListGuide
law-openapi-cli inspect-api cgmExpcMolegListGuide --view detail --json

# URL 빌드 및 호출
law-openapi-cli build-url cgmExpcMolegListGuide --param query=퇴직 --param display=5
law-openapi-cli call cgmExpcMolegListGuide --param query=퇴직 --param display=5

# 법령 검색
law-openapi-cli search-law 자동차관리법
law-openapi-cli get-law --id 000744 --type JSON

# 법제처 법령해석
law-openapi-cli search-moleg 퇴직
law-openapi-cli get-moleg --id 12345

# 환경 점검 및 예시
law-openapi-cli doctor
law-openapi-cli examples
```

---

## MCP 서버 실행

```bash
law-openapi-mcp --transport stdio
law-openapi-mcp --transport streamable-http   # http://localhost:8000/mcp
```

### Claude Desktop 설정

```json
{
  "mcpServers": {
    "law-api-mcp-korea": {
      "command": "law-openapi-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "LAW_API_OC": "your_oc_value"
      }
    }
  }
}
```

---

## 제공 인터페이스

### CLI 서브커맨드

| 서브커맨드 | alias | 설명 |
| --- | --- | --- |
| `catalog` | `search-api`, `find-api` | API 카탈로그 탐색 |
| `doc` | `inspect-api`, `api-doc` | API 문서 조회 |
| `build-url` | `url` | 요청 URL 생성 |
| `call` | `request`, `invoke` | API 호출 |
| `search-law` | `law-search` | 법령 검색 |
| `get-law` | `law` | 법령 본문 조회 |
| `search-moleg` | `interpret-search` | 법제처 법령해석 검색 |
| `get-moleg` | `interpret` | 법령해석 본문 조회 |
| `tool-catalog` | `tools` | Generated tool 목록 |
| `tool-doc` | `tool-help` | Generated tool 문서 |
| `tool` | `run-tool` | Generated tool 실행 |
| `auth` | `login` | OC 인증키 설정 |
| `doctor` | — | 환경 설정 점검 |
| `examples` | — | 자주 쓰는 예시 출력 |
| `mcp` | — | MCP 서버 실행 |

### MCP Resources

- `lawdoc://catalog`
- `lawdoc://manifest`
- `lawdoc://verification`
- `lawdoc://api/{api_name}`

### MCP Tools

| 도구 | 설명 |
| --- | --- |
| `list_apis` | API 카탈로그 탐색 (view: `summary`\|`detail`) |
| `get_api_doc` | 특정 API 문서 조회 (view: `summary`\|`detail`, markdown opt-in) |
| `build_request_url` | 요청 URL 생성 |
| `call_api` | API 직접 호출 |
| `search_current_law` | 법령 검색 (약어 자동 해석) |
| `get_current_law` | 법령 본문 조회 |
| `search_moleg_interpretations` | 법제처 법령해석 검색 |
| `get_moleg_interpretation` | 법령해석 본문 조회 |
| `search_decisions` | 판례·결정례 통합 검색 (9개 도메인, 약어 지원) |
| `get_decision_text` | 판례·결정례 본문 조회 |
| `verify_citations` | AI 법률 텍스트 법령 인용 검증 |

---

## 테스트

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
```

`LAW_API_OC`가 없으면 실 API smoke 테스트는 자동으로 skip됩니다. `.env` 파일이 있거나 환경변수가 설정되면 live smoke도 함께 실행됩니다.

---

## 프로젝트 구성

```
api/docs/                       # 원본 API 문서 정본 (Markdown)
src/law_api_mcp_korea/
  api_docs/                     # 런타임 flat 문서 + 카탈로그 메타데이터
  aliases.py                    # 법령 약어 사전 + NOT_FOUND 마커
  decisions.py                  # 판례·결정례 도메인 매핑
  citations.py                  # 법령 인용 파서 + 검증 마커
  mcp_server.py                 # FastMCP 서버 (11개 도구)
  client.py                     # MOLEG API 클라이언트
tools/sync_api_docs.py          # api/docs/ → api_docs/ 동기화
```

원본 문서 수정 후 반드시 동기화를 실행합니다:

```bash
python tools/sync_api_docs.py
```

---

## API 제약/예외

- **법령 연혁 본문 조회**: `target=lsHistory` + `HTML` 전용. `JSON/XML`은 안정적 구조 응답 미보장.
- **감사원 사전컨설팅 의견서** (`baiPvcs`): 목록/본문 모두 `invalid_api_key` 오류로 처리됨.
- **live sweep 기준**: 내부 API 총수 `191`, `invalid_api_key` `2`건 고정.

---

## 릴리스 절차

```bash
uv run python -m unittest discover -s tests -p "test_*.py"
python -m build --sdist --wheel
```

- clean venv에서 wheel 설치 후 smoke 실행
- GitHub Release 생성 → `dist/*.whl`, `dist/*.tar.gz` 첨부

```bash
pip install law_api_mcp_korea-0.1.0-py3-none-any.whl
law-openapi-cli catalog --search 법령해석
law-openapi-cli get-law --id 001571 --type JSON --with-sub-articles
law-openapi-mcp --transport stdio
```
