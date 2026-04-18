# 지능형 법령검색 시스템 검색 API 조회

## 1. API 명칭 및 기본 설명
- **API 명칭**: 지능형 법령검색 시스템 검색 API 조회
- **기본 설명**: 지능형 법령검색 시스템 검색 API

## 2. 가이드 페이지 URL
- https://open.law.go.kr/LSO/openApi/guideResult.do?htmlName=aiSearchGuide

## 3. 요청 URL (Endpoint)
- https://www.law.go.kr/DRF/lawSearch.do?target=aiSearch

## 4. 요청 변수 (Request Parameters) 명세표
| 변수명 | 타입/필수 여부 | 설명 |
| --- | --- | --- |
| OC | string(필수) | 신청한 API인증값 |
| target | string(필수) | 서비스 대상 (지능형 법령검색 시스템 검색 API : aiSearch) |
| type | char(필수) | 출력 형태 : XML/JSON |
| search | int | 검색범위 법령분류 (0:법령조문, 1:법령 별표·서식, 2:행정규칙 조문, 3:행정규칙 별표·서식) |
| query | string | 법령명에서 검색을 원하는 질의 (정확한 검색을 위한 문자열 검색 query="뺑소니") |
| display | int | 검색된 결과 개수 (default=20) |
| page | int | 검색 결과 페이지 (default=1) |

## 5. 출력 결과 (Response Elements) 명세표
| 필드명 | 타입 | 설명 |
| --- | --- | --- |
| target | string | 검색서비스 대상 |
| 키워드 | string | 검색 단어 |
| 검색결과개수 | int | 검색 건수 |
| 법령조문ID | int | 법령조문 ID |
| 법령ID | string | 법령ID |
| 법령일련번호 | string | 법령일련번호 |
| 법령명 | string | 법령명 |
| 시행일자 | string | 법령 시행일자 |
| 공포일자 | string | 법령 공포일자 |
| 공포번호 | string | 법령 공포번호 |
| 소관부처코드 | string | 소관부처코드 |
| 소관부처명 | string | 소관부처명 |
| 법령종류명 | string | 법령종류명 |
| 제개정구분명 | string | 법령 제개정구분명 |
| 법령편장절관코드 | string | 법령편장절관코드 |
| 조문일련번호 | string | 법령 조문일련번호 |
| 조문번호 | string | 법령 조문번호 |
| 조문가지번호 | string | 법령 조문가지번호 |
| 조문제목 | string | 법령 조문제목 |
| 조문내용 | string | 법령 조문내용 |
| 법령별표서식 ID | int | 법령별표서식 ID |
| 별표서식 일련번호 | string | 법령 별표서식일련번호 |
| 별표서식번호 | string | 법령 별표서식번호 |
| 별표서식 가지번호 | string | 법령 별표서식가지번호 |
| 별표서식제목 | string | 법령 별표서식제목 |
| 별표서식 구분코드 | string | 법령 별표서식구분코드 |
| 별표서식 구분명 | string | 법령 별표서식구분명 |
| 행정규칙조문 ID | int | 행정규칙조문 ID |
| 행정규칙 일련번호 | string | 행정규칙일련번호 |
| 행정규칙ID | string | 행정규칙ID |
| 행정규칙명 | string | 행정규칙명 |
| 발령일자 | string | 발령일자 |
| 발령번호 | string | 발령번호 |
| 시행일자 | string | 시행일자 |
| 발령기관명 | string | 발령기관명 |
| 행정규칙 종류명 | string | 행정규칙종류명 |
| 제개정구분명 | string | 행정규칙 제개정구분명 |
| 조문일련번호 | string | 행정규칙 조문일련번호 |
| 조문번호 | string | 행정규칙 조문번호 |
| 조문가지번호 | string | 행정규칙 조문가지번호 |
| 조문제목 | string | 행정규칙 조문제목 |
| 조문내용 | string | 행정규칙 조문내용 |
| 행정규칙 별표서식ID | int | 행정규칙별표서식 ID |
| 별표서식 일련번호 | string | 행정규칙 별표서식일련번호 |
| 별표서식번호 | string | 행정규칙 별표서식번호 |
| 별표서식 가지번호 | string | 행정규칙 별표서식가지번호 |
| 별표서식제목 | string | 행정규칙 별표서식제목 |
| 별표서식 구분코드 | string | 행정규칙 별표서식구분코드 |
| 별표서식 구분명 | string | 행정규칙 별표서식구분명 |

## 6. 에러 코드
- 가이드 페이지에 별도 에러 코드 표는 명시되지 않은 경우가 많습니다. 일반적으로 HTTP 오류, 빈 결과, 또는 XML/JSON 응답의 상태값(제공 시)으로 실패를 판별합니다.

## 7. 비고
- 법령정보지식베이스 API군은 target별 관계 유형만 달라지고 기본 요청/응답 구조는 유사합니다.

## 샘플 요청 및 응답 예시
- 아래 예시는 호출 형태를 빠르게 확인하기 위한 템플릿입니다.

#### 요청 예시
- 예시 1 (XML)
```text
https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=aiSearch&type=XML&search=0&query=뺑소니
```
- 예시 2 (JSON)
```text
https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=aiSearch&type=JSON&search=0&query=뺑소니
```

#### 응답 예시
- XML 구조 예시
```xml
<response>
  <item>
    <field name="target">예시값</field>
    <field name="키워드">자동차관리법</field>
    <field name="검색결과개수">20</field>
    <field name="page">1</field>
    <field name="명칭">자동차관리법</field>
    <field name="상세링크">https://www.law.go.kr/...</field>
  </item>
</response>
```
- JSON 구조 예시
```json
{
  "data": [
    {
      "target": "예시값",
      "키워드": "자동차관리법",
      "검색결과개수": 20,
      "page": 1,
      "명칭": "자동차관리법",
      "상세링크": "https://www.law.go.kr/..."
    }
  ]
}
```

## 8. 메타
- 정리 기준: 국가법령정보 공동활용 OPEN API 활용가이드 구조화 요약
- 근거 수준: pattern
