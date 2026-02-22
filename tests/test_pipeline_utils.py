from autodocument.utils import business_checksum, normalize_date, to_int_amount


def test_normalize_date():
    assert normalize_date("2026.02.22") == "2026-02-22"


def test_to_int_amount():
    assert to_int_amount("1,234원") == 1234


def test_business_checksum_false_for_invalid_number():
    assert business_checksum("123-45-67890") is False
