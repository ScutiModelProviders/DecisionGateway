from src.config import Settings, load_settings
from src.options import live, make_config


def test_defaults():
    s = Settings()
    assert s.port == 29406 and s.max_chars == 16000 and s.max_inflight == 8 and s.cache_enabled


def test_exposed_without_auth():
    assert Settings(host="0.0.0.0").exposed_without_auth
    assert not Settings(host="0.0.0.0", admin_password="pw").exposed_without_auth
    assert not Settings().exposed_without_auth


def test_environment_and_saved_data_path(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVICE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SERVICE_PORT", "29999")
    assert load_settings().port == 29999
    moved = tmp_path / "moved"
    (tmp_path / "settings.json").write_text('{"data_path": "%s"}' % moved.as_posix(), "utf-8")
    s = load_settings()
    assert s.data_dir == moved and s.state_dir == tmp_path


def test_live_settings_follow_saved_values(tmp_path):
    base = Settings(data_dir=tmp_path, admin_password="pw")
    config = make_config(base)
    settings = live(base, config)
    assert settings.max_chars == 16000
    config.set({"max_chars": 500})
    assert settings.max_chars == 500
    assert make_config(Settings(data_dir=tmp_path)) is None
