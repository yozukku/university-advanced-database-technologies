from datetime import timezone

from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

CUTOFF = "select getvariable('benchmark_t0') - to_months(?)"
OLD_SQL = "select id_ from audit_event_ where at_ < %s and entity_ <> 'PAYMENT' order by id_"
DELETE_PG = "delete from audit_event_ where id_ = any(%s)"
DELETE_MYSQL = "delete from audit_event_ where id_ in ({marks})"
OLD_MONGO = "auditEvents.find({at: {$lt: :cutoff}, entity: {$ne: 'PAYMENT'}}, {_id: 1})"
DELETE_MONGO = "auditEvents.deleteMany({_id: {$in: :events}}) in one transaction per batch"


def cutoff(pick):
    [(found,)] = pick.db.execute(CUTOFF, [pick.config["cutoff_months"]]).fetchall()
    return {"cutoff": found.astimezone(timezone.utc), "batch": pick.config["batch"]}


def old_sql(session, params):
    return {"audit_event_": [row[0] for row in session.fetch(OLD_SQL, [params["cutoff"]])]}


def old_mongo(session, params):
    found = session.handle.auditEvents.find({"at": {"$lt": params["cutoff"]}, "entity": {"$ne": "PAYMENT"}}, {"_id": 1})
    return {"audit_event_": sorted(event["_id"] for event in found)}


def purge_pg(session, params):
    for batch in chunks(old_sql(session, params)["audit_event_"], params["batch"]):
        with session.transaction() as conn:
            session.driver_counts["audit_event_"] += conn.execute(DELETE_PG, [batch]).rowcount


def purge_mysql(session, params):
    for batch in chunks(old_sql(session, params)["audit_event_"], params["batch"]):
        with session.transaction() as cursor:
            cursor.execute(DELETE_MYSQL.format(marks=", ".join(["%s"] * len(batch))), batch)
            session.driver_counts["audit_event_"] += cursor.rowcount


def purge_mongo(session, params):
    for batch in chunks(old_mongo(session, params)["audit_event_"], params["batch"]):
        with session.transaction() as transaction:
            done = session.handle.auditEvents.delete_many({"_id": {"$in": batch}}, session=transaction)
            session.driver_counts["auditEvents"] += done.deleted_count


SCENARIOS = [Scenario(
    id="J6", op="D", select=cutoff,
    description="Retencja: usunięcie zdarzeń audytu niedotyczących płatności, starszych niż 18 miesięcy przed T0, "
                "partiami po 5000",
    impls={
        "pg": Impl(f"{OLD_SQL};\n{DELETE_PG}", purge_pg, keys=old_sql),
        "mysql": Impl(f"{OLD_SQL};\n{DELETE_MYSQL}", purge_mysql, keys=old_sql),
        "mongo": Impl(f"{OLD_MONGO};\n{DELETE_MONGO}", purge_mongo, keys=old_mongo),
    },
)]
