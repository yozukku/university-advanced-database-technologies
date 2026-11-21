import importlib
import pkgutil
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Callable

import yaml

ENGINES = ("pg", "mysql", "mongo", "neo4j")
JSON_ENGINES = ("pg", "mysql", "mongo")
OPS = ("C", "R", "U", "D")
FLAGS = frozenset({"CX", "BA", "H1-S", "H1-I", "H1-U"})
PACKAGES = ("create", "read", "update", "delete", "json")
ORDER = "CRUDJ"
OPS_FILE = Path("bench/scenarios/ops.yaml")
COUNTS = ("ops", "ops_xs")


@dataclass(frozen=True, eq=False)
class Impl:
    text: str
    run: Callable
    keys: Callable | None = None
    plan: Callable | None = None
    after: Callable | None = None


@dataclass(frozen=True, eq=False)
class Scenario:
    id: str
    op: str
    description: str
    impls: dict
    select: Callable
    flags: frozenset = frozenset()
    columns: tuple = ()
    ordered: bool = False
    ops: dict | None = None

    @property
    def read(self):
        return self.op == "R"

    @property
    def engines(self):
        return tuple(engine for engine in ENGINES if engine in self.impls)

    @property
    def configs(self):
        return ("idx", "base") if "BA" in self.flags else ("idx",)

    def config(self, size):
        entry = read_ops()[self.id] if self.ops is None else self.ops
        return {"count": entry["ops_xs" if size == "XS" else "ops"]} | {
            key: value for key, value in entry.items() if key not in COUNTS}

    def problems(self):
        found = []
        if self.op not in OPS:
            found.append(f"op {self.op!r} is not one of {', '.join(OPS)}")
        if not self.description.strip():
            found.append("no description")
        if unknown := set(self.flags) - FLAGS:
            found.append(f"unknown flags {sorted(unknown)}")
        if self.ops is None:
            wanted = JSON_ENGINES if self.id.startswith("J") else ENGINES
            if self.engines != wanted:
                found.append(f"engines {self.engines}, expected {wanted}")
        if self.read and not self.columns:
            found.append("a read declares no result columns")
        for engine, impl in self.impls.items():
            if engine not in ENGINES:
                found.append(f"unknown engine {engine}")
            if not impl.text.strip():
                found.append(f"{engine}: no query text")
            if self.read and impl.plan is None:
                found.append(f"{engine}: a read has no plan query")
            if not self.read and impl.keys is None:
                found.append(f"{engine}: a write has no key probe")
        return found


@cache
def read_ops():
    return yaml.safe_load(OPS_FILE.read_text())


def position(scenario_id):
    return ORDER.index(scenario_id[0]), int(scenario_id[1:])


def load():
    found = {}
    for package in PACKAGES:
        directory = Path(__file__).parent / package
        for module in pkgutil.iter_modules([str(directory)]):
            for scenario in importlib.import_module(f"bench.scenarios.{package}.{module.name}").SCENARIOS:
                if scenario.id in found:
                    raise ValueError(f"Scenario {scenario.id} is registered twice")
                found[scenario.id] = scenario
    return dict(sorted(found.items(), key=lambda item: position(item[0])))
