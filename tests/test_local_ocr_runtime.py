from __future__ import annotations

from pathlib import Path

from app.parsers import ocr


def test_configured_tesseract_is_preferred(monkeypatch, tmp_path: Path):
    executable = tmp_path / "tesseract"
    executable.write_text("binary", encoding="utf-8")
    monkeypatch.setenv("THISTINTI_TESSERACT_DIR", str(tmp_path))
    assert ocr.find_tesseract() == str(executable)


def test_source_runtime_can_fall_back_to_path(monkeypatch):
    monkeypatch.delenv("THISTINTI_TESSERACT_DIR", raising=False)
    monkeypatch.delattr(ocr.sys, "frozen", raising=False)
    monkeypatch.delattr(ocr.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract" if name == "tesseract" else None)
    assert ocr.find_tesseract() == "/usr/bin/tesseract"


def test_frozen_runtime_does_not_fall_back_to_system_tesseract(monkeypatch, tmp_path: Path):
    missing_bundle = tmp_path / "missing-bundled-ocr"
    monkeypatch.setenv("THISTINTI_TESSERACT_DIR", str(missing_bundle))
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ocr.shutil, "which", lambda name: r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
    assert ocr.find_tesseract() is None


def test_frozen_runtime_without_configured_bundle_fails_closed(monkeypatch):
    monkeypatch.delenv("THISTINTI_TESSERACT_DIR", raising=False)
    monkeypatch.setattr(ocr.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ocr.shutil, "which", lambda name: r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
    assert ocr.find_tesseract() is None


def test_pdfium_is_an_embedded_renderer_fallback(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    assert ocr.pdf_renderer_available() is True


def test_ocr_runtime_requires_tesseract(monkeypatch):
    monkeypatch.setattr(ocr, "find_tesseract", lambda: None)
    assert ocr.ocr_runtime_available() is False
