import json
import re
from datetime import timedelta

from bench.scenarios.params import chunks
from bench.scenarios.registry import Impl, Scenario

DELETE_PG = "delete from cell_opening_ where id_ = any(%s)"
DELETE_MYSQL = "delete from cell_opening_ where id_ in ({marks})"
DELETE_CYPHER = "MATCH (o:CellOpening) WHERE o.id IN $openings DETACH DELETE o"
OLD_SQL = "select id_ from cell_opening_ where requested_at_ < %s order by id_"
OLD_CYPHER = "MATCH (o:CellOpening) WHERE o.requestedAt < $cutoff RETURN o.id ORDER BY o.id"
CODE_OPENING = "reservations.accessCodes.openings"
PLACEHOLDER = re.compile(r'"(:[a-z]+)"')


def marks(values):
    return ", ".join(["%s"] * len(values))


def shell(collection, method, *args):
    text = PLACEHOLDER.sub(r"\1", ", ".join(json.dumps(arg) for arg in args if arg))
    return f"{collection}.{method}({text})"


def pulls(ids):
    return (
        ("orders", {f"{CODE_OPENING}.id": {"$in": ids}},
         {"$pull": {"reservations.$[leg].accessCodes.$[code].openings": {"id": {"$in": ids}}}},
         {"arrayFilters": [{"leg.accessCodes": {"$exists": True}}, {"code.openings": {"$exists": True}}]}),
        ("incidents", {"serviceOpenings.id": {"$in": ids}}, {"$pull": {"serviceOpenings": {"id": {"$in": ids}}}}, {}),
    )


def old_pipelines(cutoff):
    before = {"$lt": cutoff}
    return (
        ("orders", [
            {"$match": {f"{CODE_OPENING}.requestedAt": before | {"$exists": True}}},
            {"$unwind": "$reservations"}, {"$unwind": "$reservations.accessCodes"}, {"$unwind": f"${CODE_OPENING}"},
            {"$match": {f"{CODE_OPENING}.requestedAt": before}},
            {"$project": {"_id": 0, "id": f"${CODE_OPENING}.id"}},
        ]),
        ("incidents", [
            {"$match": {"serviceOpenings.requestedAt": before}},
            {"$unwind": "$serviceOpenings"},
            {"$match": {"serviceOpenings.requestedAt": before}},
            {"$project": {"_id": 0, "id": "$serviceOpenings.id"}},
        ]),
    )


PULL_MONGO = ";\n".join(shell(name, "update_many", *rest) for name, *rest in pulls(":openings"))
OLD_MONGO = ";\n".join(shell(name, "aggregate", pipeline) for name, pipeline in old_pipelines(":cutoff"))


def openings(pick):
    ids = [identifier for identifier, in pick.db.execute("select id_ from cell_opening_ order by id_").fetchall()]
    chosen = pick.rng.choice(len(ids), pick.count, replace=False)
    return chunks([ids[index] for index in chosen], pick.config["batch"])


def every_opening(session, params):
    return {"cell_opening_": [opening for batch in params for opening in batch]}


def delete_pg(session, batches):
    for batch in batches:
        with session.transaction() as conn:
            session.driver_counts["cell_opening_"] += conn.execute(DELETE_PG, [batch]).rowcount


def delete_mysql(session, batches):
    for batch in batches:
        with session.transaction() as cursor:
            cursor.execute(DELETE_MYSQL.format(marks=marks(batch)), batch)
            session.driver_counts["cell_opening_"] += cursor.rowcount


def delete_mongo(session, batches):
    for batch in batches:
        with session.transaction() as transaction:
            for name, query, update, options in pulls(batch):
                done = session.handle[name].update_many(query, update, array_filters=options.get("arrayFilters"),
                                                        session=transaction)
                session.driver_counts[name] += done.modified_count


def delete_cypher(session, batches):
    for batch in batches:
        with session.transaction() as tx:
            session.driver_counts["nodes"] += tx.run(DELETE_CYPHER, openings=batch).consume().counters.nodes_deleted


D1 = Scenario(
    id="D1", op="D", description="Usunięcie wpisów dziennika otwarć skrytek według id, w transakcjach po 100 wpisów",
    select=openings,
    impls={
        "pg": Impl(DELETE_PG, delete_pg, keys=every_opening),
        "mysql": Impl(DELETE_MYSQL, delete_mysql, keys=every_opening),
        "mongo": Impl(PULL_MONGO, delete_mongo, keys=every_opening),
        "neo4j": Impl(DELETE_CYPHER, delete_cypher, keys=every_opening),
    },
)


def cutoff(pick):
    return {"cutoff": pick.t0 - timedelta(days=pick.config["cutoff_days"]), "batch": pick.config["batch"]}


def old_sql(session, params):
    return {"cell_opening_": [row[0] for row in session.fetch(OLD_SQL, [params["cutoff"]])]}


def old_mongo(session, params):
    return {"cell_opening_": sorted(found["id"] for name, pipeline in old_pipelines(params["cutoff"])
                                    for found in session.handle[name].aggregate(pipeline))}


def old_cypher(session, params):
    return {"cell_opening_": [row[0] for row in session.fetch(OLD_CYPHER, {"cutoff": params["cutoff"]})]}


def purge_pg(session, params):
    delete_pg(session, chunks(old_sql(session, params)["cell_opening_"], params["batch"]))


def purge_mysql(session, params):
    delete_mysql(session, chunks(old_sql(session, params)["cell_opening_"], params["batch"]))


def purge_mongo(session, params):
    delete_mongo(session, chunks(old_mongo(session, params)["cell_opening_"], params["batch"]))


def purge_cypher(session, params):
    delete_cypher(session, chunks(old_cypher(session, params)["cell_opening_"], params["batch"]))


D3 = Scenario(
    id="D3", op="D", description="Usunięcie wpisów dziennika otwarć skrytek starszych niż 540 dni przed T0, partiami po 5000",
    select=cutoff,
    impls={
        "pg": Impl(f"{OLD_SQL};\n{DELETE_PG}", purge_pg, keys=old_sql),
        "mysql": Impl(f"{OLD_SQL};\n{DELETE_MYSQL}", purge_mysql, keys=old_sql),
        "mongo": Impl(f"{OLD_MONGO};\n{PULL_MONGO}", purge_mongo, keys=old_mongo),
        "neo4j": Impl(f"{OLD_CYPHER};\n{DELETE_CYPHER}", purge_cypher, keys=old_cypher),
    },
)
SCENARIOS = [D1, D3]
