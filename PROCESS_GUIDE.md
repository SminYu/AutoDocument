# 모바일 촬영 증빙서류 자동 인식·작성 파이프라인 제안

아래는 제시하신 흐름을 기반으로 **실무 운영**에 맞게 보완한 권장 순서입니다.

## 0) 입력 수집 (신규 추가)
- 입력 채널: 모바일 업로드(사진), 스캔 PDF, 메신저 첨부.
- 필수 메타데이터: 촬영 시각, 사용자 ID, 원본 파일 해시(SHA-256), 업로드 경로.
- 원본 보존: 원본 이미지는 수정 없이 별도 보관(감사 추적용).

---

## 1) OpenCV 전처리 (기존 단계 보강)
- 자동 문서 경계 검출 + 투시 보정(사다리꼴 → 직사각형).
- 회전/기울기 보정(±90/180, 미세각 deskew).
- 조명 균일화(CLAHE, adaptive threshold), 노이즈 제거(bilateral/median).
- 작은 글자 OCR을 위해 해상도 업샘플(필요 시 2x).
- 다중 변환 결과 생성(원본/흑백/강조본) → OCR 앙상블 입력.

---

## 2) OCR 엔진 (한국어 영수증 특화)
- 1차 OCR: 한국어 강점 엔진(예: CLOVA OCR, Google Document AI, PaddleOCR-KR 튜닝).
- 2차 OCR(보조): Tesseract/다른 엔진으로 재시도하여 교차 검증.
- 출력 표준화:
  - line 단위 텍스트
  - token bbox(좌표)
  - confidence
  - 페이지/블록 구조

> 운영 팁: 영수증은 폰트가 작고 배경 노이즈가 많아 단일 엔진보다 "전처리 다변화 + 다중 OCR"이 인식률을 안정화합니다.

---

## 3) 필드 추출/정규화 (룰 + LLM 하이브리드)
- **룰 기반 후보 추출**
  - 키워드 사전: `공급가액`, `부가세`, `합계`, `승인번호`, `가맹점`, `사업자번호` 등
  - 정규식: 날짜, 사업자번호(###-##-#####), 금액(천단위 콤마 포함)
  - 레이아웃 힌트: 합계/부가세는 하단 영역에 자주 위치
- **LLM/SLM 확정 단계**
  - 입력: OCR 텍스트 + 후보 필드 + confidence
  - 출력: 강제 JSON Schema 준수
  - 필수 정책: 미확실하면 `null` + `reason` 기록 (추측 금지)
- 정규화:
  - 날짜 `YYYY-MM-DD`
  - 금액 정수(원 단위)
  - 사업자번호 하이픈 형식 통일

---

## 4) 회계/업무 규칙 검증 (기존 단계 확장)
- 수식 검증: `total == supply + vat`
- 허용 오차: 카드 영수증 반올림/봉사료 케이스 대응(규칙 테이블화)
- 카드 승인 패턴 검증: 승인번호 자리수, 카드사 코드 포맷
- 사업자번호 checksum 검증
- 결과 상태:
  - `PASS`: 자동 확정
  - `REVIEW`: 사람이 확인 후 승인
  - `FAIL`: 재처리/재촬영 요청

---

## 5) 양식 채우기 (HWPX/HWP/DOCX)
- 권장 우선순위: **DOCX 템플릿 > HWPX 직접편집 > HWP 자동화**
  - DOCX: 파이썬 라이브러리/서버 환경에서 자동화 용이
  - HWPX: XML 구조 직접 수정 가능(정확한 스키마 대응 필요)
  - HWP: 윈도우/한컴 설치 및 COM Automation 의존성 고려
- 템플릿 설계 규칙:
  - 플레이스홀더 명시: `{{merchant_name}}`, `{{approved_at}}`, `{{total_amount}}`
  - 필수값 누락 시 빨간 마킹/리뷰 플래그

---

## 6) 결과물/감사추적 (기존 단계 구체화)
최종 산출물 3종:
1. 채워진 증빙 문서 파일(`.docx`/`.hwpx`/`.hwp`)
2. 구조화 JSON(원문/OCR/정규화/검증 상태 포함)
3. 감사 로그(누가, 언제, 어떤 모델·버전·규칙으로 처리했는지)

권장 추가:
- 처리 단계별 confidence 및 변경 이력(versioned JSON)
- 원본 이미지와 결과를 연결하는 hash chain

---

## 운영 아키텍처 권장안
- 비동기 파이프라인: 업로드 → 작업큐(Celery/RQ/Kafka) → 단계별 워커
- 재시도 전략: OCR 실패 시 다른 전처리 버전 자동 재실행
- 휴먼 인더루프(HITL): REVIEW 건만 검수 UI로 전달
- 모델/룰 버전 관리: `ocr_engine_version`, `extractor_version`, `rule_set_version`

---

## 최소 JSON 스키마 예시
```json
{
  "document_id": "uuid",
  "source": {
    "file_name": "receipt_001.jpg",
    "sha256": "...",
    "uploaded_at": "2026-02-22T10:00:00Z"
  },
  "extracted": {
    "merchant_name": "상호명",
    "business_number": "123-45-67890",
    "approved_at": "2026-02-21",
    "supply_amount": 10000,
    "vat_amount": 1000,
    "total_amount": 11000,
    "approval_no": "12345678"
  },
  "validation": {
    "status": "PASS",
    "checks": [
      {"name": "total_formula", "result": true},
      {"name": "business_number_checksum", "result": true}
    ]
  },
  "audit": {
    "ocr_engine": "clova-ocr-v3",
    "llm_model": "local-slm-8b",
    "rule_set_version": "2026.02"
  }
}
```

---

## 제안 결론
기존 프로세스는 방향이 매우 좋습니다. 다만 실제 정확도와 운영 안정성을 위해 아래 3가지는 반드시 추가하는 것이 좋습니다.
1. **입력 수집/원본 보존 단계(0단계)**
2. **룰+LLM 하이브리드 + JSON Schema 강제**
3. **검증 결과의 상태화(PASS/REVIEW/FAIL) 및 감사추적 강화**

이 구조로 시작하면 PoC 이후에도 확장(세금계산서, 거래명세서 등)이 쉽습니다.
