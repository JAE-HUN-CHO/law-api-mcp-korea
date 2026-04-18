# Live API Contract Validation

## Summary
- total: **191**
- direct_ok: **189**
- recovered_ok: **0**
- invalid_api_key: **2**
- unresolved: **0**
- request_contract_ok: **189**
- response_documented_ok: **178**
- response_coverage_complete: **125**
- response_field_validation_skipped: **11**
- apis_with_request_doc_gaps: **0**
- apis_with_response_doc_gaps: **0**
- apis_with_unobserved_documented_fields: **53**
- structured_apis_without_response_fields: **0**

## Findings
- request issues: none
- observed response fields outside docs: none
- sampled payload did not exercise documented fields: `현행법령(시행일) 목록 조회` -> ['공동부령구분']
- sampled payload did not exercise documented fields: `현행법령(시행일) 본문 조회` -> ['개정문내용', '공동부령구분', '구분코드', '법종구분', '별표HWP 파일명', '별표PDF 파일명', '별표가지번호', '별표구분', '별표내용', '별표번호']
- sampled payload did not exercise documented fields: `현행법령(공포일) 목록 조회` -> ['공동부령구분']
- sampled payload did not exercise documented fields: `현행법령(공포일) 본문 조회` -> ['개정문내용', '공동부령구분', '구분코드', '목내용', '목번호', '법종구분', '별표HWP 파일명', '별표PDF 파일명', '별표가지번호', '별표구분']
- sampled payload did not exercise documented fields: `현행법령(시행일) 본문 조항호목 조회` -> ['법종구분', '별표시행일자문자열', '소관부처', '의결구분', '이전법령명', '적용시작일자', '적용종료일자', '제안구분']
- sampled payload did not exercise documented fields: `현행법령(공포일) 본문 조항호목 조회` -> ['법종구분명', '별표시행일자문자열', '소관부처', '의결구분', '이전법령명', '제안구분', '조문시행일자문자열']
- sampled payload did not exercise documented fields: `법령 변경이력 목록 조회` -> ['page']
- sampled payload did not exercise documented fields: `일자별 조문 개정 이력 목록 조회` -> ['조문정보']
- sampled payload did not exercise documented fields: `법령 기준 자치법규 연계 관련 목록 조회` -> ['키워드']
- sampled payload did not exercise documented fields: `법령 체계도 본문 조회` -> ['기본정보', '법률', '법종구분', '상하위법', '시행규칙', '시행령', '제개정구분']
- sampled payload did not exercise documented fields: `신구법 목록 조회` -> ['현행연혁구분']
- sampled payload did not exercise documented fields: `신구법 본문 조회` -> ['구조문_ 기본정보', '구조문목록', '신구법 존재여부', '신조문_ 기본정보', '신조문목록', '조문', '조문']
- sampled payload did not exercise documented fields: `3단 비교 본문 조회` -> ['관련삼단비교목록', '기본정보', '목록명', '법령요약정보', '법률조문', '삼단비교 목록상세링크', '삼단비교기준', '시행규칙 요약정보', '시행규칙 조문목록', '시행규칙ID']
- sampled payload did not exercise documented fields: `행정규칙 목록 조회` -> ['키워드']
- sampled payload did not exercise documented fields: `행정규칙 본문 조회` -> ['별표', '별표내용', '별표서식PDF파일링크', '부칙', '부칙공포번호', '부칙공포일자', '부칙내용', '상위부처명', '첨부파일']
- sampled payload did not exercise documented fields: `행정규칙 신구법 비교 목록 조회` -> ['현행연혁구분']
- sampled payload did not exercise documented fields: `행정규칙 신구법 비교 본문 조회` -> ['구조문_ 기본정보', '구조문목록', '신구법 존재여부', '신조문_ 기본정보', '신조문목록', '조문', '조문']
- sampled payload did not exercise documented fields: `자치법규 본문 조회` -> ['개정문내용', '별표', '별표가지번호', '별표구분', '별표내용', '별표번호', '별표제목', '별표첨부파일명', '조문번호']
- sampled payload did not exercise documented fields: `판례 목록 조회` -> ['공포번호']
- sampled payload did not exercise documented fields: `위원회 결정문 본문 조회 (공정거래위원회·국민권익위원회·개인정보보호위원회)` -> ['각주내용', '각주번호']
- structured APIs without response field docs: none
