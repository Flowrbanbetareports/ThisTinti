from pathlib import Path

from openpyxl import Workbook

from app.parsers.base import parse_file


def test_xlsx_parser(tmp_path: Path):
    path = tmp_path / "order.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Codice", "Descrizione", "Quantità", "Prezzo unitario", "Sconto", "Colore", "Taglia"])
    ws.append(["A-1", "Giacca", 10, 20, 5, "Blu", "48"])
    wb.save(path)
    result = parse_file(
        path,
        path.name,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        {"document_type": "order", "supplier_name": "Supplier"},
    )
    assert len(result.lines) == 1
    assert result.lines[0].quantity == 10
    assert result.lines[0].sku == "A-1"
