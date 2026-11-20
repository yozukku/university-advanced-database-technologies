create index ix1__idx on shipment_ (recipient_phone_);
create index ix2__idx on order_ (status_, created_at_);
create index ix3__idx on payment_ (created_at_);
create index ix4__idx on cell_opening_ (requested_at_);
create index jx1_email__idx on audit_event_ ((actor_ ->> 'email'));
create index jx1_phone__idx on audit_event_ ((actor_ ->> 'phone'));
create index jx2__idx on audit_event_ using gin (changes_ jsonb_path_ops) with (fastupdate = off);
