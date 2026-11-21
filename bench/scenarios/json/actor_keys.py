from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("kind", "text"), ("events", "int"), ("with_email", "int"), ("name_or_phone_only", "int"))
KEYS_PG = """
select actor_ ->> 'kind', count(*),
       count(*) filter (where actor_ ? 'email'),
       count(*) filter (where actor_ ?| array['name', 'phone'] and not actor_ ? 'email')
from audit_event_
group by 1
"""
KEYS_MYSQL = """
select actor_ ->> '$.kind', count(*),
       sum(json_contains_path(actor_, 'one', '$.email')),
       sum(json_contains_path(actor_, 'one', '$.name', '$.phone') and not json_contains_path(actor_, 'one', '$.email'))
from audit_event_
group by 1
"""
KEYS_MONGO = """
auditEvents.aggregate([
  {$group: {_id: '$actor.kind', events: {$sum: 1},
            withEmail: {$sum: {$cond: [{$ne: [{$type: '$actor.email'}, 'missing']}, 1, 0]}},
            nameOrPhoneOnly: {$sum: {$cond: [{$and: [{$not: [{$ne: [{$type: '$actor.email'}, 'missing']}]},
                                                     {$or: [{$ne: [{$type: '$actor.name'}, 'missing']},
                                                            {$ne: [{$type: '$actor.phone'}, 'missing']}]}]}, 1, 0]}}}}
])
"""


def present(key):
    return {"$ne": [{"$type": f"$actor.{key}"}, "missing"]}


PIPELINE = [{"$group": {
    "_id": "$actor.kind", "events": {"$sum": 1},
    "withEmail": {"$sum": {"$cond": [present("email"), 1, 0]}},
    "nameOrPhoneOnly": {"$sum": {"$cond": [
        {"$and": [{"$not": [present("email")]}, {"$or": [present("name"), present("phone")]}]}, 1, 0]}},
}}]


def whole_table(pick):
    return [{}] * pick.count


def kinds_pg(session, parameter):
    return session.fetch(KEYS_PG)


def kinds_mysql(session, parameter):
    return session.fetch(KEYS_MYSQL)


def kinds_mongo(session, parameter):
    return [(found["_id"], found["events"], found["withEmail"], found["nameOrPhoneOnly"])
            for found in session.handle.auditEvents.aggregate(PIPELINE)]


SCENARIOS = [Scenario(
    id="J3", op="R", columns=COLUMNS, select=whole_table,
    description="Istnienie kluczy JSON: liczba zdarzeń audytu na rodzaj aktora, w tym z e-mailem "
                "i tylko z imieniem lub telefonem (cała tabela)",
    impls={
        "pg": Impl(KEYS_PG, kinds_pg, plan=lambda parameter: Query(KEYS_PG)),
        "mysql": Impl(KEYS_MYSQL, kinds_mysql, plan=lambda parameter: Query(KEYS_MYSQL)),
        "mongo": Impl(KEYS_MONGO, kinds_mongo, plan=lambda parameter: Query("auditEvents", PIPELINE)),
    },
)]
