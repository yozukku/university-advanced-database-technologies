alter table lockermat_opening_hours_
    add constraint lockermat_opening_hours_lockermat__fk foreign key (lockermat_id_) references lockermat_ (id_) on delete restrict;

alter table lockermat_cell_
    add constraint lockermat_cell_lockermat__fk foreign key (lockermat_id_) references lockermat_ (id_) on delete restrict;

alter table order_
    add constraint order_customer__fk foreign key (customer_id_) references customer_ (id_) on delete restrict,
    add constraint order_tariff__fk foreign key (tariff_id_, size_) references tariff_ (id_, size_) on delete restrict;

alter table reservation_
    add constraint reservation_order__fk foreign key (order_id_, order_type_, size_) references order_ (id_, type_, size_) on delete restrict,
    add constraint reservation_lockermat_cell__fk foreign key (cell_id_, size_) references lockermat_cell_ (id_, size_) on delete restrict;

alter table shipment_
    add constraint shipment_order__fk foreign key (order_id_, order_type_) references order_ (id_, type_) on delete restrict;

alter table access_code_
    add constraint access_code_reservation__fk foreign key (reservation_id_) references reservation_ (id_) on delete restrict;

alter table incident_
    add constraint incident_lockermat_cell__fk foreign key (cell_id_) references lockermat_cell_ (id_) on delete restrict,
    add constraint incident_reservation__fk foreign key (reservation_id_, cell_id_, order_id_) references reservation_ (id_, cell_id_, order_id_) on delete restrict;

alter table cell_opening_
    add constraint cell_opening_access_code__fk foreign key (access_code_id_) references access_code_ (id_) on delete restrict,
    add constraint cell_opening_incident__fk foreign key (incident_id_) references incident_ (id_) on delete restrict;

alter table payment_
    add constraint payment_order__fk foreign key (order_id_) references order_ (id_) on delete restrict,
    add constraint payment_payment__refund_of_fk foreign key (refund_of_id_, order_id_, provider_) references payment_ (refundable_id_, order_id_, provider_) on delete restrict,
    add constraint payment_incident__fk foreign key (incident_id_, order_id_) references incident_ (id_, order_id_) on delete restrict;
