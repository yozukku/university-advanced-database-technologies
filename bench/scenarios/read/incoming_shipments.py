from bench.scenarios.explain import Query
from bench.scenarios.registry import Impl, Scenario

COLUMNS = (("order_id", "int"), ("reservation_id", "int"), ("from", "ms"), ("to", "ms"), ("lockermat_id", "int"),
           ("lockermat_name", "text"), ("lockermat_address", "text"), ("cell_number", "int"))
WAITING = {"leg": "DESTINATION", "status": "OCCUPIED"}
PHONES = """
    select s.recipient_phone_
    from shipment_ s
    join reservation_ r on r.order_id_ = s.order_id_ and r.leg_ = 'DESTINATION' and r.status_ = 'OCCUPIED'
    where s.recipient_phone_ in (select recipient_phone_ from shipment_ group by 1 having count(*) > 1)
    group by 1
    order by 1
"""
INCOMING_SQL = """
select s.order_id_, r.id_, r.from_, r.to_, l.id_, l.name_, l.address_, c.number_
from shipment_ s
join reservation_ r on r.order_id_ = s.order_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
where s.recipient_phone_ = %(phone)s and r.leg_ = 'DESTINATION' and r.status_ = 'OCCUPIED'
"""
INCOMING_MONGO = """
orders.aggregate([
  {$match: {'shipment.recipientPhone': :phone, reservations: {$elemMatch: {leg: 'DESTINATION', status: 'OCCUPIED'}}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': 'DESTINATION', 'reservations.status': 'OCCUPIED'}},
  {$lookup: {from: 'lockermats', localField: 'reservations.lockermatId', foreignField: '_id',
             let: {cell: '$reservations.cellId'},
             pipeline: [{$project: {name: 1, address: 1, cell: {$first: {$filter: {input: '$cells', cond: {$eq: ['$$this.id', '$$cell']}}}}}}],
             as: 'locker'}},
  {$unwind: '$locker'},
  {$project: {reservation: '$reservations.id', from: '$reservations.from', to: '$reservations.to',
              lockermat: '$locker._id', name: '$locker.name', address: '$locker.address', number: '$locker.cell.number'}}
])
"""
INCOMING_CYPHER = """
MATCH (s:Shipment {recipientPhone: $phone})-[:HAS_LEG]->(r:Reservation {leg: 'DESTINATION', status: 'OCCUPIED'}),
      (r)-[:IN_CELL]->(c:Cell)<-[:HAS_CELL]-(l:Lockermat)
RETURN s.id, r.id, r.from, r.to, l.id, l.name, l.address, c.number
"""


def phones(pick):
    found = [phone for phone, in pick.db.execute(PHONES).fetchall()]
    return [{"phone": found[index]} for index in pick.rng.choice(len(found), pick.count, replace=False)]


def pipeline(parameter):
    cell = {"$first": {"$filter": {"input": "$cells", "cond": {"$eq": ["$$this.id", "$$cell"]}}}}
    return [
        {"$match": {"shipment.recipientPhone": parameter["phone"], "reservations": {"$elemMatch": WAITING}}},
        {"$unwind": "$reservations"},
        {"$match": {f"reservations.{key}": value for key, value in WAITING.items()}},
        {"$lookup": {"from": "lockermats", "localField": "reservations.lockermatId", "foreignField": "_id",
                     "let": {"cell": "$reservations.cellId"},
                     "pipeline": [{"$project": {"name": 1, "address": 1, "cell": cell}}], "as": "locker"}},
        {"$unwind": "$locker"},
        {"$project": {"reservation": "$reservations.id", "from": "$reservations.from", "to": "$reservations.to",
                      "lockermat": "$locker._id", "name": "$locker.name", "address": "$locker.address",
                      "number": "$locker.cell.number"}},
    ]


def incoming_sql(session, parameter):
    return session.fetch(INCOMING_SQL, parameter)


def incoming_mongo(session, parameter):
    return [(found["_id"], found["reservation"], found["from"], found["to"], found["lockermat"], found["name"],
             found["address"], found["number"]) for found in session.handle.orders.aggregate(pipeline(parameter))]


def incoming_cypher(session, parameter):
    return session.fetch(INCOMING_CYPHER, parameter)


def sql_plan(parameter):
    return Query(INCOMING_SQL, parameter)


SCENARIOS = [Scenario(
    id="R4", op="R", flags=frozenset({"CX", "BA", "H1-S"}), columns=COLUMNS, select=phones,
    description="„Do odbioru”: przesyłki na numer telefonu odbiorcy, których skrytka docelowa jest zajęta, "
                "z punktem i numerem skrytki, ×100 numerów",
    impls={
        "pg": Impl(INCOMING_SQL, incoming_sql, plan=sql_plan),
        "mysql": Impl(INCOMING_SQL, incoming_sql, plan=sql_plan),
        "mongo": Impl(INCOMING_MONGO, incoming_mongo, plan=lambda parameter: Query("orders", pipeline(parameter))),
        "neo4j": Impl(INCOMING_CYPHER, incoming_cypher, plan=lambda parameter: Query(INCOMING_CYPHER, parameter)),
    },
)]
