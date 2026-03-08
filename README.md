# law-api-mcp-korea

법제처 국가법령정보 공동활용 OPEN API 문서를 정본으로 유지하면서, 그 문서를 기반으로 동작하는
reference-compatible **CLI + MCP 서버**를 제공하는 Python 패키지입니다.

공식 공개 배포 채널은 **GitHub Releases only** 입니다. PyPI는 지원하지 않습니다.

## 설치

공개 배포용 설치:

```bash
pip install <downloaded-wheel-file>
```

wheel 파일은 [GitHub Releases](https://github.com/JAE-HUN-CHO/law-api-mcp-korea/releases)에서 내려받습니다.

예:

```bash
pip install law_api_mcp_korea-0.1.0-py3-none-any.whl
```

로컬 개발용 설치:

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

## 공개 배포 기준

- 공개 사용자는 GitHub Release asset의 `.whl` 또는 `.tar.gz`를 설치합니다.
- PyPI 업로드는 하지 않습니다.
- 외부 MCP 사용자는 wheel 설치 후 `law-openapi-mcp --transport stdio`로 서버를 실행합니다.

## 응답 크기와 lazy loading

- packaged metadata는 `catalog_index.json` + `api_meta/<guide_html_name>.json` + 개별 markdown으로 분리됩니다.
- `MCP`는 문서/카탈로그 계열에서 summary를 기본값으로 사용합니다.
- `CLI`는 기존 기본 UX를 유지합니다.
  - `doc` 기본: markdown
  - `catalog --json` 기본: detail
- 실제 API 호출 결과(`call_api`, `search_current_law`, `get_current_law`, generated tool 실행)는 MCP/CLI 모두 full payload 기본값을 유지합니다.

## API 제약/예외

- `법령 연혁 본문 조회`
  - 현재 패키지에서는 `target=lsHistory` + `HTML` 전용으로 취급합니다.
  - `JSON/XML`은 안정적인 구조 응답으로 간주하지 않습니다.
- `감사원 사전컨설팅 의견서`(`baiPvcs`)
  - 목록/본문 조회는 현재 패키지 표면에서 `유효한 API key가 아닙니다` 스타일 오류로 표준화됩니다.
  - live sweep 기준으로도 이 두 건은 `invalid_api_key`로 집계합니다.
- 현재 live sweep 기대값:
  - `191 = 108 direct_ok + 81 recovered_ok + 2 invalid_api_key + 0 unresolved`

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

## 릴리스 절차

수동 GitHub Release 기준 체크리스트:

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m build --sdist --wheel
```

그 다음:

- clean venv에서 wheel 설치 smoke 실행
- GitHub Release 생성
- `dist/*.whl`, `dist/*.tar.gz` 첨부

clean venv smoke 예:

```bash
pip install law_api_mcp_korea-0.1.0-py3-none-any.whl
law-openapi-cli catalog --search 법령해석
law-openapi-cli get-law --id 001571 --type JSON --with-sub-articles
law-openapi-mcp --transport stdio
```

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

사전 단계: GitHub Release에서 wheel을 설치한 뒤 아래처럼 MCP 서버를 등록합니다.

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

MCP 문서/리소스 기본 view:

- `list_apis`: `summary` 기본
- `get_api_doc`: `summary` 기본, markdown은 opt-in
- `lawdoc://catalog`: summary 기본
- `lawdoc://api/{api_name}`: summary 기본
- raw/detail가 필요하면 별도 resource/view를 사용합니다.
