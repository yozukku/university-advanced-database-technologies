import uuid

from bson import Int64
from pymongo import UpdateOne

from bench.scenarios.params import chunks, fresh_id
from bench.scenarios.registry import Impl, Scenario

PHONES = 700_000_000
TERMS = "select max(terms_version_) from customer_"
KNOWN = "select keycloak_id_ from customer_ order by id_"
UPSERT_PG = """
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
select * from unnest(%(id)s::bigint[], %(keycloak)s::uuid[], %(phone)s::varchar[], %(terms)s::varchar[],
                     %(at)s::timestamptz[], %(at)s::timestamptz[])
on conflict (keycloak_id_) do update
set phone_ = excluded.phone_, terms_version_ = excluded.terms_version_, terms_accepted_at_ = excluded.terms_accepted_at_
"""
UPSERT_MYSQL = """
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
values (%s, %s, %s, %s, %s, %s) as new
on duplicate key update phone_ = new.phone_, terms_version_ = new.terms_version_,
                        terms_accepted_at_ = new.terms_accepted_at_
"""
UPSERT_MONGO = ("customers.bulkWrite([{updateOne: {filter: {keycloakId}, update: {$set: {phone, termsVersion, "
                "termsAcceptedAt}, $setOnInsert: {_id, createdAt}}, upsert: true}}, …])\n"
                "// jedna transakcja na partię")
UPSERT_CYPHER = """
UNWIND $rows AS row
MERGE (c:Customer {keycloakId: row.keycloak})
ON CREATE SET c.id = row.id, c.createdAt = row.at
SET c.phone = row.phone, c.termsVersion = row.terms, c.termsAcceptedAt = row.at
"""
EXISTING_PG = "select id_ from customer_ where keycloak_id_ = any(%s::uuid[])"
EXISTING_MYSQL = "select id_ from customer_ where keycloak_id_ in ({marks})"
EXISTING_CYPHER = "MATCH (c:Customer) WHERE c.keycloakId IN $keycloak RETURN c.id"
FIELDS = ("id", "keycloak", "phone", "terms", "at")


def upserts(pick):
    [(terms,)] = pick.db.execute(TERMS).fetchall()
    known = [keycloak for keycloak, in pick.db.execute(KNOWN).fetchall()]
    existing = pick.count // 2
    keycloaks = [str(key) for key in pick.rng.choice(known, existing, replace=False)]
    keycloaks += [str(uuid.UUID(bytes=pick.rng.bytes(16), version=4)) for _ in range(pick.count - existing)]
    rows = [{"id": fresh_id(n), "keycloak": keycloaks[index], "phone": f"+48{PHONES + n}", "terms": terms,
             "at": pick.t0} for n, index in enumerate(pick.rng.permutation(pick.count), start=1)]
    return chunks(rows, pick.config["batch"])


def every_keycloak(params):
    return [row["keycloak"] for batch in params for row in batch]


def touched(params, existing):
    return {"customer_": [*existing, *(row["id"] for batch in params for row in batch)]}


def keys_pg(session, params):
    return touched(params, [row[0] for row in session.fetch(EXISTING_PG, [every_keycloak(params)])])


def keys_mysql(session, params):
    keycloaks = every_keycloak(params)
    found = session.fetch(EXISTING_MYSQL.format(marks=", ".join(["%s"] * len(keycloaks))), keycloaks)
    return touched(params, [row[0] for row in found])


def keys_mongo(session, params):
    found = session.handle.customers.find({"keycloakId": {"$in": every_keycloak(params)}}, {"_id": 1})
    return touched(params, [customer["_id"] for customer in found])


def keys_cypher(session, params):
    return touched(params, [row[0] for row in session.fetch(EXISTING_CYPHER, {"keycloak": every_keycloak(params)})])


def upsert_pg(session, params):
    for batch in params:
        with session.transaction() as conn:
            columns = {field: [row[field] for row in batch] for field in FIELDS}
            session.driver_counts["customer_"] += conn.execute(UPSERT_PG, columns).rowcount


def upsert_mysql(session, params):
    for batch in params:
        with session.transaction() as cursor:
            cursor.executemany(UPSERT_MYSQL, [tuple(row[field] for field in (*FIELDS, "at")) for row in batch])
            session.driver_counts["customer_"] += cursor.rowcount


def update(row):
    return UpdateOne({"keycloakId": row["keycloak"]},
                     {"$set": {"phone": row["phone"], "termsVersion": row["terms"], "termsAcceptedAt": row["at"]},
                      "$setOnInsert": {"_id": Int64(row["id"]), "createdAt": row["at"]}},
                     upsert=True)


def upsert_mongo(session, params):
    for batch in params:
        with session.transaction() as transaction:
            done = session.handle.customers.bulk_write([update(row) for row in batch], session=transaction)
            session.driver_counts["upserted"] += done.upserted_count
            session.driver_counts["modified"] += done.modified_count


def upsert_cypher(session, params):
    for batch in params:
        with session.transaction() as tx:
            counters = tx.run(UPSERT_CYPHER, rows=batch).consume().counters
            session.driver_counts["nodes"] += counters.nodes_created
            session.driver_counts["properties"] += counters.properties_set


SCENARIOS = [Scenario(
    id="C5", op="C", select=upserts,
    description="Synchronizacja 10 000 klientów według identyfikatora Keycloak w transakcjach po 100: "
                "połowa istnieje i dostaje nowy telefon i regulamin, połowa zostaje wstawiona",
    impls={
        "pg": Impl(UPSERT_PG, upsert_pg, keys=keys_pg),
        "mysql": Impl(UPSERT_MYSQL, upsert_mysql, keys=keys_mysql),
        "mongo": Impl(UPSERT_MONGO, upsert_mongo, keys=keys_mongo),
        "neo4j": Impl(UPSERT_CYPHER, upsert_cypher, keys=keys_cypher),
    },
)]
