from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_operational_center_assets_are_local_and_loaded_after_core_polish():
    loader = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    script = (ROOT / "app" / "static" / "operational-center.js").read_text(encoding="utf-8")
    style = (ROOT / "app" / "static" / "operational-center.css").read_text(encoding="utf-8")
    assert "'/operational-center.css'" in loader
    assert "loadScript('/operational-center.js')" in loader
    assert loader.index("loadScript('/product-polish.js')") < loader.index("loadScript('/operational-center.js')")
    assert "/api/operational/overview" in script
    assert "/api/operational/practices" in script
    assert "/api/operational/report" in script
    assert "/api/document-lines/${lineId}" in script
    assert "window.print()" in script
    assert "fetch('http" not in script
    assert "@media (prefers-reduced-motion: reduce)" in style


def test_operational_center_includes_practice_workflow_and_truthful_measurement_labels():
    script = (ROOT / "app" / "static" / "operational-center.js").read_text(encoding="utf-8")
    for phrase in (
        "Cosa controllare adesso",
        "Prossima verifica consigliata",
        "Confronta i documenti della pratica",
        "Segna falso positivo",
        "Correzione supervisionata",
        "Tempo medio prima decisione",
        "Non misurato",
    ):
        assert phrase in script
