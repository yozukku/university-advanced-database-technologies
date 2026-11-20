import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import mysql.connector
import pytest

DDL = Path("bench/ddl/mysql")
SCRIPTS = ("base/tables.sql", "base/foreign_keys.sql", "base/indexes.sql", "base/triggers.sql", "idx/indexes.sql")
SERVER = {"host": "mysql", "user": "root", "password": "bench-root"}
DATABASE = "ddl_rules_"
T0 = datetime(2026, 11, 1)
KRAKOW = "st_geomfromtext('POINT(19.937 50.061)', 4326, 'axis-order=long-lat')"
SWAPPED = "st_geomfromtext('POINT(50.061 19.937)', 4326, 'axis-order=long-lat')"
FIXTURE = (
    f"insert into lockermat_ (id_, code_, name_, address_, location_) "
    f"values (1, 'KRK-01', 'Kraków Rynek', 'Kraków, Rynek Główny 1', {KRAKOW})",
    "insert into lockermat_cell_ (id_, lockermat_id_, number_, size_) values (1, 1, 1, 'S'), (2, 1, 2, 'S')",
    "insert into tariff_ (id_, size_, valid_from_, valid_to_, storage_price_per_day_, shipment_price_, overstay_price_per_day_) "
    "values (1, 'S', '2026-01-01', null, 15, 39, 20)",
    "insert into customer_ (id_, keycloak_id_, terms_version_, terms_accepted_at_) "
    "values (1, '00000000-0000-4000-8000-000000000001', 'demo-1', '2026-01-01')",
    "insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_, created_at_) "
    "values " + ", ".join(f"({n}, 'ORD-{n}', 1, 'STORAGE', 'S', 1, 'PAID', 15, '2026-10-31 00:15', '2026-10-31')" for n in range(1, 7)),
)
LOCK_WAIT = """
    select l.object_name, l.index_name, l.lock_mode
    from performance_schema.data_lock_waits w
    join performance_schema.data_locks l on l.engine_lock_id = w.blocking_engine_lock_id
    where w.requesting_thread_id = ps_thread_id(%s)
"""
HELD_LOCKS = "select distinct object_name, index_name from performance_schema.data_locks where thread_id = ps_thread_id(%s)"


def at(hours):
    return None if hours is None else T0 + timedelta(hours=hours)


def statements(script):
    delimiter, lines = ";", []
    for line in script.splitlines():
        if line.lower().startswith("delimiter "):
            delimiter = line.split()[1]
            continue
        lines.append(line)
        if line.rstrip().endswith(delimiter):
            statement = "\n".join(lines).rstrip().removesuffix(delimiter).strip()
            lines = []
            if statement:
                yield statement


def execute(conn, statement, params=()):
    with conn.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall() if cursor.with_rows else cursor.rowcount


@pytest.fixture(scope="module")
def schema():
    conn = mysql.connector.connect(**SERVER, autocommit=True)
    execute(conn, f"drop database if exists {DATABASE}")
    execute(conn, f"create database {DATABASE}")
    execute(conn, f"use {DATABASE}")
    for name in SCRIPTS:
        for statement in statements((DDL / name).read_text()):
            execute(conn, statement)
    tables = execute(conn, "select table_name from information_schema.tables where table_schema = %s and table_name <> 'excl_guard_'",
                     (DATABASE,))
    yield conn, [table for table, in tables]
    execute(conn, f"drop database {DATABASE}")
    conn.close()


@pytest.fixture
def connect(schema):
    admin, tables = schema
    execute(admin, "set foreign_key_checks = 0")
    for table in tables:
        execute(admin, f"delete from {table}")
    execute(admin, "set foreign_key_checks = 1")
    for statement in FIXTURE:
        execute(admin, statement)
    sessions = []

    def session():
        conn = mysql.connector.connect(**SERVER, database=DATABASE, autocommit=True)
        sessions.append(conn)
        return conn

    yield session
    for conn in sessions:
        conn.close()


@pytest.fixture
def db(connect):
    return connect()


def reservation(conn, id_, order, cell, start, end, status="BOOKED", deposited=None, collected=None):
    execute(conn, "insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_, status_, deposited_at_, "
                  "collected_at_) values (%s, %s, 'S', %s, 'STORAGE', %s, %s, %s, %s, %s)",
            (id_, order, cell, at(start), at(end), status, at(deposited), at(collected)))


def access_code(conn, id_, reservation_id, purpose, digest, start, end, status="ACTIVE"):
    execute(conn, "insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_, status_, "
                  "created_at_) values (%s, %s, %s, %s, %s, %s, %s, %s)",
            (id_, reservation_id, purpose, bytes([digest]) * 32, at(start), at(end), status, at(-24)))


def tariff(conn, id_, size, start, end):
    execute(conn, "insert into tariff_ (id_, size_, valid_from_, valid_to_, storage_price_per_day_, shipment_price_, "
                  "overstay_price_per_day_) values (%s, %s, %s, %s, 15, 39, 20)", (id_, size, start, end))


def opening(conn, id_, code, result):
    execute(conn, "insert into cell_opening_ (id_, access_code_id_, channel_, result_, requested_at_) "
                  "values (%s, %s, 'KEYPAD', %s, %s)", (id_, code, result, at(1)))


def payment(conn, id_, order, status):
    execute(conn, "insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, created_at_) "
                  "values (%s, %s, 'CHARGE', 15, %s, 'P24', %s)", (id_, order, status, at(0)))


def audit_event(conn, id_, changes, changes_new):
    execute(conn, "insert into audit_event_ (id_, at_, entity_, entity_id_, action_, actor_, changes_, changes_new_) "
                  "values (%s, %s, 'order', 1, 'STATUS', '{\"kind\": \"SYSTEM\", \"job\": \"expire\"}', %s, %s)",
            (id_, at(0), json.dumps(changes), json.dumps(changes_new)))


def rejected(action, *args, **kwargs):
    with pytest.raises(mysql.connector.Error) as caught:
        action(*args, **kwargs)
    return caught.value


def assert_exclusion(error, rule):
    assert (error.errno, error.sqlstate, error.msg) == (1644, "45000", f"excl:{rule}")


def assert_duplicate(error, key):
    assert (error.errno, error.sqlstate) == (1062, "23000")
    assert error.msg.endswith(f"for key '{key}'")


def in_background(conn, action, *args):
    outcome = {}

    def run():
        try:
            action(conn, *args)
        except mysql.connector.Error as error:
            outcome["error"] = error

    thread = threading.Thread(target=run)
    thread.start()
    return thread, outcome


def lock_wait(monitor, conn):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        waits = execute(monitor, LOCK_WAIT, (conn.connection_id,))
        if waits:
            return waits
        time.sleep(0.05)
    return []


def race(connect, first, second, *args):
    monitor, a, b = connect(), connect(), connect()
    execute(a, "start transaction")
    first(a)
    execute(b, "start transaction")
    thread, outcome = in_background(b, second, *args)
    waits = lock_wait(monitor, b)
    execute(a, "commit")
    thread.join(10)
    assert not thread.is_alive()
    execute(b, "rollback")
    return waits, outcome.get("error")


def test_tariff_no_overlap(db):
    assert_exclusion(rejected(tariff, db, 2, "S", "2027-01-01", "2028-01-01"), "tariff_no_overlap")


def test_reservation_no_double_booking(db):
    reservation(db, 1, 1, 1, 10, 12, "CANCELLED")
    reservation(db, 2, 1, 1, 10, 12)
    assert_exclusion(rejected(reservation, db, 3, 2, 1, 11, 13), "reservation_no_double_booking")


def test_reservation_actual_occupancy(db):
    reservation(db, 1, 1, 1, 10, 12, "OCCUPIED", deposited=10)
    assert_exclusion(rejected(reservation, db, 2, 2, 1, 20, 22, "OCCUPIED", deposited=20), "reservation_actual_occupancy")


def test_access_code_hmac_window(db):
    reservation(db, 1, 1, 1, 10, 12)
    reservation(db, 2, 2, 2, 10, 12)
    access_code(db, 1, 1, "DROP_OFF", 7, 10, 12)
    assert_exclusion(rejected(access_code, db, 2, 2, "DROP_OFF", 7, 11, 13), "access_code_hmac_window")


def test_access_code_active_purpose(db):
    reservation(db, 1, 1, 1, 10, 12)
    access_code(db, 1, 1, "DROP_OFF", 1, 10, 12, "REVOKED")
    access_code(db, 2, 1, "PICK_UP", 2, 10, 12)
    access_code(db, 3, 1, "DROP_OFF", 3, 10, 12)
    assert_exclusion(rejected(access_code, db, 4, 1, "DROP_OFF", 4, 11, 13), "access_code_active_purpose")


def test_reservation_leg_unique(db):
    reservation(db, 1, 1, 1, 10, 12, "CANCELLED")
    reservation(db, 2, 1, 1, 12, 14)
    assert_duplicate(rejected(reservation, db, 3, 1, 2, 14, 16), "reservation_.reservation_leg__uq")


def test_payment_pending_charge_unique(db):
    payment(db, 1, 1, "FAILED")
    payment(db, 2, 1, "PENDING")
    payment(db, 3, 2, "PENDING")
    assert_duplicate(rejected(payment, db, 4, 1, "PENDING"), "payment_.payment_pending_charge__uq")


def test_cell_opening_code_live_unique(db):
    reservation(db, 1, 1, 1, 10, 12)
    access_code(db, 1, 1, "DROP_OFF", 1, 10, 12)
    opening(db, 1, 1, "DOOR_FAILED")
    opening(db, 2, 1, "PENDING")
    assert_duplicate(rejected(opening, db, 3, 1, "OPENED"), "cell_opening_.cell_opening_code_live__uq")


def test_adjacent_intervals_are_accepted(db):
    tariff(db, 2, "S", "2024-01-01", "2025-01-01")
    tariff(db, 3, "S", "2025-01-01", "2026-01-01")
    reservation(db, 1, 1, 1, 10, 12)
    reservation(db, 3, 3, 1, 14, 16)
    reservation(db, 2, 2, 1, 12, 14)
    reservation(db, 4, 4, 2, 9, 12, "COMPLETED", deposited=10, collected=12)
    reservation(db, 6, 6, 2, 14, 16, "OCCUPIED", deposited=14)
    reservation(db, 5, 5, 2, 12, 14, "COMPLETED", deposited=12, collected=14)
    access_code(db, 1, 1, "DROP_OFF", 5, 10, 11)
    access_code(db, 3, 3, "DROP_OFF", 5, 12, 13)
    access_code(db, 2, 2, "DROP_OFF", 5, 11, 12)
    access_code(db, 4, 6, "PICK_UP", 6, 14, 15)
    access_code(db, 6, 6, "PICK_UP", 7, 16, 17)
    access_code(db, 5, 6, "PICK_UP", 8, 15, 16)
    counts = "select (select count(*) from tariff_), (select count(*) from reservation_), (select count(*) from access_code_)"
    assert execute(db, counts) == [(3, 6, 6)]


def test_overlapping_booking_waits_for_the_cell_lock(connect):
    def book(conn):
        execute(conn, "select id_ from lockermat_cell_ where id_ = 1 for update")
        reservation(conn, 1, 1, 1, 10, 12)

    waits, error = race(connect, book, reservation, 2, 2, 1, 11, 13)
    assert waits == [("lockermat_cell_", "PRIMARY", "X,REC_NOT_GAP")]
    assert_exclusion(error, "reservation_no_double_booking")


def test_cancelling_a_live_leg_probes_nothing(connect):
    holder, session = connect(), connect()
    reservation(session, 1, 1, 1, 10, 12)
    reservation(session, 2, 2, 1, 12, 14)
    execute(holder, "start transaction")
    execute(holder, "select id_ from lockermat_cell_ where id_ = 1 for update")
    execute(session, "set innodb_lock_wait_timeout = 1")
    execute(session, "start transaction")
    assert execute(session, "update reservation_ set status_ = 'CANCELLED' where id_ = 1") == 1
    held = set(execute(session, HELD_LOCKS, (session.connection_id,)))
    assert held == {("reservation_", None), ("reservation_", "PRIMARY")}
    assert rejected(execute, session, "update reservation_ set to_ = %s where id_ = 2", (at(15),)).errno == 1205
    execute(session, "rollback")
    execute(holder, "rollback")


def test_first_tariff_of_a_size_waits_for_the_guard(connect):
    def first(conn):
        tariff(conn, 2, "M", "2026-01-01", None)

    waits, error = race(connect, first, tariff, 3, "M", "2026-06-01", "2027-01-01")
    assert waits == [("excl_guard_", "PRIMARY", "X,REC_NOT_GAP")]
    assert_exclusion(error, "tariff_no_overlap")


def test_first_hmac_window_waits_for_the_guard(connect):
    def first(conn):
        access_code(conn, 1, 1, "DROP_OFF", 9, 10, 12)

    setup = connect()
    reservation(setup, 1, 1, 1, 10, 12)
    reservation(setup, 2, 2, 2, 10, 12)
    waits, error = race(connect, first, access_code, 2, 2, "DROP_OFF", 9, 11, 13)
    assert waits == [("excl_guard_", "PRIMARY", "X,REC_NOT_GAP")]
    assert_exclusion(error, "access_code_hmac_window")


def test_location_check_reads_longitude_and_latitude(db):
    latitude, longitude = execute(db, "select st_latitude(location_), st_longitude(location_) from lockermat_ where id_ = 1")[0]
    assert round(latitude, 2) == 50.06 and round(longitude, 2) == 19.94
    swapped = f"insert into lockermat_ (id_, code_, name_, address_, location_) values (2, 'KRK-02', 'Odwrócony', 'Kraków', {SWAPPED})"
    error = rejected(execute, db, swapped)
    assert (error.errno, error.msg) == (3819, "Check constraint 'lockermat_location__ck' is violated.")


def test_jx2_keeps_json_null_and_rejects_long_values(db):
    assert execute(db, "select @@restrict_fk_on_non_standard_key") == [(1,)]
    jx2 = "select count(*) from information_schema.statistics where table_schema = %s and index_name = 'jx2__idx'"
    assert execute(db, jx2, (DATABASE,)) == [(1,)]
    audit_event(db, 1, [{"f": "status_", "old": "PAID", "new": "CANCELLED"}, {"f": "closed_at_", "old": None, "new": None}],
                ["CANCELLED"])
    audit_event(db, 2, [{"f": "status_", "old": "PAID", "new": "x" * 32}], ["x" * 32])
    stored = execute(db, "select json_type(json_extract(changes_, '$[1].new')), changes_new_ from audit_event_ where id_ = 1")
    assert stored == [("NULL", '["CANCELLED"]')]
    assert execute(db, "select id_ from audit_event_ where 'CANCELLED' member of (changes_new_)") == [(1,)]
    assert rejected(audit_event, db, 3, [{"f": "status_", "old": "PAID", "new": None}], [None]).errno == 3903
    assert rejected(audit_event, db, 4, [{"f": "status_", "old": "PAID", "new": "x" * 33}], ["x" * 33]).errno == 3907
