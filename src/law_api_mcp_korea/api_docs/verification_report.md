# 샘플 추가본 검증 리포트

## 공식 가이드 최종 검증
- 검증일: **2026-04-04**
- 기준 페이지: [guideList.do](https://open.law.go.kr/LSO/openApi/guideList.do)
- `guideList.do` 화면 표시 건수: **191**
- `guideList.do` 실제 `openApiGuide('...')` 링크 수: **195**
- 내부 `catalog.json` API 수: **191**
- source docs vs 공식 sample URL mismatch: **0**
- runtime URL vs 공식 sample URL semantic mismatch: **0**
- runtime build error: **0**
- 문자열-only 차이: **618**
- 결론: **공식 상세 가이드 기준 정합성 확보 완료**

### 카운트 해석
- `191`: 공식 사이트 UI에 표시되는 집계값
- `195`: 공식 페이지 HTML에 존재하는 실제 상세 가이드 링크 수
- `191 internal APIs`: 저장소가 grouped API를 유지하는 내부 카탈로그 수
- 문자열-only 차이는 query 순서, percent-encoding, `http/https`, `www` 표기 차이만 포함하며 GAP로 보지 않습니다.

- 기준 마크다운 파일 수: **191**
- 실제 마크다운 파일 수: **191**
- 빈 파일 수: **0**
- 샘플 섹션 누락 파일 수: **0**
- 요청 변수 표 포맷 이상 파일 수: **0**
- 출력 결과 표 포맷 이상 파일 수: **0**

## 샘플 응답 포맷 포함 현황
- XML 예시 포함: **189**
- JSON 예시 포함: **187**
- HTML 예시 포함: **2**

## 무작위 3개 샘플 점검
- `법령_체계도_목록_조회.md`: 요청표=True, 응답표=True, 샘플섹션=True, 요청예시블록=1, 응답예시블록=1
- `농림축산식품부_법령해석_목록_조회.md`: 요청표=True, 응답표=True, 샘플섹션=True, 요청예시블록=1, 응답예시블록=1
- `노동위원회_결정문_목록_조회.md`: 요청표=True, 응답표=True, 샘플섹션=True, 요청예시블록=1, 응답예시블록=1

## 메모
- 샘플 요청 URL은 문서화용 예시입니다.
- `{...}` 형태의 식별자 값은 실제 조회 대상 식별값으로 치환해야 합니다.
- 일부 HTML 전용 API는 HTML 구조 예시만 포함했습니다.
- 공정거래위원회·국민권익위원회·개인정보보호위원회 묶음 가이드는 공식 가이드의 형식에 맞춰 HTML/XML 예시로 정리했습니다.
