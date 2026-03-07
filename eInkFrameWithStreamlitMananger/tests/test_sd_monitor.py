import json
import os
import time as time_mod
from datetime import datetime, time as dtime

import pytest

# Add parent directory so standalone modules are importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sd_monitor import (
    load_settings,
    get_refresh_time,
    parse_hhmm,
    parse_stop_rotation_between,
    in_quiet_hours,
    compute_tree_stats,
    DEFAULT_SETTINGS,
    SETTINGS_LOCATIONS,
)


class TestLoadSettings:
    def test_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("settings_loader.SETTINGS_LOCATIONS", [str(tmp_path / "nonexistent.json")])
        result = load_settings()
        assert result == DEFAULT_SETTINGS

    def test_loads_from_file(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(json.dumps({"picture_mode": "online", "change_interval_minutes": 30}))
        monkeypatch.setattr("settings_loader.SETTINGS_LOCATIONS", [str(settings_file)])

        result = load_settings()
        assert result["picture_mode"] == "online"
        assert result["change_interval_minutes"] == 30
        # Defaults preserved for unset keys
        assert result["s3_folder"] == "s3_folder"

    def test_priority_order(self, tmp_path, monkeypatch):
        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        first.write_text(json.dumps({"picture_mode": "both"}))
        second.write_text(json.dumps({"picture_mode": "local"}))
        monkeypatch.setattr("settings_loader.SETTINGS_LOCATIONS", [str(first), str(second)])

        result = load_settings()
        assert result["picture_mode"] == "both"  # first file wins

    def test_invalid_json_falls_through(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.json"
        good = tmp_path / "good.json"
        bad.write_text("not json")
        good.write_text(json.dumps({"picture_mode": "online"}))
        monkeypatch.setattr("settings_loader.SETTINGS_LOCATIONS", [str(bad), str(good)])

        result = load_settings()
        assert result["picture_mode"] == "online"


class TestGetRefreshTime:
    def test_from_settings(self, tmp_path):
        settings = {"change_interval_minutes": 5}
        assert get_refresh_time(str(tmp_path), settings=settings) == 300

    def test_from_file_fallback(self, tmp_path):
        (tmp_path / "refresh_time.txt").write_text("120")
        settings = {}  # no change_interval_minutes
        assert get_refresh_time(str(tmp_path), settings=settings) == 120

    def test_default_when_nothing(self, tmp_path):
        assert get_refresh_time(str(tmp_path), settings={}) == 600


class TestParseHhmm:
    def test_valid(self):
        assert parse_hhmm("22:30") == dtime(22, 30)

    def test_invalid(self):
        assert parse_hhmm("not_a_time") is None

    def test_midnight(self):
        assert parse_hhmm("00:00") == dtime(0, 0)


class TestParseStopRotationBetween:
    def test_valid(self):
        cfg = {"evening": "22:00", "morning": "06:00"}
        result = parse_stop_rotation_between(cfg)
        assert result == (dtime(22, 0), dtime(6, 0))

    def test_none_input(self):
        assert parse_stop_rotation_between(None) is None

    def test_missing_keys(self):
        assert parse_stop_rotation_between({"evening": "22:00"}) is None


class TestInQuietHours:
    def test_overnight_in_quiet(self):
        evening = dtime(22, 0)
        morning = dtime(6, 0)
        now = datetime(2026, 1, 1, 23, 30)
        assert in_quiet_hours(now, evening, morning) is True

    def test_overnight_before_evening(self):
        evening = dtime(22, 0)
        morning = dtime(6, 0)
        now = datetime(2026, 1, 1, 15, 0)
        assert in_quiet_hours(now, evening, morning) is False

    def test_overnight_after_morning(self):
        evening = dtime(22, 0)
        morning = dtime(6, 0)
        now = datetime(2026, 1, 1, 7, 0)
        assert in_quiet_hours(now, evening, morning) is False

    def test_same_day_in_quiet(self):
        evening = dtime(13, 0)
        morning = dtime(15, 0)
        now = datetime(2026, 1, 1, 14, 0)
        assert in_quiet_hours(now, evening, morning) is True


class TestComputeTreeStats:
    def test_counts_files(self, tmp_path):
        (tmp_path / "a.jpg").write_text("a")
        (tmp_path / "b.jpg").write_text("b")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.jpg").write_text("c")

        _, count = compute_tree_stats(str(tmp_path))
        assert count == 3

    def test_ignores_epaper_pic(self, tmp_path):
        (tmp_path / "a.jpg").write_text("a")
        cache = tmp_path / "_epaper_pic"
        cache.mkdir()
        (cache / "cached.jpg").write_text("cached")

        _, count = compute_tree_stats(str(tmp_path))
        assert count == 1

    def test_tracks_mtime(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("content")
        mtime, _ = compute_tree_stats(str(tmp_path))
        assert mtime > 0
