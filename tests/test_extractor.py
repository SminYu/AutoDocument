from autodocument.extractor import _extract_json_object, extract_fields_hybrid


def test_extract_json_object_from_fenced_text():
    text = """결과입니다\n```json\n{\"merchant_name\":\"가게\",\"total_amount\":11000}\n```"""
    parsed = _extract_json_object(text)
    assert parsed == {"merchant_name": "가게", "total_amount": 11000}


def test_hybrid_falls_back_to_rule_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ocr_text = "상호명\n사업자번호 123-45-67890\n합계 11,000\n공급가액 10,000\n부가세 1,000"
    fields, mode = extract_fields_hybrid(ocr_text, mode="llm_hybrid")

    assert mode == "rule_fallback"
    assert fields["total_amount"] == 11000
    assert fields["reasons"]["extractor"] == "llm_unavailable_or_failed"
