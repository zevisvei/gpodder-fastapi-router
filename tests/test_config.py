from __future__ import annotations

import textwrap

from gpodder_router import GPodderConfig


def test_from_toml(tmp_path) -> None:
    cfg_path = tmp_path / "cfg.toml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            [gpodder]
            database_url = "sqlite+aiosqlite:///./x.db"
            base_url = "https://gp.example.com"
            bcrypt_rounds = 6
            admin_usernames = ["alice", "ops"]
            enable_dashboard = false
            """
        ).strip()
    )
    cfg = GPodderConfig.from_toml(cfg_path)
    assert cfg.database_url == "sqlite+aiosqlite:///./x.db"
    assert cfg.base_url == "https://gp.example.com"
    assert cfg.bcrypt_rounds == 6
    assert cfg.admin_usernames == ["alice", "ops"]
    assert cfg.enable_dashboard is False


def test_from_toml_overrides_win(tmp_path) -> None:
    cfg_path = tmp_path / "cfg.toml"
    cfg_path.write_text('[gpodder]\nbase_url = "http://from-file"\n')
    cfg = GPodderConfig.from_toml(cfg_path, base_url="http://override")
    assert cfg.base_url == "http://override"


def test_env_prefix(monkeypatch) -> None:
    monkeypatch.setenv("GPODDER_BASE_URL", "https://env.example")
    monkeypatch.setenv("GPODDER_BCRYPT_ROUNDS", "4")
    monkeypatch.setenv("GPODDER_ADMIN_USERNAMES", '["env_admin"]')
    cfg = GPodderConfig(_env_file=None)
    assert cfg.base_url == "https://env.example"
    assert cfg.bcrypt_rounds == 4
    assert cfg.admin_usernames == ["env_admin"]
