# Third-party notices

ThisTinti is distributed with open-source Python dependencies documented in
`docs/sbom.cdx.json`. A Windows Local Edition build may additionally bundle:

- **Tesseract OCR**, Apache License 2.0;
- language data from **tessdata_fast**, Apache License 2.0;
- **PDFium** through `pypdfium2`, under its applicable BSD/Apache notices;
- the Python interpreter and standard library under the Python Software Foundation License;
- Inno Setup only as the build tool; it is not part of the installed runtime.

The release build must preserve the license files copied from bundled third-party
components. The generated SBOM is the authoritative machine-readable inventory.
