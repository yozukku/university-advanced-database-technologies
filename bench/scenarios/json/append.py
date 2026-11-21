import json
from datetime import timedelta

from bson import Int64

from bench.check.verify.canonical import string_values
from bench.scenarios.params import chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

SOURCE_IDS = "select id_ from audit_event_ order by id_"
SOURCE = """
select entity_, entity_id_, action_, actor_, changes_ from audit_event_
where id_ in (select unnest(?::bigint[]))
order by id_
"""
APPEND_PG = """
insert into audit_event_ (id_, at_, entity_, entity_id_, action_, actor_, changes_)
select * from unnest(%(id)s::bigint[], %(at)s::timestamptz[], %(entity)s::varchar[], %(entity_id)s::bigint[],
                     %(action)s::varchar[], %(actor)s::jsonb[], %(changes)s::jsonb[])
"""
APPEND_MYSQL = """
insert into audit_event_ (id_, at_, entity_, entity_id_, action_, actor_, changes_, changes_new_)
values (%s, %s, %s, %s, %s, %s, %s, %s)
"""
APPEND_MONGO = ("auditEvents.insertMany([{_id, at, entity, entityId, action, actor: {kind, …}, "
                "changes: [{f, old, new}]}, …]) in one transaction per batch")
DERIVED_MYSQL = "select changes_, changes_new_ from audit_event_ where id_ between %s and %s"
FIELDS = ("id", "at", "entity", "entity_id", "action")


def events(pick):
    ids = pick.db.execute(SOURCE_IDS).fetchnumpy()["id_"]
    chosen = sorted(pick.rng.choice(ids, pick.count, replace=False).tolist())
    rows = [{"id": fresh_id(n), "at": pick.t0 + timedelta(milliseconds=n), "entity": entity, "entity_id": entity_id,
             "action": action, "actor": json.loads(actor), "changes": None if changes is None else json.loads(changes)}
            for n, (entity, entity_id, action, actor, changes)
            in enumerate(pick.db.execute(SOURCE, [chosen]).fetchall(), start=1)]
    return chunks(rows, pick.config["batch"])


def keys(session, params):
    return {"audit_event_": [row["id"] for batch in params for row in batch]}


def text(value):
    return None if value is None else json.dumps(value, ensure_ascii=False)


def new_values(changes):
    return None if changes is None else [change["new"] for change in changes if isinstance(change.get("new"), str)]


def append_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            columns = {field: [row[field] for row in batch] for field in FIELDS}
            columns |= {field: [text(row[field]) for row in batch] for field in ("actor", "changes")}
            session.driver_counts["audit_event_"] += conn.execute(APPEND_PG, columns).rowcount


def append_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.executemany(APPEND_MYSQL, [(*(row[field] for field in FIELDS), text(row["actor"]),
                                               text(row["changes"]), text(new_values(row["changes"])))
                                              for row in batch])
            session.driver_counts["audit_event_"] += cursor.rowcount


def document(row):
    found = {"_id": Int64(row["id"]), "at": row["at"], "entity": row["entity"], "entityId": Int64(row["entity_id"]),
             "action": row["action"], "actor": row["actor"]}
    return found if row["changes"] is None else found | {"changes": row["changes"]}


def append_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.auditEvents.insert_many([document(row) for row in batch], session=transaction)
            session.driver_counts["auditEvents"] += len(done.inserted_ids)


def derived_mysql(session, params):
    ids = keys(session, params)["audit_event_"]
    found = session.fetch(DERIVED_MYSQL, (min(ids), max(ids)))
    wrong = sum(1 for changes, derived in found
                if (None if derived is None else json.loads(derived)) != string_values(changes))
    return {"rows": len(found), "wrong": wrong}


SCENARIOS = [Scenario(
    id="J1", op="C", select=events, flags=frozenset({"BA", "H1-I"}),
    description="Dopisanie 10 000 zdarzeń audytu (migawka aktora i lista zmian w JSON) partiami po 1000 "
                "w jednej transakcji na partię; rodzaje aktorów i zmiany jak w danych",
    impls={
        "pg": Impl(APPEND_PG, append_pg, keys=keys),
        "mysql": Impl(APPEND_MYSQL, append_mysql, keys=keys, after=derived_mysql),
        "mongo": Impl(APPEND_MONGO, append_mongo, keys=keys),
    },
)]
