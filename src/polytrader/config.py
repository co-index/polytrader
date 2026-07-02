"""Configuration: non-secret settings from config.yaml, secrets from the environment.

Secrets are NEVER read from the yaml file (Constitution I). Risk limits are validated
here so an invalid config fails fast rather than at trade time.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Mode = Literal["dry_run", "live"]


class RiskConfig(BaseModel):
    """Hard limits enforced by the risk gate. All caps must be positive."""

    per_order_max_usd: float = Field(gt=0)
    total_exposure_max_usd: float = Field(gt=0)
    daily_loss_limit_usd: float = Field(gt=0)
    market_whitelist: list[str] = Field(default_factory=list)


class MarketSpec(BaseModel):
    """A market/outcome-token the engine should poll each tick."""

    market_id: str
    token_id: str
    question: str = ""


class Secrets(BaseModel):
    """Loaded only from the environment; never persisted or logged."""

    wallet_private_key: str = ""
    clob_api_key: str = ""
    clob_api_secret: str = ""
    clob_api_passphrase: str = ""
    clob_host: str = "https://clob.polymarket.com"
    chain_id: int = 137
    # Proxy-wallet accounts (polymarket.com email/browser signup): the address that
    # holds the funds, and how orders are signed (1=email/Magic, 2=browser wallet).
    # Both empty -> a self-custody EOA trading directly.
    poly_funder_address: str = ""
    poly_signature_type: int | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Secrets:
        sig = env.get("POLY_SIGNATURE_TYPE", "")
        return cls(
            wallet_private_key=env.get("WALLET_PRIVATE_KEY", ""),
            clob_api_key=env.get("CLOB_API_KEY", ""),
            clob_api_secret=env.get("CLOB_API_SECRET", ""),
            clob_api_passphrase=env.get("CLOB_API_PASSPHRASE", ""),
            clob_host=env.get("CLOB_HOST", "https://clob.polymarket.com"),
            chain_id=int(env.get("CHAIN_ID", "137")),
            poly_funder_address=env.get("POLY_FUNDER_ADDRESS", ""),
            poly_signature_type=int(sig) if sig.strip() else None,
        )


def load_dotenv(path: str | Path, env: Mapping[str, str]) -> dict[str, str]:
    """Merge KEY=VALUE lines from a .env file under the real environment (real env
    wins). Missing file -> env unchanged. No external dependency."""
    merged: dict[str, str] = {}
    p = Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                merged[k.strip()] = v.strip()
    merged.update(env)
    return merged


class Settings(BaseModel):
    """Full runtime configuration."""

    tick_interval_seconds: int = 10
    default_mode: Mode = "dry_run"
    db_path: str = "data/polytrader.db"
    risk: RiskConfig
    markets: list[MarketSpec] = Field(default_factory=list)
    secrets: Secrets = Field(default_factory=Secrets)

    @classmethod
    def load(cls, config_path: str | Path, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        data = yaml.safe_load(Path(config_path).read_text()) or {}
        # Secrets come from the environment exclusively, never from the yaml.
        data.pop("secrets", None)
        data["secrets"] = Secrets.from_env(env)
        return cls(**data)
