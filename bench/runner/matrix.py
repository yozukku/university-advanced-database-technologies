import json
import time
import traceback
from dataclasses import dataclass

import docker

from bench.check.verify.canonical import TABLES, read_schema
from bench.check.verify.results import root
from bench.gen.profiles import load_profile
from bench.scenarios import oracle
from bench.scenarios.executor import Session, execute
from bench.scenarios.normalise import digest, result
from bench.scenarios.params import dataset, parameters
from bench.scenarios.qhash import MEASURED_RUNS, TIMEOUT_SECONDS, qhash
from bench.scenarios.registry import ENGINES, load

from . import disk, environment, limits, warmup
from .state import snapshot as state
from .state.containers import engine_container, others_running, stopped
from .store import Store

HASHED = ("XS", "S")
CONFIGS = ("idx", "base")
RUNS = tuple(range(1, MEASURED_RUNS + 1))
WARMUP_CAP_SECONDS = 24


@dataclass
class Measured:
    status: str
    nanoseconds: int
    outcome: object = None
    error: str | None = None


class Bench:
    def __init__(self, size, engines=ENGINES, chosen=None, timeout=None):
        self.size = size
        self.engines = engines
        self.timeout = timeout or TIMEOUT_SECONDS
        self.scenarios = [scenario for key, scenario in load().items() if not chosen or key in chosen]
        self.client = docker.from_env()
        self.store = Store(root(size))
        self.live = None
        self.states = {}
        self.versions = {}
        with dataset(size) as (db, profile):
            self.params = {scenario.id: parameters(scenario, db, profile) for scenario in self.scenarios}
            self.qhashes = {scenario.id: qhash(scenario, profile, self.params[scenario.id], self.timeout)
                            for scenario in self.scenarios}
            self.values = [value for value, in db.execute(warmup.CHANGED_VALUES).fetchall()]
        self.schema = read_schema(load_profile(size).destination)

    def group(self, engine, config):
        return [scenario for scenario in self.scenarios if engine in scenario.impls and config in scenario.configs]

    def state_id(self, engine, config):
        if (engine, config) not in self.states:
            self.states[(engine, config)] = state.state_id(engine, self.size, config)
        return self.states[(engine, config)]

    def key(self, scenario, engine, config):
        return {"engine": engine, "size": self.size, "config": config, "scenario": scenario.id,
                "qhash": self.qhashes[scenario.id], "state_id": self.state_id(engine, config)}

    def pending(self, scenario, engine, config):
        return self.store.pending(self.key(scenario, engine, config), RUNS)

    def status(self):
        rows = []
        for engine in self.engines:
            for config in CONFIGS:
                group = self.group(engine, config)
                if not group:
                    continue
                cells = {scenario.id: self.store.cell(self.key(scenario, engine, config)) for scenario in group}
                outstanding = [key for key, runs in cells.items() if len(runs) < len(RUNS)]
                statuses = [line["status"] for runs in cells.values() for line in runs.values()]
                rows.append((engine, config, len(group), len(group) - len(outstanding), statuses.count("timeout"),
                             statuses.count("error"), " ".join(outstanding)))
        return rows

    def run(self):
        try:
            for engine in self.engines:
                for config in CONFIGS:
                    self.configuration(engine, config)
        finally:
            self.stop()

    def configuration(self, engine, config):
        group = self.group(engine, config)
        pending = {scenario.id: self.pending(scenario, engine, config) for scenario in group}
        reads = [scenario for scenario in group if scenario.read]
        if any(pending[scenario.id][0] for scenario in reads):
            self.reads(engine, config, reads, pending)
        for scenario in group:
            if not scenario.read and pending[scenario.id][0]:
                self.writes(engine, config, scenario, *pending[scenario.id])

    def stop(self):
        if self.live:
            stopped(engine_container(self.client, self.live), kill=True)
            self.live = None

    def guard(self, engine):
        if running := others_running(self.client, engine):
            raise SystemExit(f"Another database is running: {', '.join(running)}; the {engine} run is refused")

    def restore(self, engine, config):
        self.stop()
        state.restore(engine, self.size, config)
        self.live = engine
        if engine not in self.versions:
            with Session(engine) as session:
                self.versions[engine] = environment.version(session)
            environment.record_version(root(self.size), self.size, engine, self.versions[engine])

    def manifest(self, engine, config):
        return json.loads(state.manifest_path(engine, self.size, config).read_text())

    def count_problems(self, engine, config, found=None):
        expected = dict(self.manifest(engine, config)["fingerprint"]["counts"])
        for table, entry in (found or {}).items():
            expected[table] += len(entry["inserted"]) - len(entry["deleted"])
        live = state.counts(engine)
        return [f"{table}: {live[table]:,} rows, expected {expected[table]:,}" for table in TABLES if live[table] != expected[table]]

    def line(self, scenario, engine, config, run, measured, **values):
        return {**self.key(scenario, engine, config), "run": run, "status": measured.status, "at": environment.now(),
                "nanoseconds": measured.nanoseconds, **({"error": measured.error} if measured.error else {}), **values}

    def skip(self, scenario, engine, config, runs, reason):
        for run in runs:
            self.store.append(self.line(scenario, engine, config, run, Measured("skipped", None, error=reason)))

    def timed(self, scenario, session, params):
        start = time.perf_counter_ns()
        session.deadline = time.monotonic() + self.timeout
        with limits.watchdog(session.engine, self.timeout) as dog:
            try:
                outcome = execute(scenario, session, params)
            except Exception as error:
                elapsed = time.perf_counter_ns() - start
                measured = Measured("timeout" if dog.expired(elapsed, error) else "error", elapsed,
                                    error=traceback.format_exc(limit=-4))
            else:
                if dog.expired(outcome.nanoseconds):
                    measured = Measured("timeout", outcome.nanoseconds, outcome, f"finished after the {self.timeout} s timeout")
                else:
                    measured = Measured("ok", outcome.nanoseconds, outcome)
        session.deadline = None
        if measured.status == "timeout":
            limits.settle(session.engine)
            print(f"{session.engine} {scenario.id}: timeout after {measured.nanoseconds / 1e9:.1f} s, "
                  f"no harness statement left running")
        return measured

    def reads(self, engine, config, reads, pending):
        self.restore(engine, config)
        try:
            with Session(engine, self.timeout) as session:
                warmed = warmup.run(session, warmup.script(engine, warmup.catalog(session), reads, self.values),
                                    WARMUP_CAP_SECONDS)
        except Exception:
            for scenario in reads:
                runs, _ = pending[scenario.id]
                if runs:
                    failed = Measured("error", None, error="warm-up: " + traceback.format_exc(limit=-4))
                    self.store.append(self.line(scenario, engine, config, runs[0], failed))
                    self.skip(scenario, engine, config, runs[1:], "after the failed warm-up")
            return
        print(f"{engine} {self.size} {config}: read warm-up {warmed.steps} steps in {warmed.seconds:.1f} s"
              + (f", not warmed: {', '.join(warmed.skipped)}" if warmed.skipped else ""))
        for scenario in reads:
            runs, failed = pending[scenario.id]
            if failed:
                self.skip(scenario, engine, config, runs, "after an earlier failed run")
            elif runs:
                self.read_cell(engine, config, scenario, runs, warmed.seconds)
        if problems := self.count_problems(engine, config):
            raise SystemExit(f"{engine} {self.size} {config}: row counts after the reads differ from the snapshot:\n  "
                             + "\n  ".join(problems))

    def warm(self, engine, config):
        reads = [scenario for scenario in self.group(engine, config) if scenario.read]
        self.stop()
        start = time.perf_counter()
        state.restore(engine, self.size, config)
        self.live = engine
        restored = time.perf_counter() - start
        with Session(engine, self.timeout) as session:
            warmed = warmup.run(session, warmup.script(engine, warmup.catalog(session), reads, self.values))
        self.stop()
        return restored, warmed

    def read_cell(self, engine, config, scenario, runs, warmed):
        params = self.params[scenario.id]
        kinds = [kind for _, kind in scenario.columns]
        with Session(engine, self.timeout) as session:
            for position, run in enumerate([None, *runs]):
                self.guard(engine)
                measured = self.timed(scenario, session, params)
                if run is None and measured.status == "ok":
                    continue
                run = run or runs[0]
                values = {"warmup_seconds": round(warmed, 3), "commits": 0}
                if measured.status == "ok":
                    found = [result(kinds, rows, scenario.ordered) for rows in measured.outcome.results]
                    values |= {"rows": sum(len(rows) for rows in found), "hash": digest(found)}
                elif position == 0:
                    measured.error = "discarded run: " + measured.error
                self.store.append(self.line(scenario, engine, config, run, measured, **values))
                if measured.status != "ok":
                    self.skip(scenario, engine, config, runs[runs.index(run) + 1:], f"after the {measured.status} of run {run}")
                    return
        print(f"{engine} {config} {scenario.id}: runs {', '.join(map(str, runs))} done")

    def writes(self, engine, config, scenario, runs, failed):
        for position, run in enumerate(runs):
            if failed:
                self.skip(scenario, engine, config, runs[position:], "after an earlier failed run")
                return
            line = self.write_run(engine, config, scenario, run)
            self.store.append(line)
            failed = line["status"] != "ok"
            print(f"{engine} {config} {scenario.id} run {run}: {line['status']}"
                  + (f" in {line['nanoseconds'] / 1e9:.3f} s" if line["nanoseconds"] else ""))

    def write_run(self, engine, config, scenario, run):
        impl = scenario.impls[engine]
        params = self.params[scenario.id]
        probed = self.size in HASHED or run == 1
        self.restore(engine, config)
        container = engine_container(self.client, engine)
        try:
            with Session(engine, self.timeout) as session:
                try:
                    keys = impl.keys(session, params) if probed else None
                    old = oracle.probe(session, self.schema, keys) if probed else None
                    warmed = warmup.run(session, warmup.script(engine, warmup.catalog(session), [scenario], self.values),
                                        WARMUP_CAP_SECONDS)
                    self.guard(engine)
                    before = disk.reads(session, container)
                except Exception:
                    return self.line(scenario, engine, config, run, Measured("error", None, error=traceback.format_exc(limit=-4)))
                measured = self.timed(scenario, session, params)
                values = {"warmup_seconds": round(warmed.seconds, 3)}
                if measured.status == "ok":
                    values |= {"commits": measured.outcome.commits, "driver_counts": measured.outcome.driver_counts}
                    try:
                        values["disk_reads"] = disk.delta(engine, before, disk.reads(session, container))
                        if probed:
                            found = oracle.diff(old, oracle.probe(session, self.schema, keys), self.schema)
                            affected = oracle.affected(found)
                            values |= {"affected": affected, "digests": oracle.digests(found),
                                       "rows": sum(sum(counts.values()) for counts in affected.values())}
                            if self.size in HASHED and (problems := self.count_problems(engine, config, found)):
                                measured.status, measured.error = "error", "count check: " + "; ".join(problems)
                    except Exception:
                        measured.status, measured.error = "error", traceback.format_exc(limit=-4)
                return self.line(scenario, engine, config, run, measured, **values)
        finally:
            self.stop()
