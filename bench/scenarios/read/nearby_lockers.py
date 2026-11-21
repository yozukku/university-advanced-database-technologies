from datetime import timedelta
from math import cos, degrees, radians

from bench.check.scenarios import eligible_locations, geo_points
from bench.scenarios.explain import Query
from bench.scenarios.normalise import APPROX
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("lockermat_id", "int"), ("distance_m", APPROX))
EARTH_METRES = 6_371_008.8
BOX_MARGIN = 1.02
LIVE = ["BOOKED", "OCCUPIED"]
NEARBY_PG = """
select l.id_, st_distance(l.location_::geography, st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography)
from lockermat_ l
where l.status_ = 'ACTIVE'
  and st_dwithin(l.location_::geography, st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography, %(radius)s)
  and exists (select 1 from lockermat_cell_ c
              where c.lockermat_id_ = l.id_ and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                                  and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s))
order by l.location_::geography <-> st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography
limit %(limit)s
"""
NEARBY_MYSQL = """
select l.id_, st_distance_sphere(l.location_, st_geomfromtext(%(point)s, 4326, 'axis-order=long-lat')) as distance_
from lockermat_ l
where mbrcontains(st_geomfromtext(%(box)s, 4326, 'axis-order=long-lat'), l.location_)
  and l.status_ = 'ACTIVE'
  and st_distance_sphere(l.location_, st_geomfromtext(%(point)s, 4326, 'axis-order=long-lat')) <= %(radius)s
  and exists (select 1 from lockermat_cell_ c
              where (case when c.status_ = 'IN_SERVICE' then c.lockermat_id_ end) = l.id_
                and (case when c.status_ = 'IN_SERVICE' then c.size_ end) = %(size)s
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                                  and r.from_ < %(to)s and r.to_ > %(from)s)
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s))
order by distance_, l.id_
limit %(limit)s
"""
NEARBY_MONGO = """
lockermats.aggregate([
  {$geoNear: {near: {type: 'Point', coordinates: [:lng, :lat]}, key: 'location', distanceField: 'distance',
              maxDistance: :radius, spherical: true,
              query: {status: 'ACTIVE', cells: {$elemMatch: {size: :size, status: 'IN_SERVICE'}}}}},
  {$project: {distance: 1, cells: {$map: {input: {$filter: {input: '$cells', cond: {$and: [{$eq: ['$$this.size', :size]}, {$eq: ['$$this.status', 'IN_SERVICE']}]}}},
                                        in: '$$this.id'}}}},
  {$lookup: {from: 'orders', localField: 'cells', foreignField: 'reservations.cellId', let: {cells: '$cells'},
             pipeline: [{$match: {$or: [{reservations: {$elemMatch: {status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                        {reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                        {$unwind: '$reservations'},
                        {$match: {$expr: {$in: ['$reservations.cellId', '$$cells']},
                                  $or: [{'reservations.status': {$in: ['BOOKED', 'OCCUPIED']}, 'reservations.from': {$lt: :to}, 'reservations.to': {$gt: :from}},
                                        {'reservations.status': 'OCCUPIED', 'reservations.to': {$lte: :now}}]}},
                        {$project: {_id: 0, cellId: '$reservations.cellId'}}],
             as: 'busy'}},
  {$match: {$expr: {$gt: [{$size: {$setDifference: ['$cells', '$busy.cellId']}}, 0]}}},
  {$limit: :limit},
  {$project: {distance: 1}}
])
"""
NEARBY_CYPHER = """
MATCH (l:Lockermat)
WHERE point.distance(l.location, point({longitude: $lng, latitude: $lat})) <= $radius
  AND l.status = 'ACTIVE'
  AND EXISTS {
      MATCH (l)-[:HAS_CELL]->(c:Cell {size: $size, status: 'IN_SERVICE'})
      WHERE NOT EXISTS {
          MATCH (c)<-[:IN_CELL]-(r:Reservation)
          WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
             OR (r.status = 'OCCUPIED' AND r.to <= $now)
      }
  }
WITH l, point.distance(l.location, point({longitude: $lng, latitude: $lat})) AS distance
ORDER BY distance, l.id
LIMIT $limit
RETURN l.id, distance
"""


def points(pick):
    config = pick.config
    found = geo_points(eligible_locations(pick.db, config), pick.rng, pick.count, config["radius_m"], config["limit"])
    if len(found) < pick.count:
        raise ValueError(f"R3: {len(found)} stable geo points, {pick.count} needed")
    start = pick.t0 + timedelta(days=config["days_after_t0"])
    return [{"lng": lng, "lat": lat, "radius": config["radius_m"], "size": config["size"], "from": start,
             "to": start + timedelta(hours=config["window_hours"]), "now": pick.t0, "limit": config["limit"]}
            for lng, lat in found]


def shapes(parameter):
    lng, lat = parameter["lng"], parameter["lat"]
    rise = degrees(parameter["radius"] * BOX_MARGIN / EARTH_METRES)
    span = rise / cos(radians(abs(lat) + rise))
    west, east, south, north = lng - span, lng + span, lat - rise, lat + rise
    return {"point": f"POINT({lng} {lat})",
            "box": f"POLYGON(({west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}))"}


def live(prefix, parameter):
    return {f"{prefix}status": {"$in": LIVE}, f"{prefix}from": {"$lt": parameter["to"]},
            f"{prefix}to": {"$gt": parameter["from"]}}


def overstayed(prefix, parameter):
    return {f"{prefix}status": "OCCUPIED", f"{prefix}to": {"$lte": parameter["now"]}}


def pipeline(parameter):
    conditions = (live, overstayed)
    free = {"$and": [{"$eq": ["$$this.size", parameter["size"]]}, {"$eq": ["$$this.status", "IN_SERVICE"]}]}
    return [
        {"$geoNear": {"near": {"type": "Point", "coordinates": [parameter["lng"], parameter["lat"]]},
                      "key": "location", "distanceField": "distance", "maxDistance": parameter["radius"],
                      "spherical": True, "query": {"status": "ACTIVE", "cells": {"$elemMatch": {
                          "size": parameter["size"], "status": "IN_SERVICE"}}}}},
        {"$project": {"distance": 1, "cells": {"$map": {"input": {"$filter": {"input": "$cells", "cond": free}},
                                                        "in": "$$this.id"}}}},
        {"$lookup": {
            "from": "orders", "localField": "cells", "foreignField": "reservations.cellId", "let": {"cells": "$cells"},
            "pipeline": [
                {"$match": {"$or": [{"reservations": {"$elemMatch": condition("", parameter)}}
                                    for condition in conditions]}},
                {"$unwind": "$reservations"},
                {"$match": {"$expr": {"$in": ["$reservations.cellId", "$$cells"]},
                            "$or": [condition("reservations.", parameter) for condition in conditions]}},
                {"$project": {"_id": 0, "cellId": "$reservations.cellId"}},
            ],
            "as": "busy"}},
        {"$match": {"$expr": {"$gt": [{"$size": {"$setDifference": ["$cells", "$busy.cellId"]}}, 0]}}},
        {"$limit": parameter["limit"]},
        {"$project": {"distance": 1}},
    ]


def nearby_pg(session, parameter):
    return session.fetch(NEARBY_PG, parameter)


def nearby_mysql(session, parameter):
    return session.fetch(NEARBY_MYSQL, parameter | shapes(parameter))


def nearby_mongo(session, parameter):
    return [(locker["_id"], locker["distance"]) for locker in session.handle.lockermats.aggregate(pipeline(parameter))]


def nearby_cypher(session, parameter):
    return session.fetch(NEARBY_CYPHER, parameter)


SCENARIOS = [Scenario(
    id="R3", op="R", flags=frozenset({"CX"}), columns=COLUMNS, select=points,
    description="10 najbliższych aktywnych punktów w promieniu 5 km z wolną skrytką danego rozmiaru "
                "w wybranym oknie czasu, ×200 lokalizacji",
    impls={
        "pg": Impl(NEARBY_PG, nearby_pg, plan=lambda parameter: Query(NEARBY_PG, parameter)),
        "mysql": Impl(NEARBY_MYSQL, nearby_mysql,
                      plan=lambda parameter: Query(NEARBY_MYSQL, parameter | shapes(parameter))),
        "mongo": Impl(NEARBY_MONGO, nearby_mongo, plan=lambda parameter: Query("lockermats", pipeline(parameter))),
        "neo4j": Impl(NEARBY_CYPHER, nearby_cypher, plan=lambda parameter: Query(NEARBY_CYPHER, parameter)),
    },
)]
