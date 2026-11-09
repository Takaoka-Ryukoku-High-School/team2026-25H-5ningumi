import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('main_mod', Path(__file__).with_name('main.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_upsert_daily_mood_replaces_same_date():
    entries = [
        {'date': '2026-11-09', 'mood': '安心'},
        {'date': '2026-11-08', 'mood': '元気'},
    ]
    updated = module.upsert_daily_mood(entries, '元気', '2026-11-09')
    assert updated[-1] == {'date': '2026-11-09', 'mood': '元気'}
    assert len(updated) == 2
