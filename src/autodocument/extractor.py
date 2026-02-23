from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .utils import normalize_date, to_int_amount

LOGGER = logging.getLogger("autodocument.extractor")


def _normalize_business_number(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    if len(digits) != 10:
        return None
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


def _extract_json_object(text: str) -> dict[str, Any] | None:
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    payload = candidate[start : end + 1]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def rule_extract_fields(ocr_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "merchant_name": None,
        "business_number": None,
        "approved_at": None,
        "supply_amount": None,
        "vat_amount": None,
        "total_amount": None,
        "approval_no": None,
        "reasons": {},
    }

    bn = re.search(r"(\d{3}-\d{2}-\d{5}|\d{10})", ocr_text)
    if bn:
        result["business_number"] = _normalize_business_number(bn.group(1))

    date_match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}|20\d{6})", ocr_text)
    if date_match:
        result["approved_at"] = normalize_date(date_match.group(1))

    total = re.search(r"(?:합계|총액|Total)\s*[: ]?\s*([\d,]+)", ocr_text, re.IGNORECASE)
    supply = re.search(r"(?:공급가액|공급가)\s*[: ]?\s*([\d,]+)", ocr_text, re.IGNORECASE)
    vat = re.search(r"(?:부가세|VAT)\s*[: ]?\s*([\d,]+)", ocr_text, re.IGNORECASE)

    if total:
        result["total_amount"] = to_int_amount(total.group(1))
    if supply:
        result["supply_amount"] = to_int_amount(supply.group(1))
    if vat:
        result["vat_amount"] = to_int_amount(vat.group(1))

    app_no = re.search(r"(?:승인번호|Approval\s*No)\s*[: ]?\s*([A-Z0-9-]{6,})", ocr_text, re.IGNORECASE)
    if app_no:
        result["approval_no"] = app_no.group(1)

    first_line = next((line.strip() for line in ocr_text.splitlines() if line.strip()), None)
    result["merchant_name"] = first_line

    for key in [
        "merchant_name",
        "business_number",
        "approved_at",
        "supply_amount",
        "vat_amount",
        "total_amount",
        "approval_no",
    ]:
        if result.get(key) is None:
            result["reasons"][key] = "not_found_by_rules"

    return result


def _llm_extract_fields(ocr_text: str, rule_fields: dict[str, Any]) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    endpoint = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/chat/completions"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    schema_hint = {
        "merchant_name": "string|null",
        "business_number": "###-##-#####|null",
        "approved_at": "YYYY-MM-DD|null",
        "supply_amount": "integer|null",
        "vat_amount": "integer|null",
        "total_amount": "integer|null",
        "approval_no": "string|null",
        "reasons": {"field_name": "reason_when_null"},
    }

    prompt = (
        "다음 OCR 텍스트에서 증빙 필드를 추출하세요. "
        "불확실하면 반드시 null과 reasons를 사용하세요. "
        "출력은 오직 JSON 객체만 반환하세요.\n"
        f"스키마: {json.dumps(schema_hint, ensure_ascii=False)}\n"
        f"rule_based_candidates: {json.dumps(rule_fields, ensure_ascii=False)}\n"
        f"ocr_text:\n{ocr_text}"
    )

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You extract receipt fields and return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("LLM extraction request failed: %s", exc)
        return None

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None

    return _extract_json_object(content)


def _normalize_extracted_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    normalized["business_number"] = _normalize_business_number(data.get("business_number"))

    if data.get("approved_at"):
        normalized["approved_at"] = normalize_date(str(data["approved_at"]))

    for key in ("supply_amount", "vat_amount", "total_amount"):
        value = data.get(key)
        if isinstance(value, int):
            normalized[key] = value
        elif value is None:
            normalized[key] = None
        else:
            normalized[key] = to_int_amount(str(value))

    approval_no = data.get("approval_no")
    normalized["approval_no"] = str(approval_no).strip() if approval_no else None
    merchant_name = data.get("merchant_name")
    normalized["merchant_name"] = str(merchant_name).strip() if merchant_name else None

    reasons = data.get("reasons")
    normalized["reasons"] = reasons if isinstance(reasons, dict) else {}
    return normalized


def extract_fields_hybrid(ocr_text: str, mode: str = "llm_hybrid") -> tuple[dict[str, Any], str]:
    rule_fields = rule_extract_fields(ocr_text)

    if mode == "rule_only":
        return rule_fields, "rule_only"

    llm_fields = _llm_extract_fields(ocr_text, rule_fields)
    if not llm_fields:
        rule_fields["reasons"]["extractor"] = "llm_unavailable_or_failed"
        return rule_fields, "rule_fallback"

    llm_norm = _normalize_extracted_fields(llm_fields)
    merged = dict(rule_fields)
    merged_reasons = dict(rule_fields.get("reasons", {}))

    for key in [
        "merchant_name",
        "business_number",
        "approved_at",
        "supply_amount",
        "vat_amount",
        "total_amount",
        "approval_no",
    ]:
        if llm_norm.get(key) is not None:
            merged[key] = llm_norm[key]
            merged_reasons.pop(key, None)
        elif key not in merged_reasons:
            merged_reasons[key] = "not_found_by_llm"

    llm_reasons = llm_norm.get("reasons", {})
    if isinstance(llm_reasons, dict):
        merged_reasons.update({k: str(v) for k, v in llm_reasons.items()})

    merged["reasons"] = merged_reasons
    return merged, "llm_hybrid"
