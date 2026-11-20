create extension if not exists postgis;
create extension if not exists btree_gist;
create extension if not exists pg_trgm;

create sequence lockermat_id_seq_ start with 1 increment by 1;
create table lockermat_
(
    id_         bigint primary key    default nextval('lockermat_id_seq_'::regclass),
    code_       varchar(16)           not null
        constraint lockermat_code__uq unique,
    name_       text                  not null,
    address_    text                  not null,
    location_   geometry(point, 4326) not null,
    time_zone_  text                  not null default 'Europe/Warsaw',
    status_     varchar(16)           not null default 'ACTIVE',
    created_at_ timestamptz           not null default now(),
    constraint lockermat_status__ck check (status_ in ('ACTIVE', 'SUSPENDED', 'DECOMMISSIONED')),
    constraint lockermat_location__ck check (not st_isempty(location_) and st_x(location_) between -25 and 45 and st_y(location_) between 27 and 72),
    constraint lockermat_time_zone__ck check (time_zone_ ~ '^[A-Za-z]+(/[A-Za-z0-9_+-]+)+$' and timezone(time_zone_, timestamptz '2000-01-01 00:00+00') is not null)
);
create index lockermat_location_geog__idx on lockermat_ using gist ((location_::geography));
create index lockermat_address_trgm__idx on lockermat_ using gin (lower(address_) gin_trgm_ops);

create sequence lockermat_opening_hours_id_seq_ start with 1 increment by 1;
create table lockermat_opening_hours_
(
    id_           bigint primary key default nextval('lockermat_opening_hours_id_seq_'::regclass),
    lockermat_id_ bigint   not null
        constraint lockermat__fk references lockermat_ (id_) on delete restrict,
    weekday_      smallint not null,
    opens_at_     time     not null,
    closes_at_    time     not null,
    constraint lockermat_opening_hours_weekday__uq unique (lockermat_id_, weekday_),
    constraint lockermat_opening_hours_weekday__ck check (weekday_ between 1 and 7),
    constraint lockermat_opening_hours_hours__ck check (opens_at_ <> closes_at_ and opens_at_ < time '24:00')
);

create sequence lockermat_cell_id_seq_ start with 1 increment by 1;
create table lockermat_cell_
(
    id_           bigint primary key default nextval('lockermat_cell_id_seq_'::regclass),
    lockermat_id_ bigint      not null
        constraint lockermat__fk references lockermat_ (id_) on delete restrict,
    number_       smallint    not null,
    size_         varchar(10) not null,
    status_       varchar(16) not null default 'IN_SERVICE',
    constraint lockermat_cell_number__uq unique (lockermat_id_, number_),
    constraint lockermat_cell_id_size__uq unique (id_, size_),
    constraint lockermat_cell_number__ck check (number_ > 0),
    constraint lockermat_cell_size__ck check (size_ in ('S', 'M', 'L')),
    constraint lockermat_cell_status__ck check (status_ in ('IN_SERVICE', 'OUT_OF_SERVICE'))
);
create index lockermat_cell_lockermat_size__idx on lockermat_cell_ (lockermat_id_, size_) where status_ = 'IN_SERVICE';

create sequence tariff_id_seq_ start with 1 increment by 1;
create table tariff_
(
    id_                     bigint primary key default nextval('tariff_id_seq_'::regclass),
    size_                   varchar(10)   not null,
    valid_from_             timestamptz   not null,
    valid_to_               timestamptz,
    storage_price_per_day_  numeric(8, 2) not null,
    shipment_price_         numeric(8, 2) not null,
    overstay_price_per_day_ numeric(8, 2) not null,
    constraint tariff_id_size__uq unique (id_, size_),
    constraint tariff_size__ck check (size_ in ('S', 'M', 'L')),
    constraint tariff_validity__ck check (valid_to_ is null or valid_to_ > valid_from_),
    constraint tariff_prices__ck check (storage_price_per_day_ > 0 and shipment_price_ > 0 and overstay_price_per_day_ > 0),
    constraint tariff_no_overlap__ex exclude using gist (size_ with =, tstzrange(valid_from_, valid_to_, '[)') with &&)
);

create sequence customer_id_seq_ start with 1 increment by 1;
create table customer_
(
    id_                bigint primary key default nextval('customer_id_seq_'::regclass),
    keycloak_id_       uuid        not null
        constraint customer_keycloak_id__uq unique,
    phone_             varchar(16),
    company_name_      text,
    tax_id_            varchar(16),
    billing_address_   text,
    terms_version_     varchar(16) not null,
    terms_accepted_at_ timestamptz not null,
    created_at_        timestamptz not null default now(),
    constraint customer_phone__ck check (phone_ is null or phone_ ~ '^\+[1-9][0-9]{7,14}$'),
    constraint customer_invoice__ck check (tax_id_ is null or (company_name_ is not null and billing_address_ is not null))
);

create sequence order_id_seq_ start with 1 increment by 1;
create table order_
(
    id_               bigint primary key default nextval('order_id_seq_'::regclass),
    number_           varchar(20)    not null
        constraint order_number__uq unique,
    customer_id_      bigint         not null
        constraint customer__fk references customer_ (id_) on delete restrict,
    type_             varchar(16)    not null,
    size_             varchar(10)    not null,
    tariff_id_        bigint         not null,
    status_           varchar(16)    not null default 'AWAITING_PAYMENT',
    price_            numeric(10, 2) not null,
    payment_deadline_ timestamptz    not null,
    created_at_       timestamptz    not null default now(),
    closed_at_        timestamptz,
    constraint tariff__fk foreign key (tariff_id_, size_) references tariff_ (id_, size_) on delete restrict,
    constraint order_id_type__uq unique (id_, type_),
    constraint order_id_type_size__uq unique (id_, type_, size_),
    constraint order_type__ck check (type_ in ('STORAGE', 'SHIPMENT')),
    constraint order_status__ck check (status_ in ('AWAITING_PAYMENT', 'PAID', 'COMPLETED', 'CANCELLED', 'EXPIRED')),
    constraint order_price__ck check (price_ >= 0),
    constraint order_closed__ck check ((closed_at_ is not null) = (status_ in ('COMPLETED', 'CANCELLED', 'EXPIRED'))),
    constraint order_chronology__ck check (payment_deadline_ > created_at_ and (closed_at_ is null or closed_at_ >= created_at_))
);
create index order_customer_created__idx on order_ (customer_id_, created_at_ desc);
create index order_awaiting_payment__idx on order_ (payment_deadline_) where status_ = 'AWAITING_PAYMENT';
create index order_tariff__idx on order_ (tariff_id_);

create sequence reservation_id_seq_ start with 1 increment by 1;
create table reservation_
(
    id_           bigint primary key default nextval('reservation_id_seq_'::regclass),
    order_id_     bigint      not null,
    order_type_   varchar(16) not null generated always as (case when leg_ = 'STORAGE' then 'STORAGE' else 'SHIPMENT' end) stored,
    size_         varchar(10) not null,
    cell_id_      bigint      not null,
    leg_          varchar(16) not null,
    from_         timestamptz not null,
    to_           timestamptz not null,
    status_       varchar(16) not null default 'BOOKED',
    deposited_at_ timestamptz,
    collected_at_ timestamptz,
    constraint order__fk foreign key (order_id_, order_type_, size_) references order_ (id_, type_, size_) on delete restrict,
    constraint lockermat_cell__fk foreign key (cell_id_, size_) references lockermat_cell_ (id_, size_) on delete restrict,
    constraint reservation_id_cell_order__uq unique (id_, cell_id_, order_id_),
    constraint reservation_leg__ck check (leg_ in ('STORAGE', 'ORIGIN', 'DESTINATION')),
    constraint reservation_period__ck check (to_ > from_),
    constraint reservation_status__ck check (status_ in ('BOOKED', 'OCCUPIED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    constraint reservation_deposit__ck check ((deposited_at_ is not null) = (status_ in ('OCCUPIED', 'COMPLETED'))),
    constraint reservation_collect__ck check ((collected_at_ is not null) = (status_ = 'COMPLETED') and (collected_at_ is null or collected_at_ >= deposited_at_)),
    constraint reservation_no_double_booking__ex exclude using gist (cell_id_ with =, tstzrange(from_, to_, '[)') with &&) where (status_ in ('BOOKED', 'OCCUPIED')),
    constraint reservation_actual_occupancy__ex exclude using gist (cell_id_ with =, tstzrange(deposited_at_, collected_at_, '[)') with &&) where (deposited_at_ is not null)
);
create unique index reservation_leg__uq on reservation_ (order_id_, leg_) where status_ <> 'CANCELLED';
create index reservation_order__idx on reservation_ (order_id_);
create index reservation_overdue__idx on reservation_ (to_) where status_ = 'OCCUPIED';

create sequence shipment_id_seq_ start with 1 increment by 1;
create table shipment_
(
    id_                  bigint primary key default nextval('shipment_id_seq_'::regclass),
    order_id_            bigint         not null
        constraint shipment_order__uq unique,
    order_type_          varchar(16)    not null generated always as ('SHIPMENT') stored,
    recipient_name_      text           not null,
    recipient_phone_     varchar(16)    not null,
    declared_value_      numeric(10, 2) not null,
    courier_keycloak_id_ uuid,
    courier_assigned_at_ timestamptz,
    constraint order__fk foreign key (order_id_, order_type_) references order_ (id_, type_) on delete restrict,
    constraint shipment_recipient_phone__ck check (recipient_phone_ ~ '^\+[1-9][0-9]{7,14}$'),
    constraint shipment_declared_value__ck check (declared_value_ >= 0),
    constraint shipment_courier__ck check ((courier_keycloak_id_ is null) = (courier_assigned_at_ is null))
);
create index shipment_courier__idx on shipment_ (courier_keycloak_id_) where courier_keycloak_id_ is not null;

create sequence access_code_id_seq_ start with 1 increment by 1;
create table access_code_
(
    id_             bigint primary key default nextval('access_code_id_seq_'::regclass),
    reservation_id_ bigint      not null
        constraint reservation__fk references reservation_ (id_) on delete restrict,
    purpose_        varchar(16) not null,
    code_hmac_      bytea       not null,
    sent_to_phone_  varchar(16),
    valid_from_     timestamptz not null,
    valid_to_       timestamptz not null,
    status_         varchar(16) not null default 'ACTIVE',
    created_at_     timestamptz not null default now(),
    used_at_        timestamptz,
    constraint access_code_purpose__ck check (purpose_ in ('DROP_OFF', 'PICK_UP')),
    constraint access_code_status__ck check (status_ in ('ACTIVE', 'USED', 'REVOKED')),
    constraint access_code_hmac__ck check (octet_length(code_hmac_) = 32),
    constraint access_code_validity__ck check (valid_to_ > valid_from_),
    constraint access_code_issue_before_expiry__ck check (created_at_ < valid_to_),
    constraint access_code_used__ck check (
        (used_at_ is not null) = (status_ = 'USED')
            and (used_at_ is null or (used_at_ >= valid_from_ and used_at_ < valid_to_ and used_at_ >= created_at_))
        ),
    constraint access_code_phone__ck check (sent_to_phone_ is null or sent_to_phone_ ~ '^\+[1-9][0-9]{7,14}$'),
    constraint access_code_hmac_window__ex exclude using gist (code_hmac_ with =, tstzrange(valid_from_, valid_to_, '[)') with &&),
    constraint access_code_active_purpose__ex exclude using gist (reservation_id_ with =, purpose_ with =, tstzrange(valid_from_, valid_to_, '[)') with &&) where (status_ = 'ACTIVE')
);
create index access_code_reservation__idx on access_code_ (reservation_id_);

create sequence incident_id_seq_ start with 1 increment by 1;
create table incident_
(
    id_                      bigint primary key default nextval('incident_id_seq_'::regclass),
    cell_id_                 bigint      not null
        constraint lockermat_cell__fk references lockermat_cell_ (id_) on delete restrict,
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
    resolved_at_             timestamptz,
    constraint reservation__fk foreign key (reservation_id_, cell_id_, order_id_) references reservation_ (id_, cell_id_, order_id_) on delete restrict,
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
create index incident_reservation__idx on incident_ (reservation_id_);
create index incident_cell__idx on incident_ (cell_id_);
create index incident_open__idx on incident_ (created_at_) where status_ in ('OPEN', 'IN_PROGRESS');

create sequence cell_opening_id_seq_ start with 1 increment by 1;
create table cell_opening_
(
    id_                bigint primary key default nextval('cell_opening_id_seq_'::regclass),
    access_code_id_    bigint
        constraint access_code__fk references access_code_ (id_) on delete restrict,
    incident_id_       bigint
        constraint incident__fk references incident_ (id_) on delete restrict,
    channel_           varchar(16) not null,
    actor_keycloak_id_ uuid,
    result_            varchar(16) not null,
    requested_at_      timestamptz not null default now(),
    closed_at_         timestamptz,
    constraint cell_opening_channel__ck check (channel_ in ('KEYPAD', 'APP', 'SERVICE')),
    constraint cell_opening_result__ck check (result_ in ('PENDING', 'OPENED', 'DOOR_FAILED')),
    constraint cell_opening_grant__ck check (
        num_nonnulls(access_code_id_, incident_id_) = 1
            and (channel_ = 'SERVICE') = (incident_id_ is not null)
            and (channel_ = 'KEYPAD') = (actor_keycloak_id_ is null)
        ),
    constraint cell_opening_closed__ck check (closed_at_ is null or (result_ = 'OPENED' and closed_at_ >= requested_at_))
);
create unique index cell_opening_code_live__uq on cell_opening_ (access_code_id_) where result_ in ('PENDING', 'OPENED');
create index cell_opening_incident__idx on cell_opening_ (incident_id_) where incident_id_ is not null;
create index cell_opening_open_door__idx on cell_opening_ (requested_at_) where result_ = 'OPENED' and closed_at_ is null;

create sequence payment_id_seq_ start with 1 increment by 1;
create table payment_
(
    id_            bigint primary key default nextval('payment_id_seq_'::regclass),
    order_id_      bigint         not null
        constraint order__fk references order_ (id_) on delete restrict,
    kind_          varchar(16)    not null,
    amount_        numeric(10, 2) not null,
    status_        varchar(16)    not null default 'PENDING',
    provider_      varchar(32)    not null,
    provider_ref_  varchar(128),
    refund_of_id_  bigint,
    incident_id_   bigint,
    refundable_id_ bigint generated always as (case when kind_ in ('CHARGE', 'EXTENSION', 'OVERSTAY') and status_ = 'COMPLETED' then id_ end) stored,
    created_at_    timestamptz    not null default now(),
    completed_at_  timestamptz,
    constraint payment_refundable__uq unique (refundable_id_, order_id_, provider_),
    constraint payment__refund_of_fk foreign key (refund_of_id_, order_id_, provider_) references payment_ (refundable_id_, order_id_, provider_) on delete restrict,
    constraint incident__fk foreign key (incident_id_, order_id_) references incident_ (id_, order_id_) on delete restrict,
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
create unique index payment_pending_charge__uq on payment_ (order_id_) where kind_ = 'CHARGE' and status_ = 'PENDING';
create index payment_order__idx on payment_ (order_id_);
create index payment_refund_of__idx on payment_ (refund_of_id_) where refund_of_id_ is not null;
create index payment_incident__idx on payment_ (incident_id_) where incident_id_ is not null;

create sequence audit_event_id_seq_ start with 1 increment by 1;
create table audit_event_
(
    id_        bigint primary key default nextval('audit_event_id_seq_'::regclass),
    at_        timestamptz not null default now(),
    entity_    varchar(24) not null,
    entity_id_ bigint      not null,
    action_    varchar(32) not null,
    actor_     jsonb       not null,
    changes_   jsonb,
    constraint audit_event_actor__ck check (jsonb_typeof(actor_) = 'object' and actor_ ? 'kind'),
    constraint audit_event_changes__ck check (jsonb_typeof(changes_) = 'array')
);
create index audit_event_entity_at__idx on audit_event_ (entity_, entity_id_, at_);
