import threading
import time
from contextlib import contextmanager, nullcontext

import mysql.connector
import psycopg
import pymongo
from neo4j import GraphDatabase

from bench.load.mongo import loader as mongo_loader
from bench.load.mysql import loader as mysql_loader
from bench.load.neo4j import loader as neo4j_loader
from bench.load.pg import loader as pg_loader
from bench.scenarios.executor import APP

SETTLE_SECONDS = 60
REPEAT_SECONDS = 1
PG_HARNESS = """
    select pid from pg_stat_activity
    where datname = current_database() and pid <> pg_backend_pid() and backend_type = 'client backend'
"""
PG_BUSY = PG_HARNESS + " and state <> 'idle'"
MYSQL_HARNESS = "select id from performance_schema.processlist where db = %s and id <> connection_id()"
MYSQL_BUSY = """
    select count(*) from performance_schema.processlist p
    where p.db = %s and p.id <> connection_id()
      and (p.command <> 'Sleep' or exists (select 1 from information_schema.innodb_trx t where t.trx_mysql_thread_id = p.id))
"""
MONGO_HARNESS = [{"$currentOp": {"allUsers": True, "idleSessions": True}},
                 {"$match": {"appName": APP, "command.hello": {"$exists": False}}}]
NEO4J_HARNESS = """
    SHOW TRANSACTIONS YIELD transactionId, currentQuery
    WHERE NOT trim(currentQuery) STARTS WITH 'SHOW TRANSACTIONS' AND NOT trim(currentQuery) STARTS WITH 'TERMINATE TRANSACTIONS'
    RETURN transactionId
"""


def pg_harness(busy):
    with psycopg.connect(f"{pg_loader.SERVER} dbname={pg_loader.DATABASE}", autocommit=True) as conn:
        found = [pid for pid, in conn.execute(PG_BUSY if busy else PG_HARNESS)]
        if not busy:
            for pid in found:
                conn.execute("select pg_terminate_backend(%s)", (pid,))
        return len(found)


def mysql_harness(busy):
    with mysql.connector.connect(**mysql_loader.SERVER) as conn, conn.cursor() as cursor:
        if busy:
            return mysql_loader.fetch(cursor, MYSQL_BUSY, (mysql_loader.DATABASE,))[0][0]
        found = [thread for thread, in mysql_loader.fetch(cursor, MYSQL_HARNESS, (mysql_loader.DATABASE,))]
        for thread in found:
            try:
                cursor.execute(f"kill {int(thread)}")
            except mysql.connector.Error:
                pass
        return len(found)


def mongo_harness(busy):
    with mongo_loader.connect() as client:
        found = list(client.admin.aggregate(MONGO_HARNESS))
        if not busy:
            for operation in found:
                if "opid" in operation:
                    client.admin.command("killOp", op=operation["opid"])
                if "lsid" in operation:
                    client.admin.command("killSessions", [{"id": operation["lsid"]["id"]}])
        return len(found)


def neo4j_harness(busy):
    with (GraphDatabase.driver(neo4j_loader.URI, auth=neo4j_loader.AUTH, notifications_min_severity="OFF") as driver,
          driver.session(database="neo4j") as session):
        found = [transaction for transaction, in session.run(NEO4J_HARNESS).values()]
        if found and not busy:
            session.run("TERMINATE TRANSACTIONS $ids", ids=found).consume()
        return len(found)


HARNESS = {"pg": pg_harness, "mysql": mysql_harness, "mongo": mongo_harness, "neo4j": neo4j_harness}


def interrupt(engine):
    return HARNESS[engine](busy=False)


def busy(engine):
    return HARNESS[engine](busy=True)


def settle(engine):
    deadline = time.monotonic() + SETTLE_SECONDS
    while True:
        interrupt(engine)
        left = busy(engine)
        if not left:
            return
        if time.monotonic() > deadline:
            raise RuntimeError(f"{engine}: {left} harness statements are still running after the timeout")
        time.sleep(1)


class Watchdog(threading.Thread):
    def __init__(self, engine, seconds):
        super().__init__(daemon=True)
        self.engine = engine
        self.seconds = seconds
        self.fired = False
        self.done = threading.Event()

    def run(self):
        if self.done.wait(self.seconds):
            return
        self.fired = True
        while not self.done.is_set():
            try:
                interrupt(self.engine)
            except Exception:
                pass
            self.done.wait(REPEAT_SECONDS)

    def expired(self, nanoseconds, error=None):
        return self.fired or nanoseconds >= self.seconds * 1e9 or bool(getattr(error, "timeout", False))


@contextmanager
def watchdog(engine, seconds):
    dog = Watchdog(engine, seconds)
    dog.start()
    try:
        with pymongo.timeout(seconds) if engine == "mongo" else nullcontext():
            yield dog
    finally:
        dog.done.set()
        dog.join()
