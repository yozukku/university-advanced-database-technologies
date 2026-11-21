from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("id", "int"), ("at", "ms"), ("entity", "text"), ("entity_id", "int"), ("action", "text"),
           ("actor", "json"), ("changes", "json"))
CUSTOMERS = """
select json_extract_string(a.actor_, '$.email'), c.phone_
from audit_event_ a
join customer_ c on c.keycloak_id_ = json_extract_string(a.actor_, '$.keycloak_id')
where json_extract_string(a.actor_, '$.kind') = 'CUSTOMER'
group by all
having count(*) > 1
order by 1
"""
RECIPIENTS = """
select null, json_extract_string(actor_, '$.phone')
from audit_event_
where json_extract_string(actor_, '$.kind') = 'RECIPIENT'
group by 2
having count(*) > 1
order by 2
"""
PERSON_PG = """
select id_, at_, entity_, entity_id_, action_, actor_, changes_
from audit_event_
where actor_ ->> 'email' = %(email)s or actor_ ->> 'phone' = %(phone)s
order by at_, id_
"""
PERSON_MYSQL = """
select id_, at_, entity_, entity_id_, action_, actor_, changes_
from audit_event_
where cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin = %(email)s
   or cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin = %(phone)s
order by at_, id_
"""
PERSON_MONGO = """
auditEvents.aggregate([
  {$match: {$or: [{'actor.email': :email}, {'actor.phone': :phone}]}},
  {$sort: {at: 1, _id: 1}}
])
// nieznany e-mail lub telefon pomija swój warunek w $or
"""


def persons(pick):
    customers = pick.db.execute(CUSTOMERS).fetchall()
    recipients = pick.db.execute(RECIPIENTS).fetchall()
    half = pick.count // 2
    chosen = ([customers[index] for index in pick.rng.choice(len(customers), half, replace=False)]
              + [recipients[index] for index in pick.rng.choice(len(recipients), pick.count - half, replace=False)])
    return [{"email": email, "phone": phone} for email, phone in chosen]


def pipeline(parameter):
    known = [{f"actor.{key}": value} for key, value in parameter.items() if value is not None]
    return [{"$match": {"$or": known}}, {"$sort": {"at": 1, "_id": 1}}]


def person_pg(session, parameter):
    return session.fetch(PERSON_PG, parameter)


def person_mysql(session, parameter):
    return session.fetch(PERSON_MYSQL, parameter)


def person_mongo(session, parameter):
    return [(found["_id"], found["at"], found["entity"], found["entityId"], found["action"], found["actor"],
             found.get("changes")) for found in session.handle.auditEvents.aggregate(pipeline(parameter))]


SCENARIOS = [Scenario(
    id="J2", op="R", flags=frozenset({"BA", "H1-S"}), columns=COLUMNS, ordered=True, select=persons,
    description="RODO art. 15: wszystkie zdarzenia audytu osoby w kolejności czasu, wyszukane w migawce aktora "
                "po e-mailu lub telefonie (klient: e-mail i telefon, odbiorca: telefon), ×100 osób",
    impls={
        "pg": Impl(PERSON_PG, person_pg, plan=lambda parameter: Query(PERSON_PG, parameter)),
        "mysql": Impl(PERSON_MYSQL, person_mysql, plan=lambda parameter: Query(PERSON_MYSQL, parameter)),
        "mongo": Impl(PERSON_MONGO, person_mongo, plan=lambda parameter: Query("auditEvents", pipeline(parameter))),
    },
)]
