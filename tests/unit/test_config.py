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
