import zlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

import duckdb
import numpy as np

from bench.check.parquet import connect
from bench.check.verify.canonical import TABLES
from bench.gen.profiles import load_profile

FRESH = 10 ** 12
CHILD = 10 ** 13


@dataclass(frozen=True)
class Pick:
    db: duckdb.DuckDBPyConnection
    rng: np.random.Generator
    count: int | None
    config: dict
    t0: datetime


def chunks(items, size):
    return [items[start:start + size] for start in range(0, len(items), size)]


def fresh_id(n):
    return FRESH + n


def child_id(parent_id, slot):
    return (slot + 1) * CHILD + parent_id


@contextmanager
def dataset(size):
    profile = load_profile(size)
    with connect(profile.destination, TABLES) as db:
        db.execute("set timezone = 'UTC'")
        db.execute("set variable benchmark_t0 = ?", [profile.t0])
        yield db, profile


def seed(profile, scenario):
    return [profile.seed, zlib.crc32(scenario.id.encode())]


def plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def parameters(scenario, db, profile):
    config = scenario.config(profile.size)
    rng = np.random.default_rng(np.random.SeedSequence(seed(profile, scenario)))
    return plain(scenario.select(Pick(db, rng, config["count"], config, profile.t0)))
