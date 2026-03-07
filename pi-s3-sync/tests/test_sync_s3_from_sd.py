"""Tests for sync_s3_from_sd.py pure-logic functions."""

import json
import os
import sys

import pytest

# Add scripts/ to path so we can import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import sync_s3_from_sd as sync


# ---------- _first_nonempty ----------


class TestFirstNonempty:
    def test_returns_first_non_empty(self):
        assert sync._first_nonempty("", "  ", "hello", "world") == "hello"

    def test_strips_whitespace(self):
        assert sync._first_nonempty("  foo  ") == "foo"

    def test_returns_none_when_all_empty(self):
        assert sync._first_nonempty("", "  ", None) is None

    def test_returns_none_for_no_args(self):
        assert sync._first_nonempty() is None

    def test_skips_non_strings(self):
        assert sync._first_nonempty(None, 42, "ok") == "ok"


# ---------- load_config ----------


class TestLoadConfig:
    def test_loads_standard_keys(self, tmp_path):
        cfg = {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "s3_bucket": "my-bucket",
            "aws_region": "us-west-2",
        }
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps(cfg))
        result = sync.load_config(str(path))
        assert result["aws_access_key_id"] == "AKID"
        assert result["aws_secret_access_key"] == "SECRET"
        assert result["s3_bucket"] == "my-bucket"
        assert result["aws_region"] == "us-west-2"

    def test_accepts_alternate_key_names(self, tmp_path):
        cfg = {
            "aws_key_id": "AKID",
            "aws_secret": "SECRET",
            "bucket": "alt-bucket",
            "region": "eu-west-1",
        }
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps(cfg))
        result = sync.load_config(str(path))
        assert result["aws_access_key_id"] == "AKID"
        assert result["aws_secret_access_key"] == "SECRET"
        assert result["s3_bucket"] == "alt-bucket"

    def test_raises_on_missing_required(self, tmp_path):
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps({"aws_region": "eu-central-1"}))
        with pytest.raises(ValueError, match="Missing AWS config"):
            sync.load_config(str(path))

    def test_default_region(self, tmp_path):
        cfg = {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "s3_bucket": "bucket",
        }
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps(cfg))
        result = sync.load_config(str(path))
        assert result["aws_region"] == "eu-central-1"

    def test_wifi_fields_optional(self, tmp_path):
        cfg = {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "s3_bucket": "bucket",
        }
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps(cfg))
        result = sync.load_config(str(path))
        assert result["wifi_name"] is None
        assert result["wifi_password"] is None

    def test_wifi_fields_present(self, tmp_path):
        cfg = {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "s3_bucket": "bucket",
            "wifi_name": "MySSID",
            "wifi_password": "MyPass",
        }
        path = tmp_path / "wifi.json"
        path.write_text(json.dumps(cfg))
        result = sync.load_config(str(path))
        assert result["wifi_name"] == "MySSID"
        assert result["wifi_password"] == "MyPass"


# ---------- ensure_wifi_connection ----------


class TestEnsureWifiConnection:
    def test_skips_when_no_ssid(self):
        assert (
            sync.ensure_wifi_connection({"wifi_name": None, "wifi_password": "x"}) == 0
        )

    def test_skips_when_no_password(self):
        assert (
            sync.ensure_wifi_connection({"wifi_name": "x", "wifi_password": None}) == 0
        )

    def test_skips_when_ssid_too_long(self):
        cfg = {"wifi_name": "A" * 33, "wifi_password": "pass"}
        assert sync.ensure_wifi_connection(cfg) == 0

    def test_skips_when_password_too_long(self):
        cfg = {"wifi_name": "ssid", "wifi_password": "A" * 64}
        assert sync.ensure_wifi_connection(cfg) == 0


# ---------- determine_base_path ----------


class TestDetermineBasePath:
    def test_uses_home_without_sudo(self, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = sync.determine_base_path()
        assert result == os.path.expanduser("~")

    def test_uses_sudo_user_home(self, monkeypatch):
        monkeypatch.setenv("SUDO_USER", "testuser")
        result = sync.determine_base_path()
        assert result == os.path.expanduser("~testuser")


# ---------- main ----------


class TestMain:
    def test_returns_1_when_no_wifi_json(self, monkeypatch, tmp_path):
        """main() returns 1 if wifi.json cannot be found anywhere."""
        monkeypatch.setattr(sync, "find_mount_with_wifi", lambda: None)
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert sync.main() == 1
