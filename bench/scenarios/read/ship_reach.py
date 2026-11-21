from datetime import timedelta

from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario, read_ops

COLUMNS = (("lockermat_id", "int"), ("hops", "int"))
MAX_HOPS = read_ops()["R8"]["max_hops"]
ORIGINS = """
    select distinct oc.lockermat_id_
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    where o.created_at_ >= ?
    order by 1
"""
LINKS = """
link (from_, to_) as (
    select oc.lockermat_id_, dc.lockermat_id_
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    join reservation_ dl on dl.order_id_ = s.order_id_ and dl.leg_ = 'DESTINATION'
    join lockermat_cell_ dc on dc.id_ = dl.cell_id_
    where o.created_at_ >= %(since)s
)"""
REACH_PG = f"""
with recursive {LINKS.strip()}, reach (lockermat_id_, hops_) as (
    select %(lockermat)s::bigint, 0
    union
    select k.to_, r.hops_ + 1
    from reach r
    join link k on k.from_ = r.lockermat_id_
    where r.hops_ < %(max_hops)s
)
select lockermat_id_, min(hops_)
from reach
where lockermat_id_ <> %(lockermat)s
group by lockermat_id_
"""
REACH_MYSQL = f"""
with recursive {LINKS.strip()}, reach (lockermat_id_, hops_) as (
    select cast(%(lockermat)s as signed), 0
    union distinct
    select k.to_, r.hops_ + 1
    from reach r
    join link k on k.from_ = r.lockermat_id_
    where r.hops_ < %(max_hops)s
)
select lockermat_id_, min(hops_)
from reach
where lockermat_id_ <> %(lockermat)s
group by lockermat_id_
"""
REACH_MONGO = """
lockermats.aggregate([
  {$match: {_id: :lockermat}},
  {$project: {_id: 1}},
  {$graphLookup: {from: 'shipLinks', startWith: '$_id', connectFromField: 'to', connectToField: 'from',
                  as: 'links', maxDepth: :max_hops - 1, depthField: 'depth', restrictSearchWithMatch: {at: {$gte: :since}}}},
  {$unwind: '$links'},
  {$group: {_id: '$links.to', hops: {$min: {$add: ['$links.depth', 1]}}}},
  {$match: {_id: {$ne: :lockermat}}}
])
"""
REACH_CYPHER = """
MATCH p = SHORTEST 1 (a:Lockermat {id: $lockermat})-[r:SHIPS_TO WHERE r.at >= $since]->{1,%d}(b:Lockermat)
WHERE b <> a
RETURN b.id, length(p)
""" % MAX_HOPS


def origins(pick):
    since = pick.t0 - timedelta(days=pick.config["days"])
    ids = [identifier for identifier, in pick.db.execute(ORIGINS, [since]).fetchall()]
    return [{"lockermat": ids[index], "since": since, "max_hops": pick.config["max_hops"]}
            for index in pick.rng.choice(len(ids), pick.count, replace=False)]


def pipeline(parameter):
    return [
        {"$match": {"_id": parameter["lockermat"]}},
        {"$project": {"_id": 1}},
        {"$graphLookup": {"from": "shipLinks", "startWith": "$_id", "connectFromField": "to", "connectToField": "from",
                          "as": "links", "maxDepth": parameter["max_hops"] - 1, "depthField": "depth",
                          "restrictSearchWithMatch": {"at": {"$gte": parameter["since"]}}}},
        {"$unwind": "$links"},
        {"$group": {"_id": "$links.to", "hops": {"$min": {"$add": ["$links.depth", 1]}}}},
        {"$match": {"_id": {"$ne": parameter["lockermat"]}}},
    ]


def frontier(parameter):
    return Query("shipLinks", {"from": {"$in": [parameter["lockermat"]]}, "at": {"$gte": parameter["since"]}})


def reach_pg(session, parameter):
    return session.fetch(REACH_PG, parameter)


def reach_mysql(session, parameter):
    return session.fetch(REACH_MYSQL, parameter)


def reach_mongo(session, parameter):
    return [(found["_id"], found["hops"]) for found in session.handle.lockermats.aggregate(pipeline(parameter))]


def reach_cypher(session, parameter):
    return session.fetch(REACH_CYPHER, parameter)


SCENARIOS = [Scenario(
    id="R8", op="R", flags=frozenset({"CX"}), columns=COLUMNS, select=origins,
    description="Punkty osiągalne z danego punktu po połączeniach przesyłek z ostatnich 90 dni "
                "z najmniejszą liczbą przeskoków ≤ 3, ×50 punktów startowych",
    impls={
        "pg": Impl(REACH_PG, reach_pg, plan=lambda parameter: Query(REACH_PG, parameter)),
        "mysql": Impl(REACH_MYSQL, reach_mysql, plan=lambda parameter: Query(REACH_MYSQL, parameter)),
        "mongo": Impl(REACH_MONGO, reach_mongo, plan=frontier),
        "neo4j": Impl(REACH_CYPHER, reach_cypher, plan=lambda parameter: Query(REACH_CYPHER, parameter)),
    },
)]
