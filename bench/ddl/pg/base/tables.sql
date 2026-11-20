create extension if not exists postgis;
create extension if not exists btree_gist;
create extension if not exists pg_trgm;

create sequence lockermat_id_seq_ start with 1 increment by 1;
create table lockermat_
(
    id_         bigint                default nextval('lockermat_id_seq_'::regclass),
    code_       varchar(16)           not null,
    name_       text                  not null,
    address_    text                  not null,
    location_   geometry(point, 4326) not null,
    time_zone_  text                  not null default 'Europe/Warsaw',
    status_     varchar(16)           not null default 'ACTIVE',
    created_at_ timestamptz           not null default now()
);

create sequence lockermat_opening_hours_id_seq_ start with 1 increment by 1;
create table lockermat_opening_hours_
(
    id_           bigint   default nextval('lockermat_opening_hours_id_seq_'::regclass),
    lockermat_id_ bigint   not null,
    weekday_      smallint not null,
    opens_at_     time     not null,
    closes_at_    time     not null
);

create sequence lockermat_cell_id_seq_ start with 1 increment by 1;
create table lockermat_cell_
(
    id_           bigint      default nextval('lockermat_cell_id_seq_'::regclass),
    lockermat_id_ bigint      not null,
    number_       smallint    not null,
    size_         varchar(10) not null,
    status_       varchar(16) not null default 'IN_SERVICE'
);

create sequence tariff_id_seq_ start with 1 increment by 1;
create table tariff_
(
    id_                     bigint        default nextval('tariff_id_seq_'::regclass),
    size_                   varchar(10)   not null,
    valid_from_             timestamptz   not null,
    valid_to_               timestamptz,
    storage_price_per_day_  numeric(8, 2) not null,
    shipment_price_         numeric(8, 2) not null,
    overstay_price_per_day_ numeric(8, 2) not null
);

create sequence customer_id_seq_ start with 1 increment by 1;
create table customer_
(
    id_                bigint      default nextval('customer_id_seq_'::regclass),
    keycloak_id_       uuid        not null,
    phone_             varchar(16),
    company_name_      text,
    tax_id_            varchar(16),
    billing_address_   text,
    terms_version_     varchar(16) not null,
    terms_accepted_at_ timestamptz not null,
    created_at_        timestamptz not null default now()
);

create sequence order_id_seq_ start with 1 increment by 1;
create table order_
(
    id_               bigint         default nextval('order_id_seq_'::regclass),
    number_           varchar(20)    not null,
    customer_id_      bigint         not null,
    type_             varchar(16)    not null,
    size_             varchar(10)    not null,
    tariff_id_        bigint         not null,
    status_           varchar(16)    not null default 'AWAITING_PAYMENT',
    price_            numeric(10, 2) not null,
    payment_deadline_ timestamptz    not null,
    created_at_       timestamptz    not null default now(),
    closed_at_        timestamptz
);

create sequence reservation_id_seq_ start with 1 increment by 1;
create table reservation_
(
    id_           bigint      default nextval('reservation_id_seq_'::regclass),
    order_id_     bigint      not null,
    order_type_   varchar(16) not null generated always as (case when leg_ = 'STORAGE' then 'STORAGE' else 'SHIPMENT' end) stored,
    size_         varchar(10) not null,
    cell_id_      bigint      not null,
    leg_          varchar(16) not null,
    from_         timestamptz not null,
    to_           timestamptz not null,
    status_       varchar(16) not null default 'BOOKED',
    deposited_at_ timestamptz,
    collected_at_ timestamptz
);

create sequence shipment_id_seq_ start with 1 increment by 1;
create table shipment_
(
    id_                  bigint         default nextval('shipment_id_seq_'::regclass),
    order_id_            bigint         not null,
    order_type_          varchar(16)    not null generated always as ('SHIPMENT') stored,
    recipient_name_      text           not null,
    recipient_phone_     varchar(16)    not null,
    declared_value_      numeric(10, 2) not null,
    courier_keycloak_id_ uuid,
    courier_assigned_at_ timestamptz
);

create sequence access_code_id_seq_ start with 1 increment by 1;
create table access_code_
(
    id_             bigint      default nextval('access_code_id_seq_'::regclass),
    reservation_id_ bigint      not null,
    purpose_        varchar(16) not null,
    code_hmac_      bytea       not null,
    sent_to_phone_  varchar(16),
    valid_from_     timestamptz not null,
    valid_to_       timestamptz not null,
    status_         varchar(16) not null default 'ACTIVE',
    created_at_     timestamptz not null default now(),
    used_at_        timestamptz
);

create sequence incident_id_seq_ start with 1 increment by 1;
create table incident_
(
    id_                      bigint      default nextval('incident_id_seq_'::regclass),
    cell_id_                 bigint      not null,
    reservation_id_          bigint,
    order_id_                bigint,
    source_                  varchar(16) not null,
    reported_by_keycloak_id_ uuid,
    type_                    varchar(24) not null,
    description_             text        not null,
    status_                  varchar(16) not null default 'OPEN',
    resolution_              text,
    resolved_by_keycloak_id_ uuid,
    created_at_              timestamptz not null default now(),
    resolved_at_             timestamptz
);

create sequence cell_opening_id_seq_ start with 1 increment by 1;
create table cell_opening_
(
    id_                bigint      default nextval('cell_opening_id_seq_'::regclass),
    access_code_id_    bigint,
    incident_id_       bigint,
    channel_           varchar(16) not null,
    actor_keycloak_id_ uuid,
    result_            varchar(16) not null,
    requested_at_      timestamptz not null default now(),
    closed_at_         timestamptz
);

create sequence payment_id_seq_ start with 1 increment by 1;
create table payment_
(
    id_            bigint         default nextval('payment_id_seq_'::regclass),
    order_id_      bigint         not null,
    kind_          varchar(16)    not null,
    amount_        numeric(10, 2) not null,
    status_        varchar(16)    not null default 'PENDING',
    provider_      varchar(32)    not null,
    provider_ref_  varchar(128),
    refund_of_id_  bigint,
    incident_id_   bigint,
    refundable_id_ bigint generated always as (case when kind_ in ('CHARGE', 'EXTENSION', 'OVERSTAY') and status_ = 'COMPLETED' then id_ end) stored,
    created_at_    timestamptz    not null default now(),
    completed_at_  timestamptz
);

create sequence audit_event_id_seq_ start with 1 increment by 1;
create table audit_event_
(
    id_        bigint      default nextval('audit_event_id_seq_'::regclass),
    at_        timestamptz not null default now(),
    entity_    varchar(24) not null,
    entity_id_ bigint      not null,
    action_    varchar(32) not null,
    actor_     jsonb       not null,
    changes_   jsonb
);
