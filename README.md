# AutoDocument

휴대폰 촬영 증빙 서류(영수증/카드매출전표)를 자동으로 처리하는 파이프라인 구현입니다.

## 실행
```bash
python run_pipeline.py --input /path/to/receipt.jpg --output ./artifacts --template /path/to/template.docx --extraction-mode llm_hybrid
```

## 처리 순서
1. 전처리(OpenCV): 경계 검출, 투시 보정, deskew, 이진화, 업스케일
2. OCR(pytesseract): 전처리 변형본 다중 OCR
3. 필드 추출/정규화: **AI 기반(LLM) + rule-based 하이브리드**
4. 검증: `total = supply + vat`, 사업자번호 checksum
5. 양식 채우기: DOCX/HWPX/TXT 템플릿 플레이스홀더 치환
6. 산출: 채워진 증빙파일 + result JSON + OCR raw/log

## AI 추출 모드
- `llm_hybrid`(기본): rule 기반 후보를 먼저 만들고 LLM으로 필드 확정
- `rule_only`: LLM 없이 rule만 사용

환경변수:
- `OPENAI_API_KEY` (LLM 추출 활성화)
- `OPENAI_MODEL` (기본: `gpt-4o-mini`)
- `OPENAI_API_BASE` (기본: `https://api.openai.com/v1`)

`OPENAI_API_KEY`가 없거나 호출이 실패하면 자동으로 `rule_fallback`으로 동작하며 `result.json.audit.extraction_mode`에 기록됩니다.

## 플레이스홀더
- `{{merchant_name}}`
- `{{business_number}}`
- `{{approved_at}}`
- `{{supply_amount}}`
- `{{vat_amount}}`
- `{{total_amount}}`
- `{{approval_no}}`
