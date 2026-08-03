from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one occurrence, found {count}")
    return text.replace(old, new, 1)


def patch_backend() -> None:
    path = Path("app/main.py")
    text = path.read_text(encoding="utf-8")
    old = '''    numeric_fields = {"quantity", "unit_price", "discount_rate", "line_total"}
    for field, value in supplied.items():
        setattr(line, field, Decimal(str(value)) if field in numeric_fields else value.strip())
    if "line_total" not in supplied and {"quantity", "unit_price", "discount_rate"} & set(supplied):
        base = Decimal(str(line.price_base_quantity or 1)) or Decimal("1")
        line.line_total = (
            Decimal(str(line.quantity or 0))
            * (Decimal(str(line.unit_price or 0)) / base)
            * (Decimal("1") - Decimal(str(line.discount_rate or 0)) / Decimal("100"))
        )
    provenance = raw.get("numeric_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    for field in numeric_fields & set(supplied):
        provenance[field] = "human_corrected"
'''
    new = '''    numeric_fields = {"quantity", "unit_price", "discount_rate", "line_total"}
    component_fields = {"quantity", "unit_price", "discount_rate"}
    component_changed = bool(component_fields & set(supplied))
    for field, value in supplied.items():
        setattr(line, field, Decimal(str(value)) if field in numeric_fields else value.strip())
    if component_changed:
        base = Decimal(str(line.price_base_quantity or 1)) or Decimal("1")
        line.line_total = (
            Decimal(str(line.quantity or 0))
            * (Decimal(str(line.unit_price or 0)) / base)
            * (Decimal("1") - Decimal(str(line.discount_rate or 0)) / Decimal("100"))
        ).quantize(Decimal("0.01"))
    provenance = raw.get("numeric_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    for field in numeric_fields & set(supplied):
        provenance[field] = "human_corrected"
    if component_changed:
        provenance["line_total"] = "derived_from_human_correction"
'''
    text = replace_once(text, old, new, "line-total consistency")
    path.write_text(text, encoding="utf-8")


def patch_report_popup() -> None:
    path = Path("app/static/operational-center.js")
    text = path.read_text(encoding="utf-8")
    old = '''  async function downloadReport() {
    try {
      const report = await api('/api/operational/report');
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ThisTinti-rapporto-operativo-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(url);
      const popup = window.open('', '_blank', 'noopener,noreferrer');
      if (popup) {
'''
    new = '''  async function downloadReport() {
    const popup = window.open('', '_blank', 'noopener,noreferrer');
    if (popup) {
      popup.document.write('<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Preparazione rapporto…</title></head><body><p>Preparazione del rapporto operativo…</p></body></html>');
      popup.document.close();
    }
    try {
      const report = await api('/api/operational/report');
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `ThisTinti-rapporto-operativo-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      if (popup) {
'''
    text = replace_once(text, old, new, "report popup")
    old_catch = '''      }
    } catch (error) { toast(error.message, true); }
  }
'''
    new_catch = '''      }
    } catch (error) {
      if (popup) popup.close();
      toast(error.message, true);
    }
  }
'''
    text = replace_once(text, old_catch, new_catch, "report popup error")
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_backend()
    patch_report_popup()
