create index ix1__idx on shipment_ (recipient_phone_);
create index ix2__idx on order_ (status_, created_at_);
create index ix3__idx on payment_ (created_at_);
create index ix4__idx on cell_opening_ (requested_at_);
create index jx1_email__idx on audit_event_ ((cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin));
create index jx1_phone__idx on audit_event_ ((cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin));
create index jx2__idx on audit_event_ ((cast(changes_new_ as char(32) array)));
