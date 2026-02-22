# AutoDocument

휴대폰 촬영 증빙 서류(영수증/카드매출전표)를 자동으로 처리하는 파이프라인 구현입니다.

## 실행
```bash
python run_pipeline.py --input /path/to/receipt.jpg --output ./artifacts --template /path/to/template.docx
```

## 처리 순서
1. 전처리(OpenCV): 경계 검출, 투시 보정, deskew, 이진화, 업스케일
2. OCR(pytesseract): 전처리 변형본 다중 OCR
3. 필드 추출/정규화: 정규식 기반 후보 추출 및 정규화
4. 검증: `total = supply + vat`, 사업자번호 checksum
5. 양식 채우기: DOCX/HWPX/TXT 템플릿 플레이스홀더 치환
6. 산출: 채워진 증빙파일 + result JSON + OCR raw/log

## 플레이스홀더
- `{{merchant_name}}`
- `{{business_number}}`
- `{{approved_at}}`
- `{{supply_amount}}`
- `{{vat_amount}}`
- `{{total_amount}}`
- `{{approval_no}}`
