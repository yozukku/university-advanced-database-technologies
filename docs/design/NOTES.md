# Bagażomat schema v5 — integration and service-layer notes

Scope: everything DECISIONS-r1/r2/r4/r5 put outside the DDL. `:name` marks a bind parameter. Patterns 1.1–1.4, the 1.5 keypad variant and the section 3 fix were run in a disposable container. Smoke F2b runs 1.5 (a definite door failure, then a retry) and 1.6 end to end, and smoke R5-1 runs a lost terminal reply; smoke R4-2 runs the opening-hours predicate.

## 1. Business rules held by the service

- **Currency.** All money is PLN: tariffs, `order_.price_`, `payment_.amount_`, `shipment_.declared_value_`. The operator is Polish and the product is single-currency, so `payment_.currency_` is gone (D8). If a second currency ever appears, it needs a column on `tariff_`, `order_` and `payment_` together, not on `payment_` alone.
- **Order shape (C2, rejected).** The service creates a SHIPMENT order, its `shipment_` row and both legs in one transaction. A STORAGE order gets exactly one STORAGE leg. The DB only stops wrong combinations (D4); it does not force completeness.
- **Shipment legs (C13).** ORIGIN and DESTINATION sit in different lockermats. The DESTINATION deposit comes only after the ORIGIN collection by the assigned courier. Both checks are cross-row, so they run under the order lock (see 1.5).
- **Tariff valid at order creation (C5).** Pick the tariff in the same statement that creates the order (1.2).
- **Refund ceiling (C3, second part).** The sum of PENDING + COMPLETED refunds never exceeds the captured payment (1.1).
- **Paid once (r2 #1).** The DB allows only one PENDING CHARGE per order. A second COMPLETED charge is a real capture (for example a late webhook for an attempt the service already cancelled), so it is recorded and refunded through 1.1. Before starting a new attempt, lock the order and require `AWAITING_PAYMENT` with no completed charge. Settlement takes the same order lock.
- **Service area (r2 #13).** `lockermat_location__ck` is a service-area rule: Europe including the Canary Islands and Madeira (lon -25..45, lat 27..72). It also catches swapped (lat, lng) points, because every seed longitude is below 27. Widening the area means changing this CHECK.
- **Incident reporter (r2 #4).** A CUSTOMER incident stores no reporter id. The reporter is the order's customer, reached through reservation → order → customer.
- **Also service-side:** DROP_OFF and regular PICK_UP code windows lie inside the reservation window (the exception is overstay pick-up, 1.6). Planned drop-off and pick-up instants fall inside opening hours (1.7). Compensation for a shipment is capped at `declared_value_`.

### 1.1 Refund (ceiling + race)

Run at READ COMMITTED. The `for update` serializes refunds of one capture. The insert then reads a fresh snapshot. Zero rows means reject. A failed or cancelled refund is never edited; a retry is a new row.

```sql
begin isolation level read committed;
select id_ from payment_ where id_ = :capture for update;
insert into payment_ (order_id_, kind_, amount_, provider_, refund_of_id_, incident_id_)
select p.order_id_, 'REFUND', :amount, p.provider_, p.id_, :incident
from payment_ p
where p.refundable_id_ = :capture
  and :amount > 0
  and :amount <= p.amount_ - (select coalesce(sum(r.amount_), 0)
                              from payment_ r
                              where r.refund_of_id_ = p.id_ and r.status_ in ('PENDING', 'COMPLETED'))
returning id_;
commit;
```

`refundable_id_` is non-null only for a COMPLETED CHARGE/EXTENSION/OVERSTAY, so the filter already refuses pending, failed and refund rows.

### 1.2 Tariff pick when creating the order

One quote per order (D3). `now()` is the same instant as the `created_at_` default in this transaction. Zero rows means no valid tariff.

```sql
insert into order_ (number_, customer_id_, type_, size_, tariff_id_, price_, payment_deadline_)
select :number, :customer, :type, t.size_, t.id_,
       case :type
           when 'STORAGE' then t.storage_price_per_day_ * ceil(extract(epoch from (:to - :from)) / 86400)
           else t.shipment_price_
       end,
       now() + interval '15 minutes'
from tariff_ t
where t.size_ = :size
  and tstzrange(t.valid_from_, t.valid_to_, '[)') @> now()
returning id_;
```

A price change is a new tariff row (close `valid_to_`, insert the next one). Never update prices in place: old orders and overstay fees must stay reproducible.

### 1.3 Cell picker and booking insert (C6)

It replaces `LockermatCellRepository.findAnyWithoutActiveReservations`. Today that method only checks "some reservation ends after now". It ignores the requested interval, cancelled rows, overstays, suspended lockers and faulty cells.

```sql
select c.id_
from lockermat_cell_ c
         join lockermat_ l on l.id_ = c.lockermat_id_
where l.id_ = :locker and l.status_ = 'ACTIVE'
  and c.size_ = :size and c.status_ = 'IN_SERVICE'
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                    and tstzrange(r.from_, r.to_, '[)') && tstzrange(:from, :to, '[)'))
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= current_timestamp)
order by c.number_
limit 1
for update of c skip locked;

insert into reservation_ (order_id_, size_, cell_id_, leg_, from_, to_)
select o.id_, o.size_, :cell, :leg, :from, :to
from order_ o
where o.id_ = :order_id;
```

The `reservation_no_double_booking__ex` exclusion still catches a racing booking (SQLSTATE 23P01). On 23P01, pick the next cell. The availability search for the map uses the same predicates.

### 1.4 Cancellation (C6)

`ReservationService.cancel` deletes the row today. That erases history, and under the new schema it fails because of access codes and payments. Replace it with status changes in one transaction. The first update must return one row. A settled charge then goes through 1.1.

Refuse cancellation while any door command for the order is PENDING (r5 #1). Run this right after the lock; one row means stop:

```sql
select id_ from order_ where id_ = :order_id for update;
select x.id_
from cell_opening_ x
         join access_code_ a on a.id_ = x.access_code_id_
         join reservation_ r on r.id_ = a.reservation_id_
where r.order_id_ = :order_id and x.result_ = 'PENDING';
update order_ o set status_ = 'CANCELLED', closed_at_ = current_timestamp
where o.id_ = :order_id and o.status_ in ('AWAITING_PAYMENT', 'PAID')
  and not exists (select 1 from reservation_ r where r.order_id_ = o.id_ and r.status_ in ('OCCUPIED', 'COMPLETED'))
returning id_;
update reservation_ set status_ = 'CANCELLED' where order_id_ = :order_id and status_ = 'BOOKED';
update access_code_ a set status_ = 'REVOKED'
from reservation_ r
where r.id_ = a.reservation_id_ and r.order_id_ = :order_id and a.status_ = 'ACTIVE';
```

The `for update` on the order is the serialization point for every cancellation, relocation and redemption (r2 #7), including STORAGE. Run it as a separate statement in the same READ COMMITTED transaction, before any check, so the following statements read a fresh snapshot after the wait.

**NO_SHOW and order closing** go through the same order lock and PENDING guard as cancellation (r6 #1). **Relocation** (incident, overstay of the previous guest) and **code reissue** take the same order lock and the same PENDING guard. Relocation uses the same steps for one leg: revoke its codes, cancel the leg, insert a new leg with the same `leg_` (1.3), issue new codes. Never `update reservation_ set cell_id_`: once an incident points at the leg, the DB refuses it.

### 1.5 Code redemption and the door journal (outbox, r5 #1)

The door command goes out only after COMMIT (r2 #7). The `cell_opening_` row is the command record. There are two short READ COMMITTED transactions, each taking the order lock as a separate statement first.

**Tx 1, request (keypad).** The terminal sends its authenticated locker and the HMAC of the typed code.
1. Resolve the candidate.
2. Lock the order.
3. Lock the cell row. Always lock the order first and then the cell, so there is no deadlock (r6 #1).
4. Validate the code exactly as in v3. For a DROP_OFF, also require "no bag inside" and "no PENDING door command on this cell from any grant", whether an access code of any order or an incident. A lost reply on the previous booking may have left a bag inside. The occupancy exclusion fires only in Tx 2, after the door has already opened.
5. Insert a `PENDING` opening. `requested_at_` is the post-lock statement time.
6. COMMIT, then send the opening id to the terminal.

`cell_opening_code_live__uq` (one PENDING or OPENED row per code) rejects a second request while one is pending. No row from step 4 means reject.

```sql
select a.reservation_id_
from access_code_ a
         join reservation_ r on r.id_ = a.reservation_id_
         join lockermat_cell_ c on c.id_ = r.cell_id_
where c.lockermat_id_ = :terminal_locker and a.code_hmac_ = :hmac and a.status_ = 'ACTIVE'
  and tstzrange(a.valid_from_, a.valid_to_, '[)') @> statement_timestamp();

select o.id_
from order_ o
         join reservation_ r on r.order_id_ = o.id_
where r.id_ = :candidate_reservation
for update of o;

select c.id_
from lockermat_cell_ c
         join reservation_ r on r.cell_id_ = c.id_
where r.id_ = :candidate_reservation
for update of c;

insert into cell_opening_ (access_code_id_, channel_, result_, requested_at_)
select a.id_, 'KEYPAD', 'PENDING', statement_timestamp()
from access_code_ a
         join reservation_ r on r.id_ = a.reservation_id_
         join lockermat_cell_ c on c.id_ = r.cell_id_
         join order_ o on o.id_ = r.order_id_
where r.id_ = :candidate_reservation
  and c.lockermat_id_ = :terminal_locker and o.status_ = 'PAID'
  and a.code_hmac_ = :hmac and a.status_ = 'ACTIVE'
  and tstzrange(a.valid_from_, a.valid_to_, '[)') @> statement_timestamp()
  and ((a.purpose_ = 'DROP_OFF' and r.status_ = 'BOOKED'
            and not exists (select 1 from reservation_ x
                            where x.cell_id_ = r.cell_id_ and x.deposited_at_ is not null and x.collected_at_ is null)
            and not exists (select 1
                            from cell_opening_ p
                                     left join access_code_ pa on pa.id_ = p.access_code_id_
                                     left join reservation_ pr on pr.id_ = pa.reservation_id_
                                     left join incident_ pi on pi.id_ = p.incident_id_
                            where p.result_ = 'PENDING' and coalesce(pr.cell_id_, pi.cell_id_) = r.cell_id_))
    or (a.purpose_ = 'PICK_UP' and r.status_ = 'OCCUPIED'))
returning id_, (select c2.number_ from reservation_ r2 join lockermat_cell_ c2 on c2.id_ = r2.cell_id_ where r2.id_ = :candidate_reservation) as door_;
```

**Tx 2, terminal reply.** Lock the order through the opening (same `for update of o`, joined from `cell_opening_ x` → code → reservation → order).

If the door opened, run this. It must return one row; otherwise roll back.

```sql
with opening as (
         update cell_opening_ set result_ = 'OPENED'
         where id_ = :opening and result_ = 'PENDING'
         returning access_code_id_, requested_at_),
     code as (
         update access_code_ a set status_ = 'USED', used_at_ = o.requested_at_
         from opening o
         where a.id_ = o.access_code_id_ and a.status_ = 'ACTIVE'
         returning a.id_, a.reservation_id_, a.purpose_, o.requested_at_)
update reservation_ r
set status_       = case c.purpose_ when 'DROP_OFF' then 'OCCUPIED' else 'COMPLETED' end,
    deposited_at_ = case c.purpose_ when 'DROP_OFF' then c.requested_at_ else r.deposited_at_ end,
    collected_at_ = case c.purpose_ when 'PICK_UP' then c.requested_at_ end
from code c
where r.id_ = c.reservation_id_
  and ((c.purpose_ = 'DROP_OFF' and r.status_ = 'BOOKED') or (c.purpose_ = 'PICK_UP' and r.status_ = 'OCCUPIED'))
returning r.id_;
```

On a definite failure, run the statement below. The code stays ACTIVE and the leg is untouched, so a retry starts a fresh Tx 1.

```sql
update cell_opening_ set result_ = 'DOOR_FAILED' where id_ = :opening and result_ = 'PENDING';
```

A door-closed event runs:

```sql
update cell_opening_ set closed_at_ = :at where id_ = :opening and result_ = 'OPENED' and closed_at_ is null;
```

- **Lost reply.** The terminal call times out after about 10 s, which counts as a lost reply, not a failure. The row stays `PENDING` for reconciliation, by support or a TERMINAL incident. While it is pending, the code cannot be redeemed again, and the order cannot be cancelled, relocated or given a reissued code (1.4). A pick-up leg stays OCCUPIED.
- **Door closed with no opening.** If the terminal reports a door closing that matches no OPENED row, the service raises a TERMINAL incident.
- **Door left open.** An `OPENED` row with no `closed_at_` after N minutes becomes a TERMINAL `DOOR_LEFT_OPEN` incident; `cell_opening_open_door__idx` finds such rows.

**App variant ("Otwórz zdalnie", r2 #8).** The candidate is `:reservation`. Tx 2 and the lock step are the same. In the Tx 1 insert:
- drop `a.code_hmac_ = :hmac`;
- write the row with `channel_ = 'APP'` and `actor_keycloak_id_ = :subject`;
- bind the verified Keycloak subject with the predicate below. The owner opens STORAGE legs and drops off at ORIGIN. The assigned courier picks up at ORIGIN and drops off at DESTINATION. The recipient uses the keypad code sent to `sent_to_phone_`.

```sql
and r.id_ = :reservation
and a.purpose_ = :purpose
and (
    ((r.leg_ = 'STORAGE' or (r.leg_ = 'ORIGIN' and a.purpose_ = 'DROP_OFF'))
     and exists (select 1 from customer_ u
                 where u.id_ = o.customer_id_ and u.keycloak_id_ = :subject))
    or
    (((r.leg_ = 'ORIGIN' and a.purpose_ = 'PICK_UP')
      or (r.leg_ = 'DESTINATION' and a.purpose_ = 'DROP_OFF'))
     and exists (select 1 from shipment_ s
                 where s.order_id_ = o.id_ and s.courier_keycloak_id_ = :subject))
)
```

- **Previous bag still inside.** If the Tx 1 occupancy check finds a bag, the previous guest is overstaying. Do not open the door; relocate instead (1.4). `reservation_actual_occupancy__ex` remains the final guard in Tx 2.
- **Staff SERVICE opening (incident handling).** Use the same outbox: insert a `PENDING` row `(incident_id_, 'SERVICE', :staff, 'PENDING')`, commit, send, and record the reply. No code is consumed. The cell is the incident's `cell_id_`.
- **Door history of a cell.** Union the openings reached through `access_code_ → reservation_.cell_id_` with those reached through `incident_.cell_id_`. `cell_opening_` deliberately has no `cell_id_` of its own, so the cell cannot disagree with the grant.
- **SHIPMENT legs.** For a DESTINATION DROP_OFF, also require ORIGIN `COMPLETED` with `collected_at_ <= at_`. The order lock above already covers it.
- **Code value.** `code_hmac_` = HMAC-SHA256(server secret, code), 32 bytes. A plain SHA-256 of a 6–8 digit code is brute-forced in seconds. A value stays reserved for its whole issued window in every status (`access_code_hmac_window__ex`). A new value for an overlapping window must be freshly generated.

### 1.6 Overstay pick-up (r2 #9)

DROP_OFF and regular PICK_UP codes stay inside the booking window. Once the booking has ended, collection works like this:
1. The OVERSTAY payment settles.
2. Under the order lock (1.5), after authenticating the customer and checking that the fee is settled, the service issues a short-lived PICK_UP code for the OCCUPIED leg.
3. The code is redeemed through 1.5.

`to_` is left unchanged, so it still prices the fee. A still-valid earlier pick-up code is either reused or revoked first.

```sql
insert into access_code_ (reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_)
select r.id_, 'PICK_UP', :new_hmac, statement_timestamp(),
       statement_timestamp() + interval '15 minutes'
from reservation_ r
         join order_ o on o.id_ = r.order_id_
where r.id_ = :reservation and r.status_ = 'OCCUPIED'
  and r.to_ <= statement_timestamp() and o.status_ = 'PAID'
returning id_;
```

### 1.7 Opening hours (r4 #2)

`lockermat_opening_hours_` has at most one interval per ISO weekday, in the locker's `time_zone_`:
- a locker with no rows is open 24/7;
- a weekday without a row is closed;
- `closes_at_ < opens_at_` runs past midnight and belongs to the day it starts;
- a full day is `00:00`–`24:00`.

```sql
select not exists (select 1 from lockermat_opening_hours_ h where h.lockermat_id_ = l.id_)
           or exists (select 1
                      from lockermat_opening_hours_ h
                      where h.lockermat_id_ = l.id_
                        and case
                                when h.opens_at_ < h.closes_at_
                                    then h.weekday_ = extract(isodow from t.local_) and t.local_::time >= h.opens_at_ and t.local_::time < h.closes_at_
                                else (h.weekday_ = extract(isodow from t.local_) and t.local_::time >= h.opens_at_)
                                    or (h.weekday_ = extract(isodow from t.local_ - interval '1 day') and t.local_::time < h.closes_at_)
                            end) as open_
from lockermat_ l
         cross join lateral (select :at at time zone l.time_zone_ as local_) t
where l.id_ = :locker;
```

Search and checkout evaluate the planned drop-off and pick-up instants separately. A bag may stay inside while the premises are closed. Holidays and exception dates are out of scope.

## 2. Repo code changes (C6, C7, O6, F14)

- **`LockermatEntity.getPosition`.** It builds `new Position(x, y)`, but `Position` is `(latitude, longitude)`. The fix is `new Position(BigDecimal.valueOf(location.getY()), BigDecimal.valueOf(location.getX()))`. `PersistenceUtils.toPoint` (x = lng) and `stDistance` are already correct.
- **`PostgreSqlFunction.stDistance`.** Order by `location_::geography <-> st_setsrid(st_makepoint(:lng, :lat), 4326)::geography` (KNN). Then the query uses `lockermat_location_geog__idx`; `st_distance` in ORDER BY never does.
- **`ReservationService.reserve`.** Order first (1.2), then cell picker and insert (1.3).
- **`ReservationService.cancel`.** Replace with 1.4.
- **JPA mapping (`ddl-auto: validate`).**
  - Generated columns `reservation_.order_type_`, `shipment_.order_type_` and `payment_.refundable_id_` need `@Column(insertable = false, updatable = false)`, or must stay unmapped.
  - Types: `code_hmac_` → `byte[]`, `number_` → `Short`, `lockermat_opening_hours_.opens_at_/closes_at_` → `LocalTime`, `weekday_` → `Short`, all `timestamptz` → `Instant`.
  - Composite FKs, partial uniques and exclusions are invisible to the validator.
- **Door transactions (r5 #4).** The two §1.5 transactions run as native SQL or short JPQL updates. Never hold a managed entity or a transaction open across the terminal call.
- **Flush rule (r2 #5).** Hibernate flushes all INSERTs before all UPDATEs. Three uniqueness rules retire an old row and insert its replacement: `reservation_leg__uq`, `access_code_active_purpose__ex` and `payment_pending_charge__uq`. For these, the retiring UPDATE must reach the database first: use `saveAndFlush`, or a JPQL update, before saving the replacement.

## 3. Coordinate data fix

The last statement of `V20251217.1703` stores every seed point as (lat, lng). Never edit an applied migration (Flyway checksum). In the new migration, and **before** adding `lockermat_location__ck`, flip only rows that still match an original seed tuple exactly. A blanket `st_flipcoordinates` would corrupt rows the app already wrote correctly.

```sql
with seed(address_, lng_, lat_) as (values
    ('Kamieńskiego Office', 19.963635273352168, 50.0272202438108),
    ('Millennium Hall', 22.01456717598967, 50.02726469603428),
    ('Port Szczecin', 14.578076, 53.418163),
    ('DB Port Szczecin', 14.581866, 53.42414),
    ('Tychy', 19.027340626981584, 50.10415637198125),
    ('Wallbox 1', 18.148554422891664, 51.69098356879579),
    ('Kraków 2', 19.974273574166773, 50.06286510353098),
    ('PNTK', 18.036534, 51.741369),
    ('Serwis Łomża', 22.05369, 53.155931),
    ('Serwis Poznań', 16.928109494410535, 52.41029087660476),
    ('Hu Park Albatros', 10.53963710940954, 43.026423190158596),
    ('La Croix du Vieux Pont', 3.133358, 49.404422),
    ('Frankfurt Vieux', 8.71316553787534, 50.019218915188475),
    ('Tallin', 24.746462, 59.436745),
    ('De Murrin', 16.936649417506317, 52.40813518568709),
    ('Ministerstwo cyfryzacji', 21.00897739681426, 52.23690127542494),
    ('Da Orffo', 19.959698, 50.076287),
    ('White Office', 19.96288277433635, 50.02723655010317),
    ('Serwis Szczecin', 14.542233732819398, 53.42670464590887),
    ('Budimex demo', 19.79221558710421, 49.9779623198535),
    ('Łysoń', 19.53830497799396, 49.88346304848122),
    ('Public Safety Solutions', 15.44267394869587, 47.0104487664257),
    ('Elcamp', 19.87474782394355, 50.034663402849105))
update lockermat_ l set location_ = st_flipcoordinates(l.location_)
from seed s
where l.address_ = s.address_
  and st_x(l.location_) = s.lat_::double precision
  and st_y(l.location_) = s.lng_::double precision;
```

Checked on a replay of the three repo migrations: 0 of 23 rows lie inside the Europe box before the fix, 23 of 23 after it. Run `getPosition` and this migration in the same release. Otherwise the map shows mirrored markers.

## 4. Flyway incremental migration and seed backfill

`schema.sql` is the target state written as `create` DDL. Existing databases already have `V20250601.0311` applied, so the target ships as **one new migration** (for example `V2026MMDD.HHMM__schema_v4.sql`) in this order. The existing extension migration installs only PostGIS, so the migration starts with (r2 #11):

```sql
create extension if not exists btree_gist;
create extension if not exists pg_trgm;
```

1. **New parent tables.** Create `tariff_`, `customer_` and `order_` (each with its sequence). Insert the three tariff rows (S/M/L). Every order needs one.
2. **`lockermat_`.** Add `code_`, `name_`, `time_zone_` (default `'Europe/Warsaw'`), `status_` and `created_at_` as nullable.
   - Backfill: `code_ = 'LM-' || lpad(id_::text, 4, '0')`, `name_ = address_`. The seed "addresses" are really names; real addresses are entered later. Set `time_zone_ = 'Europe/Tallinn'` for "Tallin" and the matching IANA zone for "Hu Park Albatros" (IT), "La Croix du Vieux Pont" (FR) and "Frankfurt Vieux" (DE).
   - Run the coordinate fix (section 3).
   - Then `set not null`, add the checks, drop the old index if any, and create `lockermat_location_geog__idx` and the trigram index.
3. **`lockermat_cell_`.**
   - Add `number_`, backfilled with `row_number() over (partition by lockermat_id_ order by id_)`, then `set not null`.
   - Add `status_`.
   - Replace `lockermat__fk ... on delete cascade` with `on delete restrict`.
   - Add `unique (id_, size_)` and the checks.
4. **`reservation_`.**
   - The current rows are test bookings with no order, customer or payment. The migration deletes them (`delete from reservation_`).
   - Convert `from_/to_` with `type timestamptz using from_ at time zone '<JVM zone>'`. No `hibernate.jdbc.time_zone` is configured, so the existing values were written in the JVM default zone: Europe/Warsaw on a dev laptop, usually UTC in a container.
   - Add `order_id_`, `size_`, the generated `order_type_`, `leg_`, `status_`, `deposited_at_` and `collected_at_`.
   - Replace `lockermat_cell__fk ... on delete cascade` with the composite FK.
   - Add the uniques, checks, exclusions and indexes.
5. **Remaining tables.** Create `lockermat_opening_hours_`, `shipment_`, `access_code_`, `incident_`, `cell_opening_` and `payment_`. Both new tables start empty: no hours rows means every locker is open 24/7 until real hours are entered, and earlier openings have no journal.
6. **`src/test/resources/test_data.sql`.**
   - Insert `code_` and `name_`. Use real European points: `point(10 20)` is outside the box and is now rejected (`point(30 40)` passes).
   - Insert `number_` for cells.
   - Create a customer, an order and a size for each reservation.
   - It truncates with `cascade`. Keep that, or truncate all twelve tables.

For a dev-only setup there is an alternative: `flyway clean`, then a single baseline migration built from `schema.sql`, plus a rewritten seed in (lng, lat) without the final flip. It is legitimate only if no environment holds data worth keeping.
