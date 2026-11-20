create table excl_guard_
(
    rule_ varchar(48) primary key
);
insert into excl_guard_ (rule_)
values ('tariff_no_overlap'),
       ('access_code_hmac_window');

create table lockermat_
(
    id_         bigint      not null,
    code_       varchar(16) not null,
    name_       text        not null,
    address_    text        not null,
    location_   point       not null srid 4326,
    time_zone_  text        not null default ('Europe/Warsaw'),
    status_     varchar(16) not null default 'ACTIVE',
    created_at_ datetime(3) not null default current_timestamp(3),
    primary key (id_),
    constraint lockermat_code__uq unique (code_),
    constraint lockermat_status__ck check (status_ in ('ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')),
    constraint lockermat_location__ck check (not st_isempty(location_) and st_longitude(location_) between -25 and 45 and st_latitude(location_) between 27 and 72),
    constraint lockermat_time_zone__ck check (regexp_like(time_zone_, '^[A-Za-z]+(/[A-Za-z0-9_+-]+)+$') and convert_tz(timestamp '2000-01-01 00:00:00', '+00:00', time_zone_) is not null)
);

create table lockermat_opening_hours_
(
    id_           bigint   not null,
    lockermat_id_ bigint   not null,
    weekday_      smallint not null,
    opens_at_     time(6)  not null,
    closes_at_    time(6)  not null,
    primary key (id_),
    constraint lockermat_opening_hours_weekday__uq unique (lockermat_id_, weekday_),
    constraint lockermat_opening_hours_weekday__ck check (weekday_ between 1 and 7),
    constraint lockermat_opening_hours_hours__ck check (opens_at_ <> closes_at_ and opens_at_ >= time '00:00:00' and opens_at_ < time '24:00:00'
        and closes_at_ >= time '00:00:00' and closes_at_ <= time '24:00:00')
);

create table lockermat_cell_
(
    id_           bigint      not null,
    lockermat_id_ bigint      not null,
    number_       smallint    not null,
    size_         varchar(10) not null,
    status_       varchar(16) not null default 'IN_SERVICE',
    primary key (id_),
    constraint lockermat_cell_number__uq unique (lockermat_id_, number_),
    constraint lockermat_cell_id_size__uq unique (id_, size_),
    constraint lockermat_cell_number__ck check (number_ > 0),
    constraint lockermat_cell_size__ck check (size_ in ('S', 'M', 'L')),
    constraint lockermat_cell_status__ck check (status_ in ('IN_SERVICE', 'OUT_OF_SERVICE'))
);

create table tariff_
(
    id_                     bigint        not null,
    size_                   varchar(10)   not null,
    valid_from_             datetime(3)   not null,
    valid_to_               datetime(3),
    storage_price_per_day_  decimal(8, 2) not null,
    shipment_price_         decimal(8, 2) not null,
    overstay_price_per_day_ decimal(8, 2) not null,
    primary key (id_),
    constraint tariff_id_size__uq unique (id_, size_),
    constraint tariff_size__ck check (size_ in ('S', 'M', 'L')),
    constraint tariff_validity__ck check (valid_to_ is null or valid_to_ > valid_from_),
    constraint tariff_prices__ck check (storage_price_per_day_ > 0 and shipment_price_ > 0 and overstay_price_per_day_ > 0)
);

create table customer_
(
    id_                bigint      not null,
    keycloak_id_       char(36)    not null,
    phone_             varchar(16),
    company_name_      text,
    tax_id_            varchar(16),
    billing_address_   text,
    terms_version_     varchar(16) not null,
    terms_accepted_at_ datetime(3) not null,
    created_at_        datetime(3) not null default current_timestamp(3),
    primary key (id_),
    constraint customer_keycloak_id__uq unique (keycloak_id_),
    constraint customer_phone__ck check (phone_ is null or regexp_like(phone_, '^[+][1-9][0-9]{7,14}$')),
    constraint customer_invoice__ck check (tax_id_ is null or (company_name_ is not null and billing_address_ is not null))
);

create table order_
(
    id_               bigint         not null,
    number_           varchar(20)    not null,
    customer_id_      bigint         not null,
    type_             varchar(16)    not null,
    size_             varchar(10)    not null,
    tariff_id_        bigint         not null,
    status_           varchar(16)    not null default 'AWAITING_PAYMENT',
    price_            decimal(10, 2) not null,
    payment_deadline_ datetime(3)    not null,
    created_at_       datetime(3)    not null default current_timestamp(3),
    closed_at_        datetime(3),
    primary key (id_),
    constraint order_number__uq unique (number_),
    constraint order_id_type__uq unique (id_, type_),
    constraint order_id_type_size__uq unique (id_, type_, size_),
    constraint order_type__ck check (type_ in ('STORAGE', 'SHIPMENT')),
    constraint order_status__ck check (status_ in ('AWAITING_PAYMENT', 'PAID', 'COMPLETED', 'CANCELLED', 'EXPIRED')),
    constraint order_price__ck check (price_ >= 0),
    constraint order_closed__ck check ((closed_at_ is not null) = (status_ in ('COMPLETED', 'CANCELLED', 'EXPIRED'))),
    constraint order_chronology__ck check (payment_deadline_ > created_at_ and (closed_at_ is null or closed_at_ >= created_at_))
);

create table reservation_
(
    id_           bigint      not null,
    order_id_     bigint      not null,
    order_type_   varchar(16) generated always as (case when leg_ = 'STORAGE' then 'STORAGE' else 'SHIPMENT' end) stored not null,
    size_         varchar(10) not null,
    cell_id_      bigint      not null,
    leg_          varchar(16) not null,
    from_         datetime(3) not null,
    to_           datetime(3) not null,
    status_       varchar(16) not null default 'BOOKED',
    deposited_at_ datetime(3),
    collected_at_ datetime(3),
    primary key (id_),
    constraint reservation_id_cell_order__uq unique (id_, cell_id_, order_id_),
    constraint reservation_leg__ck check (leg_ in ('STORAGE', 'ORIGIN', 'DESTINATION')),
    constraint reservation_period__ck check (to_ > from_),
    constraint reservation_status__ck check (status_ in ('BOOKED', 'OCCUPIED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    constraint reservation_deposit__ck check ((deposited_at_ is not null) = (status_ in ('OCCUPIED', 'COMPLETED'))),
    constraint reservation_collect__ck check ((collected_at_ is not null) = (status_ = 'COMPLETED') and (collected_at_ is null or collected_at_ >= deposited_at_))
);

create table shipment_
(
    id_                  bigint         not null,
    order_id_            bigint         not null,
    order_type_          varchar(16) generated always as ('SHIPMENT') stored not null,
    recipient_name_      text           not null,
    recipient_phone_     varchar(16)    not null,
    declared_value_      decimal(10, 2) not null,
    courier_keycloak_id_ char(36),
    courier_assigned_at_ datetime(3),
    primary key (id_),
    constraint shipment_order__uq unique (order_id_),
    constraint shipment_recipient_phone__ck check (regexp_like(recipient_phone_, '^[+][1-9][0-9]{7,14}$')),
    constraint shipment_declared_value__ck check (declared_value_ >= 0),
    constraint shipment_courier__ck check ((courier_keycloak_id_ is null) = (courier_assigned_at_ is null))
);

create table access_code_
(
    id_             bigint      not null,
    reservation_id_ bigint      not null,
    purpose_        varchar(16) not null,
    code_hmac_      binary(32)  not null,
    sent_to_phone_  varchar(16),
    valid_from_     datetime(3) not null,
    valid_to_       datetime(3) not null,
    status_         varchar(16) not null default 'ACTIVE',
    created_at_     datetime(3) not null default current_timestamp(3),
    used_at_        datetime(3),
    primary key (id_),
    constraint access_code_purpose__ck check (purpose_ in ('DROP_OFF', 'PICK_UP')),
    constraint access_code_status__ck check (status_ in ('ACTIVE', 'USED', 'REVOKED')),
    constraint access_code_hmac__ck check (octet_length(code_hmac_) = 32),
    constraint access_code_validity__ck check (valid_to_ > valid_from_),
    constraint access_code_issue_before_expiry__ck check (created_at_ < valid_to_),
    constraint access_code_used__ck check (
        (used_at_ is not null) = (status_ = 'USED')
            and (used_at_ is null or (used_at_ >= valid_from_ and used_at_ < valid_to_ and used_at_ >= created_at_))
        ),
    constraint access_code_phone__ck check (sent_to_phone_ is null or regexp_like(sent_to_phone_, '^[+][1-9][0-9]{7,14}$'))
);

create table incident_
(
    id_                      bigint      not null,
    cell_id_                 bigint      not null,
    reservation_id_          bigint,
    order_id_                bigint,
    source_                  varchar(16) not null,
    reported_by_keycloak_id_ char(36),
    type_                    varchar(24) not null,
    description_             text        not null,
    status_                  varchar(16) not null default 'OPEN',
    resolution_              text,
    resolved_by_keycloak_id_ char(36),
    created_at_              datetime(3) not null default current_timestamp(3),
    resolved_at_             datetime(3),
    primary key (id_),
    constraint incident_id_order__uq unique (id_, order_id_),
    constraint incident_reservation__ck check ((reservation_id_ is null) = (order_id_ is null)),
    constraint incident_source__ck check (source_ in ('CUSTOMER', 'COURIER', 'SUPPORT', 'TERMINAL')),
    constraint incident_reporter__ck check ((source_ in ('TERMINAL', 'CUSTOMER')) = (reported_by_keycloak_id_ is null)),
    constraint incident_customer__ck check (source_ <> 'CUSTOMER' or reservation_id_ is not null),
    constraint incident_type__ck check (type_ in ('DOOR_WONT_OPEN', 'CELL_NOT_EMPTY', 'DOOR_LEFT_OPEN', 'LUGGAGE_DAMAGED', 'LUGGAGE_MISSING', 'DELIVERY_DELAYED', 'OTHER')),
    constraint incident_status__ck check (status_ in ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'REJECTED')),
    constraint incident_resolved__ck check (
        (status_ in ('RESOLVED', 'REJECTED')) = (resolved_at_ is not null)
            and (resolved_at_ is null or (resolution_ is not null and resolved_by_keycloak_id_ is not null and resolved_at_ >= created_at_))
        )
);

create table cell_opening_
(
    id_                bigint      not null,
    access_code_id_    bigint,
    incident_id_       bigint,
    channel_           varchar(16) not null,
    actor_keycloak_id_ char(36),
    result_            varchar(16) not null,
    requested_at_      datetime(3) not null default current_timestamp(3),
    closed_at_         datetime(3),
    primary key (id_),
    constraint cell_opening_channel__ck check (channel_ in ('KEYPAD', 'APP', 'SERVICE')),
    constraint cell_opening_result__ck check (result_ in ('PENDING', 'OPENED', 'DOOR_FAILED')),
    constraint cell_opening_grant__ck check (
        (access_code_id_ is not null) + (incident_id_ is not null) = 1
            and (channel_ = 'SERVICE') = (incident_id_ is not null)
            and (channel_ = 'KEYPAD') = (actor_keycloak_id_ is null)
        ),
    constraint cell_opening_closed__ck check (closed_at_ is null or (result_ = 'OPENED' and closed_at_ >= requested_at_))
);

create table payment_
(
    id_            bigint         not null,
    order_id_      bigint         not null,
    kind_          varchar(16)    not null,
    amount_        decimal(10, 2) not null,
    status_        varchar(16)    not null default 'PENDING',
    provider_      varchar(32)    not null,
    provider_ref_  varchar(128),
    refund_of_id_  bigint,
    incident_id_   bigint,
    refundable_id_ bigint generated always as (case when kind_ in ('CHARGE', 'EXTENSION', 'OVERSTAY') and status_ = 'COMPLETED' then id_ end) stored,
    created_at_    datetime(3)    not null default current_timestamp(3),
    completed_at_  datetime(3),
    primary key (id_),
    constraint payment_refundable__uq unique (refundable_id_, order_id_, provider_),
    constraint payment_kind__ck check (kind_ in ('CHARGE', 'EXTENSION', 'OVERSTAY', 'REFUND', 'COMPENSATION')),
    constraint payment_amount__ck check (amount_ > 0),
    constraint payment_status__ck check (status_ in ('PENDING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    constraint payment_link__ck check (
        (kind_ = 'REFUND') = (refund_of_id_ is not null)
            and (kind_ <> 'COMPENSATION' or incident_id_ is not null)
            and (incident_id_ is null or kind_ in ('REFUND', 'COMPENSATION'))
        ),
    constraint payment_completed__ck check ((status_ = 'COMPLETED') = (completed_at_ is not null)),
    constraint payment_provider_ref__ck check (status_ <> 'COMPLETED' or provider_ref_ is not null),
    constraint payment_chronology__ck check (completed_at_ is null or completed_at_ >= created_at_),
    constraint payment_provider_ref__uq unique (provider_, provider_ref_)
);

create table audit_event_
(
    id_          bigint      not null,
    at_          datetime(3) not null default current_timestamp(3),
    entity_      varchar(24) not null,
    entity_id_   bigint      not null,
    action_      varchar(32) not null,
    actor_       json        not null,
    changes_     json,
    changes_new_ json,
    primary key (id_),
    constraint audit_event_actor__ck check (json_type(actor_) = 'OBJECT' and json_contains_path(actor_, 'one', '$.kind')),
    constraint audit_event_changes__ck check (json_type(changes_) = 'ARRAY')
);
