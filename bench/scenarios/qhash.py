import inspect
import tomllib
from functools import cache
from pathlib import Path

from .normalise import digest
from .params import seed

POLICY = {"timeout_seconds": 600, "discarded_runs": 1, "measured_runs": 3}
DRIVERS = ("psycopg", "mysql-connector-python", "pymongo", "neo4j")
LOCK = Path("uv.lock")


@cache
def drivers():
    packages = tomllib.loads(LOCK.read_text())["package"]
    return {package["name"]: package["version"] for package in packages if package["name"] in DRIVERS}


def source(function):
    return None if function is None else inspect.getsource(function)


def entry(scenario, profile):
    return {
        "id": scenario.id,
        "op": scenario.op,
        "config": scenario.config(profile.size),
        "seed": seed(profile, scenario),
        "queries": {engine: {"text": impl.text, "run": source(impl.run), "keys": source(impl.keys), "plan": source(impl.plan)}
                    for engine, impl in sorted(scenario.impls.items())},
    }


def qhash(scenario, profile, params):
    return digest({"entry": entry(scenario, profile), "parameters": digest(params), "policy": POLICY, "drivers": drivers()})
