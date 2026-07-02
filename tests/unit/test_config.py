"""Unit tests for polytrader.config — secrets from env, limits from yaml."""

import textwrap

import pytest
from pydantic import ValidationError

from polytrader.config import RiskConfig, Settings


def _write_config(tmp_path, body: str):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(body))
    return p


def test_riskconfig_rejects_nonpositive_per_order_cap():
    with pytest.raises(ValidationError):
        RiskConfig(
            per_order_max_usd=0,
            total_exposure_max_usd=50,
            daily_loss_limit_usd=20,
            market_whitelist=["m1"],
        )


def test_settings_loads_risk_limits_from_yaml(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        tick_interval_seconds: 10
        default_mode: dry_run
        db_path: data/polytrader.db
        risk:
          per_order_max_usd: 5.0
          total_exposure_max_usd: 50.0
          daily_loss_limit_usd: 20.0
          market_whitelist:
            - m1
            - m2
        """,
    )
    s = Settings.load(cfg, env={})
    assert s.risk.per_order_max_usd == 5.0
    assert s.risk.total_exposure_max_usd == 50.0
    assert s.risk.daily_loss_limit_usd == 20.0
    assert s.risk.market_whitelist == ["m1", "m2"]
    assert s.tick_interval_seconds == 10


def test_settings_reads_secrets_from_env_not_yaml(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        tick_interval_seconds: 10
        default_mode: dry_run
        db_path: data/polytrader.db
        risk:
          per_order_max_usd: 5.0
          total_exposure_max_usd: 50.0
          daily_loss_limit_usd: 20.0
          market_whitelist: [m1]
        """,
    )
    env = {
        "WALLET_PRIVATE_KEY": "0xdeadbeef",
        "CLOB_API_KEY": "key",
        "CLOB_API_SECRET": "secret",
        "CLOB_API_PASSPHRASE": "pass",
    }
    s = Settings.load(cfg, env=env)
    assert s.secrets.wallet_private_key == "0xdeadbeef"
    assert s.secrets.clob_api_key == "key"


def test_settings_default_mode_must_be_valid(tmp_path):
    cfg = _write_config(
        tmp_path,
        """
        tick_interval_seconds: 10
        default_mode: bogus
        db_path: data/polytrader.db
        risk:
          per_order_max_usd: 5.0
          total_exposure_max_usd: 50.0
          daily_loss_limit_usd: 20.0
          market_whitelist: [m1]
        """,
    )
    with pytest.raises(ValidationError):
        Settings.load(cfg, env={})


def test_secrets_include_proxy_wallet_fields():
    from polytrader.config import Secrets

    s = Secrets.from_env({
        "WALLET_PRIVATE_KEY": "0x" + "a" * 64,
        "POLY_FUNDER_ADDRESS": "0xFUNDER",
        "POLY_SIGNATURE_TYPE": "1",
    })
    assert s.poly_funder_address == "0xFUNDER"
    assert s.poly_signature_type == 1
    # Absent -> direct-EOA defaults (no proxy).
    d = Secrets.from_env({})
    assert d.poly_funder_address == ""
    assert d.poly_signature_type is None


def test_load_dotenv_file_parses_without_overriding_existing(tmp_path):
    from polytrader.config import load_dotenv

    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "WALLET_PRIVATE_KEY=0xabc\n"
        "POLY_SIGNATURE_TYPE=1\n"
        "EMPTY=\n",
        encoding="utf-8",
    )
    env = {"WALLET_PRIVATE_KEY": "0xalready"}
    merged = load_dotenv(f, env)
    assert merged["WALLET_PRIVATE_KEY"] == "0xalready"  # real env wins
    assert merged["POLY_SIGNATURE_TYPE"] == "1"
    assert merged["EMPTY"] == ""
    # Missing file -> env passthrough, no crash.
    assert load_dotenv(tmp_path / "nope", {"A": "1"}) == {"A": "1"}
