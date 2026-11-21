import hashlib
import hmac
import json
from collections import defaultdict

from pymongo import UpdateMany

from bench.scenarios.explain import Query
from bench.scenarios.json.person_events import persons
from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

TARGETS_PG = """
select id_, actor_ ->> 'email'
from audit_event_
where actor_ ->> 'email' = any(%(emails)s) or actor_ ->> 'phone' = any(%(phones)s)
order by id_
"""
TARGETS_MYSQL = """
select id_, actor_ ->> '$.email'
from audit_event_
where cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin in ({emails})
   or cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin in ({phones})
order by id_
"""
PSEUDONYMISE_PG = """
update audit_event_ a
set actor_ = case when t.pseudonym is null then a.actor_
                  else jsonb_set(a.actor_, '{email}', to_jsonb(t.pseudonym)) end - 'name' - 'phone'
from unnest(%(id)s::bigint[], %(pseudonym)s::text[]) as t (id_, pseudonym)
where a.id_ = t.id_
"""
PSEUDONYMISE_MYSQL = """
update audit_event_ a
join json_table(%s, '$[*]' columns (id_ bigint path '$[0]', pseudonym varchar(64) path '$[1]')) t on t.id_ = a.id_
set a.actor_ = json_remove(json_replace(a.actor_, '$.email', t.pseudonym), '$.name', '$.phone')
"""
TARGETS_MONGO = """
auditEvents.find({$or: [{'actor.email': {$in: :emails}}, {'actor.phone': {$in: :phones}}]}, {'actor.email': 1})
"""
PSEUDONYMISE_MONGO = """
auditEvents.bulkWrite([
  {updateMany: {filter: {_id: {$in: <zdarzenia z tym e-mailem>}},
                update: {$set: {'actor.email': :pseudonym}, $unset: {'actor.name': '', 'actor.phone': ''}}}}, …,
  {updateMany: {filter: {_id: {$in: <zdarzenia bez e-maila>}}, update: {$unset: {'actor.name': '', 'actor.phone': ''}}}}
])
// jedna transakcja na partię
"""
GONE = {"actor.name": "", "actor.phone": ""}


def forgotten(pick):
    chosen = persons(pick)
    return {"emails": [person["email"] for person in chosen if person["email"]],
            "phones": [person["phone"] for person in chosen if person["phone"]],
            "key": pick.rng.bytes(32).hex(), "batch": pick.config["batch"]}


def pseudonym(key, email):
    return hmac.new(bytes.fromhex(key), email.encode(), hashlib.sha256).hexdigest()


def pseudonymised(params, targets):
    return chunks([(identifier, None if email is None else pseudonym(params["key"], email))
                   for identifier, email in targets], params["batch"])


def marks(values):
    return ", ".join(["%s"] * len(values))


def targets_pg(session, params):
    return session.fetch(TARGETS_PG, {"emails": params["emails"], "phones": params["phones"]})


def targets_mysql(session, params):
    text = TARGETS_MYSQL.format(emails=marks(params["emails"]), phones=marks(params["phones"]))
    return session.fetch(text, [*params["emails"], *params["phones"]])


def matching(params):
    return {"$or": [{"actor.email": {"$in": params["emails"]}}, {"actor.phone": {"$in": params["phones"]}}]}


def targets_mongo(session, params):
    return sorted((found["_id"], found["actor"].get("email"))
                  for found in session.handle.auditEvents.find(matching(params), {"actor.email": 1}))


def keyed(targets):
    def keys(session, params):
        return {"audit_event_": [identifier for identifier, _ in targets(session, params)]}
    return keys


def left(targets):
    def after(session, params):
        return {"left": len(targets(session, params))}
    return after


def forget_pg(session, params):
    for batch in pseudonymised(params, targets_pg(session, params)):
        with session.transaction() as conn:
            done = conn.execute(PSEUDONYMISE_PG, {"id": [identifier for identifier, _ in batch],
                                                  "pseudonym": [value for _, value in batch]})
            session.driver_counts["audit_event_"] += done.rowcount


def forget_mysql(session, params):
    for batch in pseudonymised(params, targets_mysql(session, params)):
        with session.transaction() as cursor:
            rows = [[identifier] if value is None else [identifier, value] for identifier, value in batch]
            cursor.execute(PSEUDONYMISE_MYSQL, [json.dumps(rows)])
            session.driver_counts["audit_event_"] += cursor.rowcount


def updates(batch):
    groups = defaultdict(list)
    for identifier, value in batch:
        groups[value].append(identifier)
    return [UpdateMany({"_id": {"$in": ids}}, {"$unset": GONE} | ({} if value is None else {"$set": {"actor.email": value}}))
            for value, ids in groups.items()]


def forget_mongo(session, params):
    for batch in pseudonymised(params, targets_mongo(session, params)):
        with session.transaction() as transaction:
            done = session.handle.auditEvents.bulk_write(updates(batch), session=transaction)
            session.driver_counts["auditEvents"] += done.modified_count


def mysql_plan(params):
    text = TARGETS_MYSQL.format(emails=marks(params["emails"]), phones=marks(params["phones"]))
    return Query(text, [*params["emails"], *params["phones"]])


SCENARIOS = [Scenario(
    id="J5", op="U", flags=frozenset({"BA"}), select=forgotten,
    description="RODO art. 17: pseudonimizacja 100 osób (klient: e-mail i telefon, odbiorca: telefon) we wszystkich "
                "ich zdarzeniach audytu: e-mail zastąpiony skrótem HMAC-SHA256 z kluczem, imię i telefon usunięte "
                "z migawki aktora, partiami po 5000 zdarzeń",
    impls={
        "pg": Impl(f"{TARGETS_PG.strip()};\n{PSEUDONYMISE_PG}", forget_pg, keys=keyed(targets_pg), after=left(targets_pg),
                   plan=lambda params: Query(TARGETS_PG, {"emails": params["emails"], "phones": params["phones"]})),
        "mysql": Impl(f"{TARGETS_MYSQL.format(emails=':emails', phones=':phones').strip()};\n{PSEUDONYMISE_MYSQL}",
                      forget_mysql, keys=keyed(targets_mysql), after=left(targets_mysql), plan=mysql_plan),
        "mongo": Impl(f"{TARGETS_MONGO.strip()};\n{PSEUDONYMISE_MONGO}", forget_mongo, keys=keyed(targets_mongo),
                      after=left(targets_mongo), plan=lambda params: Query("auditEvents", matching(params))),
    },
)]
