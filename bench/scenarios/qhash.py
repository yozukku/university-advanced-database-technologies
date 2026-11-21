import inspect
import tomllib
from functools import cache
from hashlib import sha256
from pathlib import Path

from .normalise import digest
from .params import seed

TIMEOUT_SECONDS = 600
DISCARDED_RUNS = 1
MEASURED_RUNS = 3
POLICY_FILES = ("bench/runner/warmup.py", "bench/runner/limits.py")
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
        "module": inspect.getsource(inspect.getmodule(scenario.select)),
        "queries": {engine: {"text": impl.text, "run": source(impl.run), "keys": source(impl.keys), "plan": source(impl.plan)}
                    for engine, impl in sorted(scenario.impls.items())},
    }


def policy(timeout=TIMEOUT_SECONDS):
    return {"timeout_seconds": timeout, "discarded_runs": DISCARDED_RUNS, "measured_runs": MEASURED_RUNS,
            "files": {path: sha256(Path(path).read_bytes()).hexdigest() for path in POLICY_FILES}}


def qhash(scenario, profile, params, timeout=TIMEOUT_SECONDS):
    return digest({"entry": entry(scenario, profile), "parameters": digest(params), "policy": policy(timeout),
                   "drivers": drivers()})
