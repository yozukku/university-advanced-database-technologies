create spatial index lockermat_location_geog__idx on lockermat_ (location_);
create fulltext index lockermat_address_trgm__idx on lockermat_ (address_) with parser ngram;

alter table lockermat_cell_
    add index lockermat_cell_lockermat_size__idx ((case when status_ = 'IN_SERVICE' then lockermat_id_ end), (case when status_ = 'IN_SERVICE' then size_ end));

alter table tariff_
    add index tariff_size_from__idx (size_, valid_from_);

alter table order_
    add index order_customer_created__idx (customer_id_, created_at_ desc),
    add index order_awaiting_payment__idx ((case when status_ = 'AWAITING_PAYMENT' then payment_deadline_ end)),
    add index order_tariff__idx (tariff_id_);

alter table reservation_
    add unique index reservation_leg__uq ((case when status_ <> 'CANCELLED' then order_id_ end), (case when status_ <> 'CANCELLED' then leg_ end)),
    add index reservation_order__idx (order_id_),
    add index reservation_overdue__idx ((case when status_ = 'OCCUPIED' then to_ end)),
    add index reservation_cell_from__idx (cell_id_, from_);

alter table shipment_
    add index shipment_courier__idx (courier_keycloak_id_);

alter table access_code_
    add index access_code_reservation__idx (reservation_id_),
    add index access_code_hmac_from__idx (code_hmac_, valid_from_);

alter table incident_
    add index incident_reservation__idx (reservation_id_),
    add index incident_cell__idx (cell_id_),
    add index incident_open__idx ((case when status_ in ('OPEN', 'IN_PROGRESS') then created_at_ end));

alter table cell_opening_
    add unique index cell_opening_code_live__uq ((case when result_ in ('PENDING', 'OPENED') then access_code_id_ end)),
    add index cell_opening_open_door__idx ((case when result_ = 'OPENED' and closed_at_ is null then requested_at_ end));

alter table payment_
    add unique index payment_pending_charge__uq ((case when kind_ = 'CHARGE' and status_ = 'PENDING' then order_id_ end)),
    add index payment_order__idx (order_id_);

alter table audit_event_
    add index audit_event_entity_at__idx (entity_, entity_id_, at_);
