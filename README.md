# law-api-mcp-korea

법제처 국가법령정보 공동활용 OPEN API 문서를 정본으로 유지하면서, 그 문서를 기반으로 동작하는
reference-compatible **CLI + MCP 서버**를 제공하는 Python 패키지입니다.

## 설치

PyPI에서 설치:

```bash
pip install law-api-mcp-korea
```

로컬 개발 버전 설치:

```bash
pip install -e .
```

## 구성

- `api/docs/`: 사람이 읽는 원본 문서 정본
- `src/law_api_mcp_korea/api_docs/`: 런타임에서 사용하는 flat 문서와 카탈로그 메타데이터
- `tools/sync_api_docs.py`: `api/docs/**`를 packaged `api_docs/`로 동기화하는 스크립트
- `law-openapi-cli`: 문서 검색, URL 생성, API 호출용 CLI
- `law-openapi-mcp`: stdio / streamable-http MCP 서버

## 전제

법제처 OPEN API는 요청 파라미터 `OC`(사용자 이메일 ID)를 요구합니다.
기본적으로 `LAW_API_OC` 환경변수 또는 루트 `.env` 파일에서 해당 값을 읽습니다.

```bash
export LAW_API_OC=your_oc_value
```

또는:

```bash
echo LAW_API_OC=your_oc_value > .env
```

`.env`는 로컬 실행용으로만 사용하고 저장소에는 커밋하지 않습니다.

추가 환경변수:

- `LAW_API_TIMEOUT`: 요청 타임아웃(초), 기본값 `30`
- `LAW_API_FORCE_HTTPS`: `true`/`1`이면 `http://` 엔드포인트를 `https://`로 강제 변환

테스트에 MCP stdio E2E를 포함하려면 `mcp` 패키지가 설치되어 있어야 합니다. 위 명령으로 함께 설치됩니다.

## 문서 동기화

원본 문서를 수정했으면 packaged 문서를 다시 생성해야 합니다.

```bash
python tools/sync_api_docs.py
```

이 스크립트는 다음을 수행합니다.

- `api/docs/**`의 중첩 문서를 flat 파일명으로 역매핑
- `src/law_api_mcp_korea/api_docs/*.md`로 복사
- `catalog.json`의 191개 `filename` 집합과 정확히 일치하는지 검증

## 빠른 사용

```bash
law-openapi-cli catalog --search 법령해석
law-openapi-cli doc cgmExpcMolegListGuide
law-openapi-cli build-url cgmExpcMolegListGuide --param query=퇴직 --param display=5
law-openapi-cli call cgmExpcMolegListGuide --param query=퇴직 --param display=5
law-openapi-cli search-law 자동차관리법
law-openapi-cli get-law --id 000744
law-openapi-cli search-moleg 퇴직
law-openapi-cli get-moleg --id 12345
```

## 테스트

기본 테스트는 오프라인으로 동작하며, `LAW_API_OC`가 없으면 실 API smoke 테스트는 자동으로 skip 됩니다.

```bash
python -m unittest discover -s tests -p "test_*.py"
```

실 API smoke까지 포함하려면 환경변수만 설정한 뒤 같은 명령을 다시 실행하면 됩니다.

```bash
export LAW_API_OC=your_oc_value
python -m unittest discover -s tests -p "test_*.py"
```

`.env` 파일이 있으면 같은 테스트 명령으로 live smoke가 자동 활성화됩니다.

## MCP 서버 실행

```bash
law-openapi-mcp --transport stdio
law-openapi-mcp --transport streamable-http
```

`streamable-http` 사용 시 일반적으로 `http://localhost:8000/mcp` 로 연결하면 됩니다.

설치된 패키지는 아래 콘솔 엔트리포인트를 제공합니다.

- `law-openapi-cli`
- `law-openapi-mcp`

## Claude Desktop 예시 설정

```json
{
  "mcpServers": {
    "law-api-mcp-korea": {
      "command": "law-openapi-mcp",
      "args": [
        "--transport",
        "stdio"
      ],
      "env": {
        "LAW_API_OC": "your_oc_value"
      }
    }
  }
}
```

## 제공 인터페이스

CLI 서브커맨드:

- `catalog`
- `doc`
- `build-url`
- `call`
- `search-law`
- `get-law`
- `search-moleg`
- `get-moleg`
- `mcp`

MCP resources:

- `lawdoc://catalog`
- `lawdoc://manifest`
- `lawdoc://verification`
- `lawdoc://api/{api_name}`

MCP tools:

- `list_apis`
- `get_api_doc`
- `build_request_url`
- `call_api`
- `search_current_law`
- `get_current_law`
- `search_moleg_interpretations`
- `get_moleg_interpretation`
