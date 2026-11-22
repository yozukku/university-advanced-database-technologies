import json
import sys
import time
import types
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from bench.check.verify.results import root
from bench.runner import environment, warmup
from bench.runner.matrix import WARMUP_CAP_SECONDS, Bench
from bench.scenarios.create.booking import PICK_MYSQL
from bench.scenarios.executor import Session, execute


def describe(bench):
    environment.record(root(bench.size), bench.size, environment.describe(bench.client, bench.timeout))


def order(size, engine, scenarios, configs):
    bench = Bench(size, (engine,), set(scenarios))
    with environment.lock(root(size), bench.client):
        describe(bench)
        try:
            for scenario in bench.scenarios:
                for config in configs:
                    bench.configuration(engine, config, [scenario])
        finally:
            bench.stop()


def idx_only(size, pairs):
    engines = sorted({engine for engine, _ in pairs})
    bench = Bench(size, tuple(engines), {scenario for _, scenario in pairs})
    with environment.lock(root(size), bench.client):
        describe(bench)
        try:
            for engine, key in pairs:
                [scenario] = [s for s in bench.scenarios if s.id == key]
                bench.configuration(engine, "idx", [scenario])
        finally:
            bench.stop()


class Timed:
    def __init__(self, cursor, stats):
        self.cursor = cursor
        self.stats = stats

    def label(self, text):
        return " ".join(text.split())[:48]

    def execute(self, text, params=None):
        start = time.perf_counter_ns()
        self.cursor.execute(text, params)
        self.stats[self.label(text)] += time.perf_counter_ns() - start

    def executemany(self, text, rows):
        start = time.perf_counter_ns()
        self.cursor.executemany(text, rows)
        self.stats[self.label(text)] += time.perf_counter_ns() - start

    def __getattr__(self, name):
        return getattr(self.cursor, name)


def explain(session, text, params):
    with session.handle.cursor() as cursor:
        cursor.execute("explain analyze " + text, params)
        return [row[0] for row in cursor.fetchall()]


OVERLAP = """
select count(*) from reservation_ force index (reservation_cell_from__idx)
where cell_id_ = %(cell)s and from_ < %(to)s and to_ > %(from)s and status_ in ('BOOKED', 'OCCUPIED')
"""


def profile(size, config, key, out):
    bench = Bench(size, ("mysql",), {key})
    [scenario] = bench.scenarios
    params = bench.params[key]
    report = {"size": size, "config": config, "scenario": key}
    with environment.lock(root(size), bench.client):
        describe(bench)
        try:
            bench.restore("mysql", config)
            with Session("mysql", bench.timeout) as session:
                warmup.run(session, warmup.script("mysql", warmup.catalog(session), [scenario], bench.values),
                           WARMUP_CAP_SECONDS)
                first = {k: v for k, v in params[0][0].items() if not isinstance(v, list)}
                if key == "C3":
                    report["pick_first"] = explain(session, PICK_MYSQL.replace("for update of c skip locked", ""), first)
                stats = defaultdict(int)

                @contextmanager
                def transaction(self):
                    self.handle.start_transaction()
                    cursor = Timed(self.handle.cursor(), stats)
                    try:
                        yield cursor
                        start = time.perf_counter_ns()
                        self.handle.commit()
                        stats["commit"] += time.perf_counter_ns() - start
                    except BaseException:
                        self.handle.rollback()
                        raise
                    finally:
                        cursor.cursor.close()
                    self.commits += 1

                session.transaction = types.MethodType(transaction, session)
                outcome = execute(scenario, session, params)
                report["total_ms"] = round(outcome.nanoseconds / 1e6, 1)
                report["parts_ms"] = {k: round(v / 1e6, 1) for k, v in sorted(stats.items(), key=lambda i: -i[1])}
                if key == "C3":
                    last = {k: v for k, v in params[-1][-1].items() if not isinstance(v, list)}
                    report["pick_last"] = explain(session, PICK_MYSQL.replace("for update of c skip locked", ""), last)
                    cell = session.fetch("select cell_id_ from reservation_ where id_ = %s", (last["leg"],))[0][0]
                    report["overlap_last"] = explain(session, OVERLAP, last | {"cell": cell})
                    lockers = {b["locker"] for batch in params for b in batch}
                    report["bookings_per_locker"] = round(sum(len(batch) for batch in params) / len(lockers), 2)
                    report["cells_per_locker_size"] = session.fetch(
                        "select avg(n) from (select lockermat_id_, size_, count(*) n from lockermat_cell_ "
                        "where status_ = 'IN_SERVICE' group by 1, 2) x")[0][0].__float__()
                    report["reservations_per_cell"] = session.fetch(
                        "select (select count(*) from reservation_) / (select count(*) from lockermat_cell_)")[0][0].__float__()
        finally:
            bench.stop()
    Path(out).write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k in ("size", "config", "scenario", "total_ms", "parts_ms")}))


if __name__ == "__main__":
    command, *rest = sys.argv[1:]
    if command == "order":
        size, engine, scenarios, configs = rest
        order(size, engine, scenarios.split(","), configs.split(","))
    elif command == "idx":
        size, pairs = rest
        idx_only(size, [tuple(pair.split(":")) for pair in pairs.split(",")])
    else:
        size, config, key, out = rest
        profile(size, config, key, out)
