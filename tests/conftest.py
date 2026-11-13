import tomllib
from pathlib import Path

import pytest

from utilityagent import settings as settings_mod
from utilityagent.knowledge import Knowledge
from utilityagent.model import Release
from utilityagent.world.sim import World

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def world():
    cfg = tomllib.loads((ROOT / "config" / "world.toml").read_text())
    cfg.update(accounts=600, sizes={"golden": 150, "traffic": 200, "demo": 10})
    return World(cfg)


@pytest.fixture(scope="session")
def cfg():
    return settings_mod.load()


@pytest.fixture(scope="session")
def kb():
    return Knowledge.load(ROOT / "config" / "knowledge.toml")


@pytest.fixture(scope="session")
def release(cfg):
    return Release(**cfg["releases"]["production"])
