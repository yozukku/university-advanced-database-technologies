from datetime import timezone

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("entity", "text"), ("events", "int"))
STATUS = "CANCELLED"
MONTHS = """
select since, since + interval 1 month
from (select distinct date_trunc('month', a.at_) as since
      from audit_event_ a, json_each(a.changes_) c
      where a.at_ < date_trunc('month', getvariable('benchmark_t0'))
        and json_extract_string(c.value, '$.f') = 'status_' and json_extract_string(c.value, '$.new') = ?)
order by since desc
limit ?
"""
CHANGES_PG = """
select entity_, count(*)
from audit_event_
where changes_ @> jsonb_build_array(jsonb_build_object('f', 'status_', 'new', %(value)s::text))
  and at_ >= %(since)s and at_ < %(until)s
group by entity_
"""
CHANGES_MYSQL = """
select entity_, count(*)
from audit_event_
where %(value)s member of (changes_new_)
  and json_contains(changes_, json_object('f', 'status_', 'new', %(value)s))
  and at_ >= %(since)s and at_ < %(until)s
group by entity_
"""
CHANGES_MONGO = """
auditEvents.aggregate([
  {$match: {changes: {$elemMatch: {f: 'status_', new: :value}}, at: {$gte: :since, $lt: :until}}},
  {$group: {_id: '$entity', events: {$sum: 1}}}
])
"""


def months(pick):
    found = pick.db.execute(MONTHS, [STATUS, pick.count]).fetchall()
    return [{"value": STATUS, "since": since.astimezone(timezone.utc), "until": until.astimezone(timezone.utc)}
            for since, until in reversed(found)]


def pipeline(parameter):
    return [
        {"$match": {"changes": {"$elemMatch": {"f": "status_", "new": parameter["value"]}},
                    "at": {"$gte": parameter["since"], "$lt": parameter["until"]}}},
        {"$group": {"_id": "$entity", "events": {"$sum": 1}}},
    ]


def changes_pg(session, parameter):
    return session.fetch(CHANGES_PG, parameter)


def changes_mysql(session, parameter):
    return session.fetch(CHANGES_MYSQL, parameter)


def changes_mongo(session, parameter):
    return [(found["_id"], found["events"]) for found in session.handle.auditEvents.aggregate(pipeline(parameter))]


SCENARIOS = [Scenario(
    id="J4", op="R", flags=frozenset({"BA", "H1-S"}), columns=COLUMNS, select=months,
    description="Wyszukiwanie elementu tablicy JSON: zdarzenia audytu z jednego miesiąca, których lista zmian "
                "zawiera zmianę status_ na CANCELLED, policzone według encji, ×12 miesięcy",
    impls={
        "pg": Impl(CHANGES_PG, changes_pg, plan=lambda parameter: Query(CHANGES_PG, parameter)),
        "mysql": Impl(CHANGES_MYSQL, changes_mysql, plan=lambda parameter: Query(CHANGES_MYSQL, parameter)),
        "mongo": Impl(CHANGES_MONGO, changes_mongo, plan=lambda parameter: Query("auditEvents", pipeline(parameter))),
    },
)]
