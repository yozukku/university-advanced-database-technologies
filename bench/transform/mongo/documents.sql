create macro ejson_long(value) as case when value is not null then json_object('$numberLong', value::varchar) end;
create macro ejson_money(value) as ejson_long((value * 100)::bigint);
create macro ejson_date(value) as case when value is not null then json_object('$date', json_object('$numberLong', epoch_ms(value)::varchar)) end;
create macro clock(value) as strftime(date '2000-01-01' + value, '%H:%M:%S.%f');
create macro without_nulls(document) as json_merge_patch('{}', document);

create view leg_lockers as
select r.id_, r.order_id_, r.leg_, c.lockermat_id_
from reservation_ r
join lockermat_cell_ c on c.id_ = r.cell_id_;

create view shipment_lockers as
select order_id_,
       any_value(lockermat_id_) filter (where leg_ = 'ORIGIN') as origin_,
       any_value(lockermat_id_) filter (where leg_ = 'DESTINATION') as destination_
from leg_lockers
where leg_ in ('ORIGIN', 'DESTINATION')
group by order_id_;

create view opening_documents as
select id_, access_code_id_, incident_id_, without_nulls(json_object(
    'id', ejson_long(id_),
    'channel', channel_,
    'actorKeycloakId', actor_keycloak_id_,
    'result', result_,
    'requestedAt', ejson_date(requested_at_),
    'closedAt', ejson_date(closed_at_)
)) as document
from cell_opening_;

create view lockermats as
with cells as (
    select lockermat_id_, to_json(list(json_object(
        'id', ejson_long(id_),
        'number', number_,
        'size', size_,
        'status', status_
    ) order by id_)) as items
    from lockermat_cell_
    group by lockermat_id_
), hours as (
    select lockermat_id_, to_json(list(json_object(
        'id', ejson_long(id_),
        'weekday', weekday_,
        'opensAt', clock(opens_at_),
        'closesAt', clock(closes_at_)
    ) order by id_)) as items
    from lockermat_opening_hours_
    group by lockermat_id_
)
select l.id_, without_nulls(json_object(
    '_id', ejson_long(l.id_),
    'code', l.code_,
    'name', l.name_,
    'address', l.address_,
    'location', json_object('type', 'Point', 'coordinates', point_coordinates(l.location_)),
    'timeZone', l.time_zone_,
    'status', l.status_,
    'createdAt', ejson_date(l.created_at_),
    'cells', c.items,
    'openingHours', h.items
)) as document
from lockermat_ l
left join cells c on c.lockermat_id_ = l.id_
left join hours h on h.lockermat_id_ = l.id_;

create view tariffs as
select id_, without_nulls(json_object(
    '_id', ejson_long(id_),
    'size', size_,
    'validFrom', ejson_date(valid_from_),
    'validTo', ejson_date(valid_to_),
    'storagePricePerDay', ejson_money(storage_price_per_day_),
    'shipmentPrice', ejson_money(shipment_price_),
    'overstayPricePerDay', ejson_money(overstay_price_per_day_)
)) as document
from tariff_;

create view customers as
select id_, without_nulls(json_object(
    '_id', ejson_long(id_),
    'keycloakId', keycloak_id_,
    'phone', phone_,
    'companyName', company_name_,
    'taxId', tax_id_,
    'billingAddress', billing_address_,
    'termsVersion', terms_version_,
    'termsAcceptedAt', ejson_date(terms_accepted_at_),
    'createdAt', ejson_date(created_at_)
)) as document
from customer_;

create view orders as
with openings as (
    select access_code_id_, to_json(list(document order by id_)) as items
    from opening_documents
    where access_code_id_ is not null
    group by access_code_id_
), codes as (
    select a.reservation_id_, to_json(list(without_nulls(json_object(
        'id', ejson_long(a.id_),
        'purpose', a.purpose_,
        'codeHmac', json_object('$binary', json_object('base64', to_base64(a.code_hmac_), 'subType', '00')),
        'sentToPhone', a.sent_to_phone_,
        'validFrom', ejson_date(a.valid_from_),
        'validTo', ejson_date(a.valid_to_),
        'status', a.status_,
        'createdAt', ejson_date(a.created_at_),
        'usedAt', ejson_date(a.used_at_),
        'openings', o.items
    )) order by a.id_)) as items
    from access_code_ a
    left join openings o on o.access_code_id_ = a.id_
    group by a.reservation_id_
), legs as (
    select r.order_id_, to_json(list(without_nulls(json_object(
        'id', ejson_long(r.id_),
        'size', r.size_,
        'cellId', ejson_long(r.cell_id_),
        'lockermatId', ejson_long(l.lockermat_id_),
        'leg', r.leg_,
        'from', ejson_date(r.from_),
        'to', ejson_date(r.to_),
        'status', r.status_,
        'depositedAt', ejson_date(r.deposited_at_),
        'collectedAt', ejson_date(r.collected_at_),
        'accessCodes', c.items
    )) order by r.id_)) as items
    from reservation_ r
    join leg_lockers l on l.id_ = r.id_
    left join codes c on c.reservation_id_ = r.id_
    group by r.order_id_
), payments as (
    select order_id_, to_json(list(without_nulls(json_object(
        'id', ejson_long(id_),
        'kind', kind_,
        'amount', ejson_money(amount_),
        'status', status_,
        'provider', provider_,
        'providerRef', provider_ref_,
        'refundOfId', ejson_long(refund_of_id_),
        'incidentId', ejson_long(incident_id_),
        'createdAt', ejson_date(created_at_),
        'completedAt', ejson_date(completed_at_)
    )) order by id_)) as items
    from payment_
    group by order_id_
), shipments as (
    select s.order_id_, without_nulls(json_object(
        'id', ejson_long(s.id_),
        'recipientName', s.recipient_name_,
        'recipientPhone', s.recipient_phone_,
        'declaredValue', ejson_money(s.declared_value_),
        'courierKeycloakId', s.courier_keycloak_id_,
        'courierAssignedAt', ejson_date(s.courier_assigned_at_),
        'originLockermatId', ejson_long(l.origin_),
        'destinationLockermatId', ejson_long(l.destination_)
    )) as document
    from shipment_ s
    join shipment_lockers l on l.order_id_ = s.order_id_
)
select o.id_, without_nulls(json_object(
    '_id', ejson_long(o.id_),
    'number', o.number_,
    'customerId', ejson_long(o.customer_id_),
    'type', o.type_,
    'size', o.size_,
    'tariffId', ejson_long(o.tariff_id_),
    'status', o.status_,
    'price', ejson_money(o.price_),
    'paymentDeadline', ejson_date(o.payment_deadline_),
    'createdAt', ejson_date(o.created_at_),
    'closedAt', ejson_date(o.closed_at_),
    'shipment', s.document,
    'reservations', l.items,
    'payments', p.items
)) as document
from order_ o
left join shipments s on s.order_id_ = o.id_
left join legs l on l.order_id_ = o.id_
left join payments p on p.order_id_ = o.id_;

create view incidents as
with openings as (
    select incident_id_, to_json(list(document order by id_)) as items
    from opening_documents
    where incident_id_ is not null
    group by incident_id_
)
select i.id_, without_nulls(json_object(
    '_id', ejson_long(i.id_),
    'cellId', ejson_long(i.cell_id_),
    'reservationId', ejson_long(i.reservation_id_),
    'orderId', ejson_long(i.order_id_),
    'source', i.source_,
    'reportedByKeycloakId', i.reported_by_keycloak_id_,
    'type', i.type_,
    'description', i.description_,
    'status', i.status_,
    'resolution', i.resolution_,
    'resolvedByKeycloakId', i.resolved_by_keycloak_id_,
    'createdAt', ejson_date(i.created_at_),
    'resolvedAt', ejson_date(i.resolved_at_),
    'serviceOpenings', o.items
)) as document
from incident_ i
left join openings o on o.incident_id_ = i.id_;

create view auditEvents as
select id_, json_merge_patch(json_object(
    '_id', ejson_long(id_),
    'at', ejson_date(at_),
    'entity', entity_,
    'entityId', ejson_long(entity_id_),
    'action', action_,
    'actor', actor_::json
), json_object('changes', changes_::json)) as document
from audit_event_;

create view shipLinks as
select s.order_id_ as id_, json_object(
    '_id', ejson_long(s.order_id_),
    'orderId', ejson_long(s.order_id_),
    'from', ejson_long(l.origin_),
    'to', ejson_long(l.destination_),
    'at', ejson_date(o.created_at_)
) as document
from shipment_ s
join shipment_lockers l on l.order_id_ = s.order_id_
join order_ o on o.id_ = s.order_id_;
