from .parquet import require_empty


AUDIT_CHECKS = {
    "invalid audit JSON": """
        select count(*) from audit_event_
        where not json_valid(actor_) or not json_valid(changes_) or actor_ is null or changes_ is null
    """,
    "invalid audit actors": """
        with actors as (
            select actor_, json_extract_string(actor_, '$.kind') as kind from audit_event_
        )
        select count(*) from actors
        where json_type(actor_) != 'OBJECT' or kind is null
           or kind not in ('CUSTOMER','RECIPIENT','COURIER','SUPPORT','TERMINAL','SYSTEM','PROVIDER')
           or (kind = 'CUSTOMER' and (
               json_type(actor_, '$.keycloak_id') is distinct from 'VARCHAR'
               or json_type(actor_, '$.email') is distinct from 'VARCHAR'
           ))
           or (kind = 'RECIPIENT' and (
               json_type(actor_, '$.name') is distinct from 'VARCHAR'
               or json_type(actor_, '$.phone') is distinct from 'VARCHAR'
           ))
           or (kind in ('COURIER','SUPPORT') and json_type(actor_, '$.keycloak_id') is distinct from 'VARCHAR')
           or (kind = 'TERMINAL' and coalesce(json_type(actor_, '$.lockermat_id'),'') not in ('BIGINT','UBIGINT'))
           or (kind = 'SYSTEM' and json_type(actor_, '$.job') is distinct from 'VARCHAR')
           or (kind = 'PROVIDER' and json_type(actor_, '$.provider') is distinct from 'VARCHAR')
    """,
    "invalid actor field types": """
        select count(*) from audit_event_ a, json_each(a.actor_) f
        where (f.key = 'lockermat_id' and f.type not in ('BIGINT','UBIGINT'))
           or (f.key != 'lockermat_id' and f.type != 'VARCHAR')
    """,
    "invalid change arrays": """
        select count(*) from audit_event_ where json_type(changes_) is distinct from 'ARRAY' or json_array_length(changes_) = 0
    """,
    "personal fields or invalid audit changes": """
        select count(*) from audit_event_ a, json_each(a.changes_) c
        where c.type != 'OBJECT' or json_extract_string(c.value, '$.f') is distinct from 'status_'
           or coalesce(json_type(c.value, '$.old'), '') not in ('VARCHAR','NULL')
           or coalesce(json_type(c.value, '$.new'), '') not in ('VARCHAR','NULL')
           or length(json_extract_string(c.value, '$.old')) > 32
           or length(json_extract_string(c.value, '$.new')) > 32
    """,
    "audit events outside their canonical milestone": """
        select count(*) from audit_event_ a
        left join order_ o on a.entity_ = 'ORDER' and o.id_ = a.entity_id_
        left join payment_ p on a.entity_ = 'PAYMENT' and p.id_ = a.entity_id_
        left join reservation_ r on a.entity_ = 'RESERVATION' and r.id_ = a.entity_id_
        left join payment_ charge on a.entity_ = 'ORDER' and a.action_ = 'PAID' and charge.id_ = o.id_
        where a.at_ >= getvariable('benchmark_t0') or a.at_ is distinct from
          case
              when a.action_ = 'CREATED' then o.created_at_
              when a.action_ = 'PAID' then charge.completed_at_
              when a.action_ in ('CANCELLED','EXPIRED') and o.status_ = a.action_ then o.closed_at_
              when a.action_ = 'DEPOSITED' then r.deposited_at_
              when a.action_ = 'COLLECTED' then r.collected_at_
              when a.action_ = 'REFUNDED' and p.kind_ = 'REFUND' then p.completed_at_
          end
    """,
    "duplicated audit milestones": """
        select count(*) from (
            select entity_, entity_id_, action_ from audit_event_ group by all having count(*) > 1
        )
    """,
}


def check_audit(db, plan):
    require_empty(db, AUDIT_CHECKS)
    count, kinds = db.execute("select count(*), count(distinct json_extract_string(actor_, '$.kind')) from audit_event_").fetchone()
    if count != plan.counts["audit_event_"] or kinds != 7:
        raise ValueError(f"Expected {plan.counts['audit_event_']} audit events and 7 actor kinds, found {count} and {kinds}")
    print(f"Audit: {count:,} canonical lifecycle events, {kinds} actor kinds")
