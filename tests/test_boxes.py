from app.services.boxes import build_qr_payload, validate_box_code


def test_validate_box_code_accepts_numeric_short_codes():
    assert validate_box_code("1")
    assert validate_box_code("23")
    assert validate_box_code("123")


def test_validate_box_code_accepts_full_box_format():
    assert validate_box_code("BOX-001")
    assert validate_box_code("BOX-999")


def test_validate_box_code_rejects_invalid_codes():
    assert not validate_box_code("")          # leer
    assert not validate_box_code("BOX-12")    # zu kurz
    assert not validate_box_code("BOX-1234")  # zu lang
    assert not validate_box_code("ABC-123")   # falsches Prefix
    assert not validate_box_code("BOX-XYZ")   # keine Ziffern

def test_build_qr_payload_uses_box_code_and_path(monkeypatch):
    # Arrange: Base URL faken wie in Produktion
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://l-info-3.onrender.com")

    # Act
    url = build_qr_payload("BOX-023")

    # Assert
    assert url == "https://l-info-3.onrender.com/new-loan?box_code=BOX-023"