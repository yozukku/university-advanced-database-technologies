import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass

import mysql.connector
import psycopg
from neo4j import GraphDatabase, Query
from pymongo import MongoClient

from bench.load.mongo import loader as mongo_loader
from bench.load.neo4j import loader as neo4j_loader
from bench.load.pg import loader as pg_loader

MYSQL = {"host": "mysql", "user": "bench", "password": "bench", "database": "bagazomat", "autocommit": True}
APP = "ztb-bench"


@dataclass
class Outcome:
    nanoseconds: int
    commits: int
    driver_counts: dict
    results: list | None


class Session:
    def __init__(self, engine, timeout=None):
        self.engine = engine
        self.timeout = timeout
        self.deadline = None
        self.commits = 0
        self.driver_counts = Counter()
        if engine == "pg":
            self.handle = psycopg.connect(f"{pg_loader.SERVER} dbname={pg_loader.DATABASE}", autocommit=True)
            if timeout:
                self.handle.execute(f"set statement_timeout = {round(timeout * 1000)}")
        elif engine == "mysql":
            self.handle = mysql.connector.connect(**MYSQL)
            if timeout:
                self.fetch(f"set session max_execution_time = {round(timeout * 1000)}")
        elif engine == "mongo":
            self.client = MongoClient(mongo_loader.URI, w=1, journal=True, appname=APP)
            self.handle = self.client[mongo_loader.DATABASE]
        else:
            self.graph = GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF")
            self.handle = self.graph.session(database="neo4j")

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.close()

    def close(self):
        if self.engine == "mongo":
            self.client.close()
        elif self.engine == "neo4j":
            self.handle.close()
            self.graph.close()
        else:
            self.handle.close()

    def check(self):
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TimeoutError("the run passed its timeout")

    def fetch(self, text, params=None):
        self.check()
        if self.engine == "pg":
            return self.handle.execute(text, params).fetchall()
        if self.engine == "mysql":
            with self.handle.cursor() as cursor:
                cursor.execute(text, params)
                return cursor.fetchall() if cursor.with_rows else []
        if self.engine == "neo4j":
            return self.handle.run(Query(text, timeout=self.timeout), params).values()
        raise TypeError("MongoDB has no query text; use the handle")

    @contextmanager
    def transaction(self):
        self.check()
        if self.engine == "pg":
            with self.handle.transaction():
                yield self.handle
        elif self.engine == "mysql":
            self.handle.start_transaction()
            cursor = self.handle.cursor()
            try:
                yield cursor
                self.handle.commit()
            except BaseException:
                self.handle.rollback()
                raise
            finally:
                cursor.close()
        elif self.engine == "mongo":
            with self.client.start_session() as session, session.start_transaction():
                yield session
        else:
            with self.handle.begin_transaction(timeout=self.timeout) as tx:
                yield tx
                tx.commit()
        self.commits += 1


def execute(scenario, session, params):
    impl = scenario.impls[session.engine]
    session.commits = 0
    session.driver_counts.clear()
    start = time.perf_counter_ns()
    if scenario.read:
        results = [impl.run(session, parameter) for parameter in params]
    else:
        impl.run(session, params)
        results = None
    elapsed = time.perf_counter_ns() - start
    return Outcome(elapsed, session.commits, dict(session.driver_counts), results)
