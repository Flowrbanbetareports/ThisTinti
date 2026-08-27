from scripts.check_module_boundaries import LIMITS, build_report


def test_large_modules_have_hard_growth_boundaries() -> None:
    report = build_report()

    assert report["passed"] is True, report["failures"]
    assert set(LIMITS) == {
        "app/main.py",
        "app/api.py",
        "app/rc15_api.py",
        "app/services/rc15.py",
        "app/services/intelligence.py",
        "app/services/rules.py",
        "app/services/discovery.py",
        "app/static/app-core.js",
        "app/static/rc15.js",
    }
    for module in report["modules"]:
        assert module["remaining"] >= 0
        assert module["limit"] > 0
