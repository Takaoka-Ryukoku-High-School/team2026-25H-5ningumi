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
