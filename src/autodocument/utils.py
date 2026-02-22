from __future__ import annotations

import re


def normalize_date(raw: str) -> str | None:
    cleaned = re.sub(r"[^0-9]", "", raw)
    if len(cleaned) != 8:
        return None
    return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"


def to_int_amount(raw: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", raw)
    return int(digits) if digits else None


def business_checksum(number: str) -> bool:
    digits = re.sub(r"[^0-9]", "", number)
    if len(digits) != 10:
        return False
    weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    total = sum(int(digits[i]) * weights[i] for i in range(9))
    total += (int(digits[8]) * 5) // 10
    return (10 - (total % 10)) % 10 == int(digits[9])
