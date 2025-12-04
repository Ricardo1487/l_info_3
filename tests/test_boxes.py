from app.services.boxes import build_qr_payload


def test_build_qr_payload_uses_box_code_and_path(monkeypatch):
    # Arrange: Base URL faken wie in Produktion
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://l-info-3.onrender.com")

    # Act
    url = build_qr_payload("BOX-023")

    # Assert
    assert url == "https://l-info-3.onrender.com/new-loan?box_code=BOX-023"