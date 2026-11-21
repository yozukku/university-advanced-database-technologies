import traceback
from dataclasses import dataclass

import docker
import pytest

from bench.check.verify.canonical import read_schema
from bench.gen.profiles import load_profile
from bench.runner.state import snapshot as state
from bench.runner.state.containers import engine_container, stopped

from . import oracle
from .executor import Outcome, Session, execute
from .explain import access, explain, plan
from .normalise import digest, encode, result
from .params import dataset, parameters
from .registry import ENGINES, Scenario

HASHED = ("XS", "S")
CHECKS = ("metadata", "errors", "hash", "empty", "union", "probe", "affected", "commits", "rebuild", "coverage")


@dataclass
class Run:
    outcome: Outcome | None = None
    results: list | None = None
    hash: str | None = None
    access: dict | None = None
    plan: dict | None = None
    probe: dict | None = None
    rebuild: dict | None = None
    after: dict | None = None
    error: str | None = None


class Harness:
    def __init__(self, size, scenarios):
        self.size = size
        self.scenarios = scenarios
        self.client = docker.from_env()
        self.live = None
        self.params = {}
        self.runs = {}

    def run(self):
        self.schema = read_schema(load_profile(self.size).destination)
        with dataset(self.size) as (db, profile):
            for scenario in self.scenarios:
                self.params[scenario.id] = parameters(scenario, db, profile)
        try:
            for engine in ENGINES:
                for config in ("idx", "base"):
                    group = [scenario for scenario in self.scenarios
                             if engine in scenario.impls and config in scenario.configs]
                    if group:
                        self.engine(engine, config, group)
        finally:
            self.stop()

    def stop(self):
        if self.live:
            stopped(engine_container(self.client, self.live), kill=True)
            self.live = None

    def restore(self, engine, config):
        self.stop()
        try:
            state.restore(engine, self.size, config)
        except SystemExit as error:
            raise RuntimeError(str(error)) from None
        self.live = engine

    def engine(self, engine, config, group):
        self.restore(engine, config)
        with Session(engine) as session:
            for scenario in group:
                if scenario.read:
                    self.attempt(scenario, config, self.read, session)
        before = None
        for position, scenario in enumerate(scenario for scenario in group if not scenario.read):
            if position:
                self.restore(engine, config)
            with Session(engine) as session:
                if before is None and self.size in HASHED:
                    before = oracle.snapshot(session, self.schema)
                self.attempt(scenario, config, self.write, session, before)

    def attempt(self, scenario, config, step, session, *args):
        try:
            found = step(scenario, session, *args)
        except Exception:
            found = Run(error=traceback.format_exc(limit=-4))
        self.runs[(scenario.id, session.engine, config)] = found

    def read(self, scenario, session):
        params = self.params[scenario.id]
        impl = scenario.impls[session.engine]
        outcome = execute(scenario, session, params)
        kinds = [kind for _, kind in scenario.columns]
        found = [result(kinds, rows, scenario.ordered) for rows in outcome.results]
        access = explain(session, impl.plan(params[0])) if params else None
        return Run(outcome=outcome, results=found, hash=digest(found), access=access)

    def write(self, scenario, session, before):
        params = self.params[scenario.id]
        impl = scenario.impls[session.engine]
        found = plan(session, impl.plan(params)) if impl.plan else None
        keys = impl.keys(session, params)
        old = oracle.probe(session, self.schema, keys)
        outcome = execute(scenario, session, params)
        run = Run(outcome=outcome, probe=oracle.diff(old, oracle.probe(session, self.schema, keys), self.schema),
                  plan=found, access=None if found is None else access(session.engine, found))
        if impl.after:
            run.after = impl.after(session, params)
        if before is not None:
            run.rebuild = oracle.diff(before, oracle.snapshot(session, self.schema), self.schema)
        return run

    def labelled(self, scenario):
        return {f"{engine}/{config}": self.runs[(scenario.id, engine, config)]
                for engine in scenario.engines for config in scenario.configs}

    def problems(self, scenario):
        found = {name: [] for name in CHECKS}
        found["metadata"] = scenario.problems()
        runs = self.labelled(scenario)
        found["errors"] = [f"{label}: {run.error}" for label, run in runs.items() if run.error]
        runs = {label: run for label, run in runs.items() if not run.error}
        if not runs:
            return found
        if scenario.read:
            found["hash"] = mismatch({label: run.results for label, run in runs.items()})
            if self.size in HASHED:
                found["empty"] = [f"{label}: parameter sets {empty} return no rows" for label, run in runs.items()
                                  if (empty := [index for index, rows in enumerate(run.results) if not rows])]
            return found
        probes = {label: run.probe for label, run in runs.items()}
        found["union"] = [] if any(probes.values()) else ["no run inserted, changed or deleted a row"]
        found["probe"] = oracle.compare(probes)
        found["affected"] = differing({label: oracle.affected(probe) for label, probe in probes.items()})
        found["commits"] = differing({label: run.outcome.commits for label, run in runs.items()})
        if self.size in HASHED:
            found["rebuild"] = oracle.compare({label: run.rebuild for label, run in runs.items()})
            found["coverage"] = [f"{label}: the key probe gives {oracle.affected(run.probe)}, the rebuild "
                                 f"{oracle.affected(run.rebuild)}" for label, run in runs.items()
                                 if digest(run.probe) != digest(run.rebuild)]
        return found

    def check(self, scenario):
        found = {name: items for name, items in self.problems(scenario).items() if items}
        if found:
            pytest.fail("\n".join(f"{name}: {item}" for name, items in found.items() for item in items), pytrace=False)


def differing(values):
    if len({encode(value) for value in values.values()}) <= 1:
        return []
    return ["; ".join(f"{label} {encode(value)}" for label, value in values.items())]


def mismatch(results):
    if len({digest(found) for found in results.values()}) <= 1:
        return []
    (first, reference), *others = results.items()
    lines = []
    for label, found in others:
        index = next((index for index, (a, b) in enumerate(zip(reference, found)) if a != b), None)
        if index is None and len(reference) == len(found):
            continue
        if index is None:
            lines.append(f"{label}: {len(found)} parameter sets, {first}: {len(reference)}")
        else:
            lines.append(f"parameter set {index}: {first} {encode(reference[index])[:300]}; "
                         f"{label} {encode(found[index])[:300]}")
    return lines


def pytest_addoption(parser):
    parser.addoption("--size", choices=("XS", "S", "M", "L"), default="XS", help="Dataset size of the scenario tests")


@pytest.fixture(scope="session")
def size(request):
    return request.config.getoption("--size")


@pytest.fixture(scope="session")
def bench(request, size):
    chosen = {}
    for item in request.session.items:
        scenario = getattr(item, "callspec", None) and item.callspec.params.get("scenario")
        if isinstance(scenario, Scenario):
            chosen.setdefault(id(scenario), scenario)
    harness = Harness(size, list(chosen.values()))
    harness.run()
    return harness
