from __future__ import annotations

import os
import tomllib
from pathlib import Path

# the checkout in development; the image sets UTILITYAGENT_ROOT, because an installed package lives in site-packages
ROOT = Path(os.environ.get("UTILITYAGENT_ROOT", Path(__file__).resolve().parents[2]))


def load() -> dict:
    cfg = tomllib.loads((ROOT / "config" / "policy.toml").read_text())
    cfg["releases"] = tomllib.loads((ROOT / "config" / "releases.toml").read_text())
    cfg["prices"] = tomllib.loads((ROOT / "config" / "models.toml").read_text())["models"]
    return cfg
