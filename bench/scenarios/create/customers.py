import uuid

from bson import Int64

from bench.scenarios.params import chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

PHONES = 600_000_000
TERMS = "select max(terms_version_) from customer_"
REGISTER_PG = """
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
select * from unnest(%(id)s::bigint[], %(keycloak)s::uuid[], %(phone)s::varchar[], %(terms)s::varchar[],
                     %(at)s::timestamptz[], %(at)s::timestamptz[])
"""
REGISTER_MYSQL = """
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
values (%s, %s, %s, %s, %s, %s)
"""
REGISTER_MONGO = ("customers.insertMany([{_id, keycloakId, phone, termsVersion, termsAcceptedAt, createdAt}, …]) "
                  "in one transaction per batch")
REGISTER_CYPHER = """
UNWIND $rows AS row
CREATE (:Customer {id: row.id, keycloakId: row.keycloak, phone: row.phone, termsVersion: row.terms,
                   termsAcceptedAt: row.at, createdAt: row.at})
"""
FIELDS = ("id", "keycloak", "phone", "terms", "at")


def registrations(pick):
    [(terms,)] = pick.db.execute(TERMS).fetchall()
    rows = [{"id": fresh_id(n), "keycloak": str(uuid.UUID(bytes=pick.rng.bytes(16), version=4)),
             "phone": f"+48{PHONES + n}", "terms": terms, "at": pick.t0} for n in range(1, pick.count + 1)]
    return chunks(rows, pick.config["batch"])


def keys(session, params):
    return {"customer_": [row["id"] for batch in params for row in batch]}


def register_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            columns = {field: [row[field] for row in batch] for field in FIELDS}
            session.driver_counts["customer_"] += conn.execute(REGISTER_PG, columns).rowcount


def register_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.executemany(REGISTER_MYSQL, [tuple(row[field] for field in (*FIELDS, "at")) for row in batch])
            session.driver_counts["customer_"] += cursor.rowcount


def document(row):
    return {"_id": Int64(row["id"]), "keycloakId": row["keycloak"], "phone": row["phone"], "termsVersion": row["terms"],
            "termsAcceptedAt": row["at"], "createdAt": row["at"]}


def register_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.customers.insert_many([document(row) for row in batch], session=transaction)
            session.driver_counts["customers"] += len(done.inserted_ids)


def register_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(REGISTER_CYPHER, rows=batch).consume().counters.nodes_created


SCENARIOS = [Scenario(
    id="C1", op="C", select=registrations,
    description="Rejestracja 10 000 nowych klientów w transakcjach po 100 (wielowierszowy INSERT, "
                "unikalny identyfikator Keycloak)",
    impls={
        "pg": Impl(REGISTER_PG, register_pg, keys=keys),
        "mysql": Impl(REGISTER_MYSQL, register_mysql, keys=keys),
        "mongo": Impl(REGISTER_MONGO, register_mongo, keys=keys),
        "neo4j": Impl(REGISTER_CYPHER, register_cypher, keys=keys),
    },
)]
