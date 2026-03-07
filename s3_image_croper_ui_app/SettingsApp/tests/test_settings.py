import json
from pathlib import Path
from unittest.mock import patch

import pytest

from settingsapp.app import (
    DEFAULT_SETTINGS,
    load_settings,
    save_settings,
    parse_time_str,
    sd_mount_available,
    get_primary_settings_path,
)


class TestParseTimeStr:
    def test_valid_time(self):
        from datetime import time

        result = parse_time_str("22:30", fallback=time(0, 0))
        assert result == time(22, 30)

    def test_none_returns_fallback(self):
        from datetime import time

        fallback = time(6, 0)
        assert parse_time_str(None, fallback) == fallback

    def test_invalid_returns_fallback(self):
        from datetime import time

        fallback = time(6, 0)
        assert parse_time_str("not_a_time", fallback) == fallback

    def test_empty_returns_fallback(self):
        from datetime import time

        fallback = time(6, 0)
        assert parse_time_str("", fallback) == fallback


class TestLoadSettings:
    @patch("settingsapp.app.sd_mount_available", return_value=False)
    def test_returns_defaults_when_no_file(self, mock_sd, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "settingsapp.app.HOME_SETTINGS_PATH", tmp_path / "nonexistent.json"
        )
        monkeypatch.setattr(
            "settingsapp.app.SD_SETTINGS_PATH", tmp_path / "nonexistent2.json"
        )
        result = load_settings()
        assert result["picture_mode"] == DEFAULT_SETTINGS["picture_mode"]
        assert (
            result["change_interval_minutes"]
            == DEFAULT_SETTINGS["change_interval_minutes"]
        )

    @patch("settingsapp.app.sd_mount_available", return_value=False)
    def test_loads_from_home(self, mock_sd, tmp_path, monkeypatch):
        home_settings = tmp_path / "settings.json"
        home_settings.write_text(
            json.dumps({"picture_mode": "online", "change_interval_minutes": 30})
        )
        monkeypatch.setattr("settingsapp.app.HOME_SETTINGS_PATH", home_settings)
        monkeypatch.setattr(
            "settingsapp.app.SD_SETTINGS_PATH", tmp_path / "nonexistent.json"
        )

        result = load_settings()
        assert result["picture_mode"] == "online"
        assert result["change_interval_minutes"] == 30


class TestSaveSettings:
    @patch("settingsapp.app.sd_mount_available", return_value=False)
    @patch("settingsapp.app.st")
    def test_saves_to_home_when_no_sd(self, mock_st, mock_sd, tmp_path, monkeypatch):
        home_dir = tmp_path / "config"
        home_path = home_dir / "settings.json"
        monkeypatch.setattr("settingsapp.app.HOME_CONFIG_DIR", home_dir)
        monkeypatch.setattr("settingsapp.app.HOME_SETTINGS_PATH", home_path)

        settings = {"picture_mode": "both", "change_interval_minutes": 10}
        save_settings(settings)

        assert home_path.exists()
        saved = json.loads(home_path.read_text())
        assert saved["picture_mode"] == "both"

    @patch("settingsapp.app.sd_mount_available", return_value=True)
    @patch("settingsapp.app.st")
    def test_saves_to_sd_and_home(self, mock_st, mock_sd, tmp_path, monkeypatch):
        sd_dir = tmp_path / "sd_config"
        sd_path = sd_dir / "settings.json"
        home_dir = tmp_path / "home_config"
        home_path = home_dir / "settings.json"

        monkeypatch.setattr("settingsapp.app.SD_CONFIG_DIR", sd_dir)
        monkeypatch.setattr("settingsapp.app.SD_SETTINGS_PATH", sd_path)
        monkeypatch.setattr("settingsapp.app.HOME_CONFIG_DIR", home_dir)
        monkeypatch.setattr("settingsapp.app.HOME_SETTINGS_PATH", home_path)

        settings = {"picture_mode": "online", "change_interval_minutes": 5}
        save_settings(settings)

        assert sd_path.exists()
        assert home_path.exists()
        assert json.loads(sd_path.read_text())["picture_mode"] == "online"
        assert json.loads(home_path.read_text())["picture_mode"] == "online"
