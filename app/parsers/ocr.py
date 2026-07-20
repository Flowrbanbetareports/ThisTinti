from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import tempfile
from pathlib import Path

from ..config import settings
from .base import ParseError


def find_tesseract() -> str | None:
    configured = os.getenv("THISTINTI_TESSERACT_DIR", "").strip()
    if configured:
        root = Path(configured)
        for name in ("tesseract.exe", "tesseract"):
            candidate = root / name
            if candidate.exists() and candidate.is_file():
                return str(candidate)
    return shutil.which("tesseract")


def pdf_renderer_available() -> bool:
    if shutil.which("pdftoppm"):
        return True
    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        return False
    return True


def ocr_runtime_available() -> bool:
    return find_tesseract() is not None and pdf_renderer_available()


def _render_with_pdfium(path: Path, output_dir: Path) -> list[Path]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ParseError("Renderer PDF locale non disponibile") from exc

    images: list[Path] = []
    try:
        document = pdfium.PdfDocument(path)
        page_count = min(len(document), settings.ocr_max_pages)
        scale = settings.ocr_dpi / 72.0
        for index in range(page_count):
            page = document[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            target = output_dir / f"page-{index + 1:04d}.png"
            image.save(target, format="PNG")
            images.append(target)
            image.close()
            bitmap.close()
            page.close()
        document.close()
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"Rendering PDF integrato fallito: {exc}") from exc
    return images


def _render_pdf(path: Path, output_dir: Path) -> tuple[list[Path], str]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return _render_with_pdfium(path, output_dir), "pdfium"

    prefix = output_dir / "page"
    render_command = [
        pdftoppm,
        "-f",
        "1",
        "-l",
        str(settings.ocr_max_pages),
        "-r",
        str(settings.ocr_dpi),
        "-png",
        str(path),
        str(prefix),
    ]
    try:
        subprocess.run(  # nosec B603
            render_command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=settings.ocr_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseError("Rendering PDF per OCR scaduto") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace")[-500:]
        raise ParseError(f"Rendering PDF per OCR fallito: {detail}") from exc
    return sorted(output_dir.glob("page-*.png")), "pdftoppm"


def ocr_pdf(path: Path) -> tuple[str, dict[str, object]]:
    """Extract text from a scanned PDF with local-only tools.

    PDFium is used as an embedded renderer when Poppler is unavailable. Tesseract
    remains an external local process and receives no network access from ThisTinti.
    """
    if not settings.ocr_enabled:
        raise ParseError("PDF privo di testo estraibile; OCR locale disabilitato")
    tesseract = find_tesseract()
    if not tesseract or not pdf_renderer_available():
        raise ParseError("PDF privo di testo estraibile; strumenti OCR locali non disponibili")

    with tempfile.TemporaryDirectory(prefix="thistinti-ocr-") as tmp:
        tmp_path = Path(tmp)
        images, renderer = _render_pdf(path, tmp_path)
        if not images:
            raise ParseError("OCR non ha prodotto pagine elaborabili")

        page_texts: list[str] = []
        total_chars = 0
        command_env = os.environ.copy()
        tessdata_prefix = os.getenv("TESSDATA_PREFIX", "").strip()
        if tessdata_prefix:
            command_env["TESSDATA_PREFIX"] = tessdata_prefix
        for image in images:
            command = [
                tesseract,
                str(image),
                "stdout",
                "-l",
                settings.ocr_languages,
                "--psm",
                "6",
            ]
            try:
                result = subprocess.run(  # nosec B603
                    command,
                    check=True,
                    capture_output=True,
                    timeout=settings.ocr_timeout_seconds,
                    env=command_env,
                )
            except subprocess.TimeoutExpired as exc:
                raise ParseError("Riconoscimento OCR scaduto") from exc
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.decode("utf-8", errors="replace")[-500:]
                raise ParseError(f"Riconoscimento OCR fallito: {detail}") from exc
            text = result.stdout.decode("utf-8", errors="replace")
            total_chars += len(text)
            if total_chars > settings.ocr_max_chars:
                raise ParseError("Testo OCR oltre il limite consentito")
            page_texts.append(text)

    text = "\n".join(page_texts).strip()
    if not text:
        raise ParseError("OCR completato senza testo riconoscibile")
    return text, {
        "extraction_method": "local_ocr",
        "ocr_engine": "tesseract",
        "pdf_renderer": renderer,
        "ocr_languages": settings.ocr_languages,
        "ocr_pages": len(page_texts),
        "ocr_dpi": settings.ocr_dpi,
        "evidence_class": "derived",
    }
