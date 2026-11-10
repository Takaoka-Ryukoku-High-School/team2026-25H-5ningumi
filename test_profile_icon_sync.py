import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("main_mod", Path(__file__).with_name("main.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_build_icon_visual_matches_profile_icon():
    emoji = module.build_icon_visual("🐼")
    image = module.build_icon_visual("data:image/png;base64,AAAA")

    assert emoji[0] == "emoji"
    assert image[0] == "image"
    assert emoji[1] == "🐼"
    assert image[1].startswith("data:image/png;base64,")


def test_profile_data_round_trip(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(module, "PROFILE_FILE", profile_path)

    history = [
        {"date": "2026-01-01", "height_cm": "159", "weight_kg": "51.0"},
        {"date": "2026-01-10", "height_cm": "160", "weight_kg": "52.5"},
    ]
    module.save_profile_data({
        "height_cm": "160",
        "weight_kg": "52.5",
        "history": history,
    })

    loaded = module.load_profile_data()
    assert loaded["height_cm"] == "160"
    assert loaded["weight_kg"] == "52.5"
    assert loaded["history"][0]["date"] == "2026-01-01"

    chart = module.build_measurement_chart_svg(loaded["history"], "160", "52.5")
    assert chart is not None
    assert chart.startswith("data:image/svg+xml;base64,")
    assert "<svg" in __import__("base64").b64decode(chart.split(",", 1)[1]).decode("utf-8")
