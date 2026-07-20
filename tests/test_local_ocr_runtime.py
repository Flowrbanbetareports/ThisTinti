from __future__ import annotations

from pathlib import Path

from app.parsers import ocr


def test_configured_tesseract_is_preferred(monkeypatch, tmp_path: Path):
    executable = tmp_path / "tesseract"
    executable.write_text("binary", encoding="utf-8")
    monkeypatch.setenv("THISTINTI_TESSERACT_DIR", str(tmp_path))
    assert ocr.find_tesseract() == str(executable)


def test_pdfium_is_an_embedded_renderer_fallback(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _name: None)
    assert ocr.pdf_renderer_available() is True


def test_ocr_runtime_requires_tesseract(monkeypatch):
    monkeypatch.setattr(ocr, "find_tesseract", lambda: None)
    assert ocr.ocr_runtime_available() is False
