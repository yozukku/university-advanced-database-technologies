# Katalog scenariuszy

Plik powstaje z rejestru `bench/scenarios/`, z `bench/scenarios/ops.yaml`, z `docs/bench/indexes.yaml` i ze skryptów `bench/ddl/<silnik>/idx/`. Nie edytuj go ręcznie: `make catalogue` zapisuje go od nowa, a `make catalogue CHECK=1` sprawdza katalog i zgodność pliku z rejestrem.

Scenariusze podstawowe: 26 (C 6, R 8, U 6, D 6) we wszystkich czterech SZBD. Scenariusze JSON: 6 (C 1, R 3, U 1, D 1) w PostgreSQL, MySQL i MongoDB. Neo4j przechowuje `actor_` i `changes_` jako tekst JSON bez indeksów ścieżek, więc nie wykonuje serii J.

Flagi: CX — złożony odczyt (złączenie, agregacja, przejście grafu albo zapytanie przestrzenne); BA — pomiar w konfiguracji BASE i IDX (pozostałe scenariusze tylko w IDX); H1-S, H1-I, H1-U — zbiory SELECT, INSERT i UPDATE hipotezy H1. Kolumna „Indeks IDX” podaje dla odczytu indeks, który go obsługuje, a dla zapisu indeksy, które zapis utrzymuje.

Parametry: `%(nazwa)s` i `%s` w SQL, `$nazwa` w Cypher, `:nazwa` w wywołaniach MongoDB. `{marks}` i `{rows}` to listy znaczników, które adapter MySQL wstawia dla partii.

## Przegląd

| Id | Operacja | Opis | Flagi | Indeks IDX |
|---|---|---|---|---|
| C1 | C | Rejestracja 10 000 nowych klientów w transakcjach po 100 (wielowierszowy INSERT, unikalny identyfikator Keycloak) | — | — |
| C2 | C | Dopisanie 100 000 wpisów dziennika drzwi (nieudane otwarcia kodem z klawiatury) partiami po 1000 w jednej transakcji na partię | BA, H1-I | IX4 |
| C3 | C | Rezerwacja skrytki ×1000: zamówienie, noga, opłata i dwa kody w jednej transakcji, z wyborem taryfy, wolnej skrytki i kontrolą nakładania rezerwacji | BA, H1-I | IX2, IX3 |
| C4 | C | Nadanie przesyłki ×1000: zamówienie, przesyłka, dwie nogi w różnych punktach, cztery kody i opłata w jednej transakcji, z wyborem taryfy i wolnych skrytek oraz zapisem połączenia między punktami | BA, H1-I | IX1, IX2, IX3 |
| C5 | C | Synchronizacja 10 000 klientów według identyfikatora Keycloak w transakcjach po 100: połowa istnieje i dostaje nowy telefon i regulamin, połowa zostaje wstawiona | — | — |
| C6 | C | Naliczenie opłat za przetrzymanie bagażu dla wszystkich zajętych skrytek po terminie: INSERT z zapytania z ceną z taryfy zamówienia za każdą rozpoczętą dobę, partiami po 5000 zamówień | BA, H1-I | IX3 |
| R1 | R | Szczegóły zamówienia według id: zamówienie, jego rezerwacje z punktem (id, nazwa, adres), kody dostępu i płatności | CX | — |
| R2 | R | „Moje rezerwacje”: strona 3 (20 wierszy) zamówień klienta od najnowszego | — | — |
| R3 | R | 10 najbliższych aktywnych punktów w promieniu 5 km z wolną skrytką danego rozmiaru w wybranym oknie czasu, ×200 lokalizacji | CX | — |
| R4 | R | „Do odbioru”: przesyłki na numer telefonu odbiorcy, których skrytka docelowa jest zajęta, z punktem i numerem skrytki, ×100 numerów | BA, CX, H1-S | IX1 |
| R5 | R | Ranking 20 punktów według liczby zamówień utworzonych w ostatnich 30 dniach i teraz zakończonych (punkt skrytki przechowania albo nadania; filtr na dacie utworzenia, nie zakończenia) | BA, CX, H1-S | IX2 |
| R6 | R | Przychód netto każdego punktu w jednym miesiącu (zrealizowane opłaty minus zwroty i rekompensaty, w groszach), ×12 miesięcy; płatność należy do punktu skrytki przechowania albo, dla przesyłki, skrytki nadania | BA, CX, H1-S | IX3 |
| R7 | R | Aktywność drzwi każdego punktu w oknie 24 h: liczba otwarć kodem i liczba nieudanych (DOOR_FAILED), z której wynika ich udział, bez otwarć serwisowych; ×30 dni | BA, CX, H1-S | IX4 |
| R8 | R | Punkty osiągalne z danego punktu po połączeniach przesyłek z ostatnich 90 dni z najmniejszą liczbą przeskoków ≤ 3, ×50 punktów startowych | CX | — |
| U1 | U | Zamknięcie 5000 opłaconych zamówień (PAID → COMPLETED) według id, w transakcjach po 1000 zamówień | BA, H1-U | IX2 |
| U2 | U | Użycie kodu nadania ×1000: otwarcie skrytki → OPENED, kod → USED, noga → OCCUPIED w jednej transakcji, z kontrolą faktycznego zajęcia skrytki | — | — |
| U3 | U | Wygaszenie nieopłaconych zamówień po terminie płatności (→ EXPIRED) i anulowanie ich nóg (→ CANCELLED), partiami po 5000 zamówień | BA | IX2 |
| U4 | U | Wycofanie 20 automatów z eksploatacji w jednej transakcji: ich skrytki → OUT_OF_SERVICE, przyszłe zarezerwowane nogi → CANCELLED, aktywne kody tych nóg → REVOKED | — | — |
| U5 | U | Korekta numeru telefonu odbiorcy 5000 przesyłek według id zamówienia, w transakcjach po 1000 przesyłek | BA, H1-U | IX1 |
| U6 | U | Unieważnienie wszystkich aktywnych kodów dostępu po upływie ich ważności (ACTIVE → REVOKED), partiami po 5000 kodów | — | — |
| D1 | D | Usunięcie wpisów dziennika otwarć skrytek według id, w transakcjach po 100 wpisów | — | — |
| D2 | D | Usunięcie zamówień ze wszystkimi zależnymi wierszami, od dzieci do rodzica w 7 tabelach, jedno zamówienie na transakcję | — | — |
| D3 | D | Usunięcie wpisów dziennika otwarć skrytek starszych niż 540 dni przed T0, partiami po 5000 | — | — |
| D4 | D | Usunięcie klientów bez żadnego zamówienia (antyzłączenie), partiami po 5000 klientów | — | — |
| D5 | D | Usunięcie anulowanych i wygasłych zamówień starszych niż rok przed T0 ze wszystkimi zależnymi wierszami, partiami po 5000 zamówień | — | — |
| D6 | D | Usunięcie nieużywanych punktów razem ze skrytkami i godzinami otwarcia po sprawdzeniu, że żadna rezerwacja ani zgłoszenie nie wskazuje ich skrytek, partiami po 5000 punktów | — | — |
| J1 | C | Dopisanie 10 000 zdarzeń audytu (migawka aktora i lista zmian w JSON) partiami po 1000 w jednej transakcji na partię; rodzaje aktorów i zmiany jak w danych | BA, H1-I | JX1, JX2 |
| J2 | R | RODO art. 15: wszystkie zdarzenia audytu osoby w kolejności czasu, wyszukane w migawce aktora po e-mailu lub telefonie (klient: e-mail i telefon, odbiorca: telefon), ×100 osób | BA, H1-S | JX1 |
| J3 | R | Istnienie kluczy JSON: liczba zdarzeń audytu na rodzaj aktora, w tym z e-mailem i tylko z imieniem lub telefonem (cała tabela) | — | — |
| J4 | R | Wyszukiwanie elementu tablicy JSON: zdarzenia audytu z jednego miesiąca, których lista zmian zawiera zmianę status_ na CANCELLED, policzone według encji, ×12 miesięcy | BA, H1-S | JX2 |
| J5 | U | RODO art. 17: pseudonimizacja 100 osób (klient: e-mail i telefon, odbiorca: telefon) we wszystkich ich zdarzeniach audytu: e-mail zastąpiony skrótem HMAC-SHA256 z kluczem, imię i telefon usunięte z migawki aktora, partiami po 5000 zdarzeń | BA | JX1 |
| J6 | D | Retencja: usunięcie zdarzeń audytu niedotyczących płatności, starszych niż 18 miesięcy przed T0, partiami po 5000 | — | — |

## Zbiory hipotezy H1

| Zbiór | Operacja | Scenariusze |
|---|---|---|
| H1-S | SELECT | R4, R5, R6, R7, J2, J4 |
| H1-I | INSERT | C2, C3, C4, C6, J1 |
| H1-U | UPDATE | U1, U5 |
| poza werdyktem (BA) | UPDATE | U3, J5 |

## Scenariusze podstawowe

### C1 — tworzenie (INSERT)

Rejestracja 10 000 nowych klientów w transakcjach po 100 (wielowierszowy INSERT, unikalny identyfikator Keycloak)

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 10000`, `ops_xs: 100`, `batch: 100`.

**PostgreSQL**

```sql
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
select * from unnest(%(id)s::bigint[], %(keycloak)s::uuid[], %(phone)s::varchar[], %(terms)s::varchar[],
                     %(at)s::timestamptz[], %(at)s::timestamptz[])
```

**MySQL**

```sql
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
values (%s, %s, %s, %s, %s, %s)
```

**MongoDB**

```javascript
customers.insertMany([{_id, keycloakId, phone, termsVersion, termsAcceptedAt, createdAt}, …]) in one transaction per batch
```

**Neo4j**

```cypher
UNWIND $rows AS row
CREATE (:Customer {id: row.id, keycloakId: row.keycloak, phone: row.phone, termsVersion: row.terms,
                   termsAcceptedAt: row.at, createdAt: row.at})
```

### C2 — tworzenie (INSERT)

Dopisanie 100 000 wpisów dziennika drzwi (nieudane otwarcia kodem z klawiatury) partiami po 1000 w jednej transakcji na partię

Flagi: BA, H1-I. Indeks IDX: IX4. Ustawienia z `ops.yaml`: `ops: 100000`, `ops_xs: 1000`, `batch: 1000`.

**PostgreSQL**

```sql
insert into cell_opening_ (id_, access_code_id_, channel_, result_, requested_at_)
select * from unnest(%(id)s::bigint[], %(code)s::bigint[], %(channel)s::varchar[], %(result)s::varchar[],
                     %(at)s::timestamptz[])
```

**MySQL**

```sql
insert into cell_opening_ (id_, access_code_id_, channel_, result_, requested_at_)
values (%s, %s, %s, %s, %s)
```

**MongoDB**

```javascript
orders.bulkWrite([{updateOne: {filter: {'reservations.accessCodes.id': :code}, update: {$push: {'reservations.$[leg].accessCodes.$[code].openings': {id, channel, result, requestedAt}}}, arrayFilters: [{'leg.accessCodes.id': :code}, {'code.id': :code}]}}, …]) in one transaction per batch
```

**Neo4j**

```cypher
UNWIND $rows AS row
MATCH (a:AccessCode {id: row.code})
CREATE (:CellOpening {id: row.id, channel: row.channel, result: row.result, requestedAt: row.at})-[:OPENED_WITH]->(a)
```

### C3 — tworzenie (INSERT)

Rezerwacja skrytki ×1000: zamówienie, noga, opłata i dwa kody w jednej transakcji, z wyborem taryfy, wolnej skrytki i kontrolą nakładania rezerwacji

Flagi: BA, H1-I. Indeks IDX: IX2, IX3. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 20`, `batch: 1`, `days_after_t0: 40`, `window_hours: 4`.

**PostgreSQL**

```sql
with cell as (
    select c.id_
    from lockermat_cell_ c
    join lockermat_ l on l.id_ = c.lockermat_id_
    where l.id_ = %(locker)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                        and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
    order by c.number_
    limit 1
    for update of c skip locked
), placed as (
    insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_,
                        created_at_)
    select %(order)s, %(number)s, %(customer)s, 'STORAGE', t.size_, t.id_, 'PAID',
           t.storage_price_per_day_ * ceil(extract(epoch from (%(to)s - %(from)s)) / 86400),
           %(now)s + interval '15 minutes', %(now)s
    from tariff_ t cross join cell
    where t.size_ = %(size)s and tstzrange(t.valid_from_, t.valid_to_, '[)') @> %(now)s
    returning id_, size_, price_
), leg as (
    insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
    select %(leg)s, p.id_, p.size_, c.id_, 'STORAGE', %(from)s, %(to)s
    from placed p cross join cell c
    returning id_, cell_id_, from_, to_
), charge as (
    insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
    select %(payment)s, id_, 'CHARGE', price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
    from placed
)
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_, created_at_)
select code.id_, leg.id_, code.purpose_, code.hmac_, leg.from_, leg.to_, %(now)s
from leg cross join unnest(%(code_ids)s::bigint[], %(purposes)s::varchar[], %(hmacs)s::bytea[]) code(id_, purpose_, hmac_)
returning id_
```

**MySQL**

```sql
select c.id_
from lockermat_cell_ c
join lockermat_ l on l.id_ = c.lockermat_id_
where l.id_ = %(locker)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                    and r.from_ < %(to)s and r.to_ > %(from)s)
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
order by c.number_
limit 1
for update of c skip locked;
insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_, created_at_)
select %(order)s, %(number)s, %(customer)s, 'STORAGE', t.size_, t.id_, 'PAID',
       t.storage_price_per_day_ * ceil(timestampdiff(second, %(from)s, %(to)s) / 86400),
       %(now)s + interval 15 minute, %(now)s
from tariff_ t
where t.size_ = %(size)s and t.valid_from_ <= %(now)s and (t.valid_to_ is null or t.valid_to_ > %(now)s);
insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
values (%(leg)s, %(order)s, %(size)s, %(cell)s, 'STORAGE', %(from)s, %(to)s);
insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
select %(payment)s, o.id_, 'CHARGE', o.price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
from order_ o
where o.id_ = %(order)s;
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, valid_from_, valid_to_, created_at_)
values (%s, %s, %s, %s, %s, %s, %s)
```

**MongoDB**

```javascript
tariffs.findOne({size: :size, validFrom: {$lte: :now}, $or: [{validTo: null}, {validTo: {$gt: :now}}]});
lockermats.findOne({_id: :locker, status: 'ACTIVE'}, {cells: 1});
orders.aggregate([{$match: {$or: [{reservations: {$elemMatch: {cellId: {$in: <cells>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                  {reservations: {$elemMatch: {cellId: {$in: <cells>}, status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                  {$unwind: '$reservations'}, {$match: <the same two conditions on reservations>},
                  {$group: {_id: '$reservations.cellId'}}]);
lockermats.updateOne({_id: :locker, 'cells.id': <first free cell by number>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: <cell>, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}});
orders.insertOne({_id: :order, …, reservations: [{…, accessCodes: [<DROP_OFF>, <PICK_UP>]}], payments: [<CHARGE>]})
in one transaction per booking
```

**Neo4j**

```cypher
MATCH (:Lockermat {id: $locker, status: 'ACTIVE'})-[:HAS_CELL]->(c:Cell {size: $size, status: 'IN_SERVICE'})
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(r:Reservation)
    WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
       OR (r.status = 'OCCUPIED' AND r.to <= $now)
}
WITH c ORDER BY c.number LIMIT 1
SET c._guard = coalesce(c._guard, 0) + 1
WITH c
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(r:Reservation)
    WHERE r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from
}
MATCH (t:Tariff {size: $size})
WHERE t.validFrom <= $now AND (t.validTo IS NULL OR t.validTo > $now)
MATCH (u:Customer {id: $customer})
WITH c, t, u, t.storagePricePerDay * toInteger(ceil(duration.inSeconds($from, $to).seconds / 86400.0)) AS price
CREATE (u)-[:PLACED]->(o:Order {id: $order, number: $number, customerId: $customer, type: 'STORAGE', size: $size,
                                tariffId: t.id, status: 'PAID', price: price,
                                paymentDeadline: $now + duration({minutes: 15}), createdAt: $now})-[:PRICED_BY]->(t)
CREATE (o)-[:HAS_LEG]->(r:Reservation {id: $leg, size: $size, leg: 'STORAGE', from: $from, to: $to,
                                       status: 'BOOKED'})-[:IN_CELL]->(c)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {id: $payment, kind: 'CHARGE', amount: price, status: 'COMPLETED',
                                      provider: 'MOCK', providerRef: $provider_ref, createdAt: $now, completedAt: $now})
FOREACH (code IN $codes |
    CREATE (r)-[:HAS_CODE]->(:AccessCode {id: code.id, purpose: code.purpose, codeHmac: code.hmac,
                                          validFrom: $from, validTo: $to, status: 'ACTIVE', createdAt: $now}))
RETURN c.id
```

### C4 — tworzenie (INSERT)

Nadanie przesyłki ×1000: zamówienie, przesyłka, dwie nogi w różnych punktach, cztery kody i opłata w jednej transakcji, z wyborem taryfy i wolnych skrytek oraz zapisem połączenia między punktami

Flagi: BA, H1-I. Indeks IDX: IX1, IX2, IX3. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 20`, `batch: 1`, `days_after_t0: 40`, `window_hours: 4`.

**PostgreSQL**

```sql
with origin as (
    select c.id_
    from lockermat_cell_ c
    join lockermat_ l on l.id_ = c.lockermat_id_
    where l.id_ = %(origin)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                        and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
    order by c.number_
    limit 1
    for update of c skip locked
), destination as (
    select c.id_
    from lockermat_cell_ c
    join lockermat_ l on l.id_ = c.lockermat_id_
    where l.id_ = %(destination)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                        and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
      and not exists (select 1 from reservation_ r
                      where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
    order by c.number_
    limit 1
    for update of c skip locked
),
placed as (
    insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_,
                        created_at_)
    select %(order)s, %(number)s, %(customer)s, 'SHIPMENT', t.size_, t.id_, 'PAID', t.shipment_price_,
           %(now)s + interval '15 minutes', %(now)s
    from tariff_ t cross join origin cross join destination
    where t.size_ = %(size)s and tstzrange(t.valid_from_, t.valid_to_, '[)') @> %(now)s
    returning id_, size_, price_
), parcel as (
    insert into shipment_ (id_, order_id_, recipient_name_, recipient_phone_, declared_value_)
    select %(shipment)s, id_, %(recipient_name)s, %(recipient_phone)s, %(declared)s::numeric / 100
    from placed
), legs as (
    insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
    select leg.id_, p.id_, p.size_, leg.cell_id_, leg.leg_, %(from)s, %(to)s
    from placed p
    cross join (select %(origin_leg)s::bigint, id_, 'ORIGIN' from origin
                union all
                select %(destination_leg)s::bigint, id_, 'DESTINATION' from destination) leg(id_, cell_id_, leg_)
    returning id_, leg_, from_, to_
), charge as (
    insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
    select %(payment)s, id_, 'CHARGE', price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
    from placed
)
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, sent_to_phone_, valid_from_, valid_to_, created_at_)
select code.id_, legs.id_, code.purpose_, code.hmac_, code.phone_, legs.from_, legs.to_, %(now)s
from legs
join unnest(%(code_ids)s::bigint[], %(code_legs)s::varchar[], %(purposes)s::varchar[], %(hmacs)s::bytea[],
            %(phones)s::varchar[]) code(id_, leg_, purpose_, hmac_, phone_) on code.leg_ = legs.leg_
returning id_
```

**MySQL**

```sql
select c.id_
from lockermat_cell_ c
join lockermat_ l on l.id_ = c.lockermat_id_
where l.id_ = %(origin)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                    and r.from_ < %(to)s and r.to_ > %(from)s)
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
order by c.number_
limit 1
for update of c skip locked;
select c.id_
from lockermat_cell_ c
join lockermat_ l on l.id_ = c.lockermat_id_
where l.id_ = %(destination)s and l.status_ = 'ACTIVE' and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                    and r.from_ < %(to)s and r.to_ > %(from)s)
  and not exists (select 1 from reservation_ r
                  where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s)
order by c.number_
limit 1
for update of c skip locked;
insert into order_ (id_, number_, customer_id_, type_, size_, tariff_id_, status_, price_, payment_deadline_, created_at_)
select %(order)s, %(number)s, %(customer)s, 'SHIPMENT', t.size_, t.id_, 'PAID', t.shipment_price_,
       %(now)s + interval 15 minute, %(now)s
from tariff_ t
where t.size_ = %(size)s and t.valid_from_ <= %(now)s and (t.valid_to_ is null or t.valid_to_ > %(now)s);
insert into shipment_ (id_, order_id_, recipient_name_, recipient_phone_, declared_value_)
values (%(shipment)s, %(order)s, %(recipient_name)s, %(recipient_phone)s, %(declared)s / 100);
insert into reservation_ (id_, order_id_, size_, cell_id_, leg_, from_, to_)
values (%(origin_leg)s, %(order)s, %(size)s, %(origin_cell)s, 'ORIGIN', %(from)s, %(to)s),
       (%(destination_leg)s, %(order)s, %(size)s, %(destination_cell)s, 'DESTINATION', %(from)s, %(to)s);
insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, provider_ref_, created_at_, completed_at_)
select %(payment)s, o.id_, 'CHARGE', o.price_, 'COMPLETED', 'MOCK', %(provider_ref)s, %(now)s, %(now)s
from order_ o
where o.id_ = %(order)s;
insert into access_code_ (id_, reservation_id_, purpose_, code_hmac_, sent_to_phone_, valid_from_, valid_to_, created_at_)
values (%s, %s, %s, %s, %s, %s, %s, %s)
```

**MongoDB**

```javascript
tariffs.findOne({size: :size, validFrom: {$lte: :now}, $or: [{validTo: null}, {validTo: {$gt: :now}}]});
lockermats.find({_id: {$in: [:origin, :destination]}, status: 'ACTIVE'}, {cells: 1});
orders.aggregate([{$match: {$or: [{reservations: {$elemMatch: {cellId: {$in: <cells of both lockers>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                  {reservations: {$elemMatch: {cellId: {$in: <cells of both lockers>}, status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                  {$unwind: '$reservations'}, {$match: <the same two conditions on reservations>},
                  {$group: {_id: '$reservations.cellId'}}]);
lockermats.updateOne({_id: :origin, 'cells.id': <first free origin cell by number>}, {$inc: {'cells.$.guardSeq': 1}});
lockermats.updateOne({_id: :destination, 'cells.id': <first free destination cell by number>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: {$in: <both cells>}, status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}});
orders.insertOne({_id: :order, …, shipment: {…, originLockermatId, destinationLockermatId},
                  reservations: [{leg: 'ORIGIN', lockermatId, accessCodes: [<DROP_OFF>, <PICK_UP>]},
                                 {leg: 'DESTINATION', lockermatId, accessCodes: [<DROP_OFF>, <PICK_UP sent to the recipient>]}],
                  payments: [<CHARGE>]});
shipLinks.insertOne({_id: :order, orderId: :order, from: :origin, to: :destination, at: :now})
in one transaction per shipment
```

**Neo4j**

```cypher
MATCH (ol:Lockermat {id: $origin, status: 'ACTIVE'})-[:HAS_CELL]->(oc:Cell {size: $size, status: 'IN_SERVICE'})

    WHERE NOT EXISTS {
        MATCH (oc)<-[:IN_CELL]-(r:Reservation)
        WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
           OR (r.status = 'OCCUPIED' AND r.to <= $now)
    }

WITH ol, oc ORDER BY oc.number LIMIT 1
MATCH (dl:Lockermat {id: $destination, status: 'ACTIVE'})-[:HAS_CELL]->(dc:Cell {size: $size, status: 'IN_SERVICE'})

    WHERE NOT EXISTS {
        MATCH (dc)<-[:IN_CELL]-(r:Reservation)
        WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
           OR (r.status = 'OCCUPIED' AND r.to <= $now)
    }

WITH ol, oc, dl, dc ORDER BY dc.number LIMIT 1
SET oc._guard = coalesce(oc._guard, 0) + 1, dc._guard = coalesce(dc._guard, 0) + 1
WITH ol, oc, dl, dc
WHERE 
    NOT EXISTS {
        MATCH (oc)<-[:IN_CELL]-(r:Reservation)
        WHERE r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from
    }
 AND 
    NOT EXISTS {
        MATCH (dc)<-[:IN_CELL]-(r:Reservation)
        WHERE r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from
    }

MATCH (t:Tariff {size: $size})
WHERE t.validFrom <= $now AND (t.validTo IS NULL OR t.validTo > $now)
MATCH (u:Customer {id: $customer})
CREATE (u)-[:PLACED]->(o:Order:Shipment {id: $order, number: $number, customerId: $customer, type: 'SHIPMENT',
                                         size: $size, tariffId: t.id, status: 'PAID', price: t.shipmentPrice,
                                         paymentDeadline: $now + duration({minutes: 15}), createdAt: $now,
                                         shipmentId: $shipment, recipientName: $recipient_name,
                                         recipientPhone: $recipient_phone, declaredValue: $declared})-[:PRICED_BY]->(t)
CREATE (o)-[:HAS_LEG]->(ro:Reservation {id: $origin_leg, size: $size, leg: 'ORIGIN', from: $from, to: $to,
                                        status: 'BOOKED'})-[:IN_CELL]->(oc)
CREATE (o)-[:HAS_LEG]->(rd:Reservation {id: $destination_leg, size: $size, leg: 'DESTINATION', from: $from, to: $to,
                                        status: 'BOOKED'})-[:IN_CELL]->(dc)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {id: $payment, kind: 'CHARGE', amount: t.shipmentPrice, status: 'COMPLETED',
                                      provider: 'MOCK', providerRef: $provider_ref, createdAt: $now,
                                      completedAt: $now})
CREATE (ol)-[:SHIPS_TO {orderId: $order, at: $now}]->(dl)

FOREACH (code IN [item IN $codes WHERE item.leg = 'ORIGIN'] |
    CREATE (ro)-[:HAS_CODE]->(:AccessCode {id: code.id, purpose: code.purpose, codeHmac: code.hmac,
                                                  sentToPhone: code.phone, validFrom: $from, validTo: $to,
                                                  status: 'ACTIVE', createdAt: $now}))


FOREACH (code IN [item IN $codes WHERE item.leg = 'DESTINATION'] |
    CREATE (rd)-[:HAS_CODE]->(:AccessCode {id: code.id, purpose: code.purpose, codeHmac: code.hmac,
                                                  sentToPhone: code.phone, validFrom: $from, validTo: $to,
                                                  status: 'ACTIVE', createdAt: $now}))

RETURN oc.id, dc.id
```

### C5 — tworzenie (INSERT)

Synchronizacja 10 000 klientów według identyfikatora Keycloak w transakcjach po 100: połowa istnieje i dostaje nowy telefon i regulamin, połowa zostaje wstawiona

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 10000`, `ops_xs: 100`, `batch: 100`.

**PostgreSQL**

```sql
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
select * from unnest(%(id)s::bigint[], %(keycloak)s::uuid[], %(phone)s::varchar[], %(terms)s::varchar[],
                     %(at)s::timestamptz[], %(at)s::timestamptz[])
on conflict (keycloak_id_) do update
set phone_ = excluded.phone_, terms_version_ = excluded.terms_version_, terms_accepted_at_ = excluded.terms_accepted_at_
```

**MySQL**

```sql
insert into customer_ (id_, keycloak_id_, phone_, terms_version_, terms_accepted_at_, created_at_)
values (%s, %s, %s, %s, %s, %s) as new
on duplicate key update phone_ = new.phone_, terms_version_ = new.terms_version_,
                        terms_accepted_at_ = new.terms_accepted_at_
```

**MongoDB**

```javascript
customers.bulkWrite([{updateOne: {filter: {keycloakId}, update: {$set: {phone, termsVersion, termsAcceptedAt}, $setOnInsert: {_id, createdAt}}, upsert: true}}, …]) in one transaction per batch
```

**Neo4j**

```cypher
UNWIND $rows AS row
MERGE (c:Customer {keycloakId: row.keycloak})
ON CREATE SET c.id = row.id, c.createdAt = row.at
SET c.phone = row.phone, c.termsVersion = row.terms, c.termsAcceptedAt = row.at
```

### C6 — tworzenie (INSERT)

Naliczenie opłat za przetrzymanie bagażu dla wszystkich zajętych skrytek po terminie: INSERT z zapytania z ceną z taryfy zamówienia za każdą rozpoczętą dobę, partiami po 5000 zamówień

Flagi: BA, H1-I. Indeks IDX: IX3. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`.

**PostgreSQL**

```sql
select order_id_ from reservation_ where status_ = 'OCCUPIED' and to_ < %(now)s order by order_id_;

insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, created_at_)
select 10000000000000 + o.id_, o.id_, 'OVERSTAY',
       t.overstay_price_per_day_ * ceil(extract(epoch from (%(now)s - r.to_)) / 86400), 'PENDING', 'MOCK', %(now)s
from reservation_ r
join order_ o on o.id_ = r.order_id_
join tariff_ t on t.id_ = o.tariff_id_
where r.order_id_ = any(%(orders)s) and r.status_ = 'OCCUPIED' and r.to_ < %(now)s
```

**MySQL**

```sql
select order_id_ from reservation_ where (case when status_ = 'OCCUPIED' then to_ end) < %(now)s order by order_id_;

insert into payment_ (id_, order_id_, kind_, amount_, status_, provider_, created_at_)
select 10000000000000 + o.id_, o.id_, 'OVERSTAY',
       t.overstay_price_per_day_ * ((timestampdiff(microsecond, r.to_, %s) + 86399999999) div 86400000000),
       'PENDING', 'MOCK', %s
from reservation_ r
join order_ o on o.id_ = r.order_id_
join tariff_ t on t.id_ = o.tariff_id_
where r.order_id_ in ({marks}) and (case when r.status_ = 'OCCUPIED' then r.to_ end) < %s
```

**MongoDB**

```javascript
tariffs.find({}, {overstayPricePerDay: 1});
orders.find({reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lt: :now}}}}, {_id: 1}).sort({_id: 1});
orders.updateMany({_id: {$in: <batch of 5000>}, reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lt: :now}}}},
                  [{$set: {payments: {$concatArrays: [{$ifNull: ['$payments', []]}, [{$let: {
                      vars: {leg: {$first: {$filter: {input: '$reservations',
                                                      cond: {$and: [{$eq: ['$$this.status', 'OCCUPIED']},
                                                                    {$lt: ['$$this.to', :now]}]}}}}},
                      in: {id: {$add: [10000000000000, '$_id']}, kind: 'OVERSTAY', status: 'PENDING', provider: 'MOCK',
                           createdAt: :now,
                           amount: {$toLong: {$multiply: [{$switch: {branches: [{case: {$eq: ['$tariffId', <tariff id>]},
                                                                                   then: <overstay rate>}, …]}},
                                                          {$ceil: {$divide: [{$subtract: [:now, '$$leg.to']}, 86400000]}}]}}}
                  }}]]}}}])
in one transaction per batch
```

**Neo4j**

```cypher
MATCH (o:Order)-[:HAS_LEG]->(r:Reservation)
WHERE r.status = 'OCCUPIED' AND r.to < $now
RETURN o.id ORDER BY o.id;

UNWIND $orders AS id
MATCH (o:Order {id: id})-[:HAS_LEG]->(r:Reservation)
WHERE r.status = 'OCCUPIED' AND r.to < $now
MATCH (o)-[:PRICED_BY]->(t:Tariff)
CREATE (o)-[:HAS_PAYMENT]->(:Payment {id: 10000000000000 + o.id, kind: 'OVERSTAY',
    amount: t.overstayPricePerDay * toInteger(ceil(($now.epochMillis - r.to.epochMillis) / 86400000.0)),
    status: 'PENDING', provider: 'MOCK', createdAt: $now})
```

### R1 — odczyt (SELECT)

Szczegóły zamówienia według id: zamówienie, jego rezerwacje z punktem (id, nazwa, adres), kody dostępu i płatności

Flagi: CX. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 20`.

**PostgreSQL**

```sql
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       r.id_, r.leg_, r.status_, r.from_, r.to_, l.id_, l.name_, l.address_,
       a.id_, a.purpose_, a.status_, a.valid_from_, a.valid_to_,
       null, null, null, null, null
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
left join access_code_ a on a.reservation_id_ = r.id_
where o.id_ = %(order)s
union all
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       null, null, null, null, null, null, null, null,
       null, null, null, null, null,
       p.id_, p.kind_, p.status_, p.amount_, p.created_at_
from order_ o
join payment_ p on p.order_id_ = o.id_
where o.id_ = %(order)s
```

**MySQL**

```sql
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       r.id_, r.leg_, r.status_, r.from_, r.to_, l.id_, l.name_, l.address_,
       a.id_, a.purpose_, a.status_, a.valid_from_, a.valid_to_,
       null, null, null, null, null
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
left join access_code_ a on a.reservation_id_ = r.id_
where o.id_ = %(order)s
union all
select o.id_, o.number_, o.type_, o.status_, o.price_, o.created_at_,
       null, null, null, null, null, null, null, null,
       null, null, null, null, null,
       p.id_, p.kind_, p.status_, p.amount_, p.created_at_
from order_ o
join payment_ p on p.order_id_ = o.id_
where o.id_ = %(order)s
```

**MongoDB**

```javascript
orders.findOne({_id: :order}, {"number": 1, "type": 1, "status": 1, "price": 1, "createdAt": 1, "reservations.id": 1, "reservations.leg": 1, "reservations.status": 1, "reservations.from": 1, "reservations.to": 1, "reservations.lockermatId": 1, "reservations.accessCodes.id": 1, "reservations.accessCodes.purpose": 1, "reservations.accessCodes.status": 1, "reservations.accessCodes.validFrom": 1, "reservations.accessCodes.validTo": 1, "payments.id": 1, "payments.kind": 1, "payments.status": 1, "payments.amount": 1, "payments.createdAt": 1}); lockermats.find({_id: {$in: <reservations.lockermatId>}}, {"name": 1, "address": 1})
```

**Neo4j**

```cypher
MATCH (o:Order {id: $order})
RETURN o {.id, .number, .type, .status, .price, .createdAt,
          reservations: [(o)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat) |
                         r {.id, .leg, .status, .from, .to, lockermat: l {.id, .name, .address},
                            accessCodes: [(r)-[:HAS_CODE]->(a:AccessCode) |
                                          a {.id, .purpose, .status, .validFrom, .validTo}]}],
          payments: [(o)-[:HAS_PAYMENT]->(p:Payment) | p {.id, .kind, .status, .amount, .createdAt}]}
```

### R2 — odczyt (SELECT)

„Moje rezerwacje”: strona 3 (20 wierszy) zamówień klienta od najnowszego

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 20`, `page: 3`, `page_size: 20`.

**PostgreSQL**

```sql
select id_, number_, type_, status_, price_, created_at_
from order_
where customer_id_ = %(customer)s
order by created_at_ desc, id_ desc
limit %(limit)s offset %(offset)s
```

**MySQL**

```sql
select id_, number_, type_, status_, price_, created_at_
from order_
where customer_id_ = %(customer)s
order by created_at_ desc, id_ desc
limit %(limit)s offset %(offset)s
```

**MongoDB**

```javascript
orders.aggregate([{$match: {customerId: :customer}}, {$sort: {createdAt: -1, _id: -1}}, {$skip: :offset}, {$limit: :limit}, {$project: {"number": 1, "type": 1, "status": 1, "price": 1, "createdAt": 1}}])
```

**Neo4j**

```cypher
MATCH (:Customer {id: $customer})-[:PLACED]->(o:Order)
RETURN o.id, o.number, o.type, o.status, o.price, o.createdAt
ORDER BY o.createdAt DESC, o.id DESC
SKIP $offset LIMIT $limit
```

### R3 — odczyt (SELECT)

10 najbliższych aktywnych punktów w promieniu 5 km z wolną skrytką danego rozmiaru w wybranym oknie czasu, ×200 lokalizacji

Flagi: CX. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 200`, `ops_xs: 20`, `radius_m: 5000`, `limit: 10`, `days_after_t0: 7`, `window_hours: 4`, `size: M`.

**PostgreSQL**

```sql
select l.id_, st_distance(l.location_::geography, st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography)
from lockermat_ l
where l.status_ = 'ACTIVE'
  and st_dwithin(l.location_::geography, st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography, %(radius)s)
  and exists (select 1 from lockermat_cell_ c
              where c.lockermat_id_ = l.id_ and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                                  and tstzrange(r.from_, r.to_, '[)') && tstzrange(%(from)s, %(to)s, '[)'))
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s))
order by l.location_::geography <-> st_setsrid(st_makepoint(%(lng)s, %(lat)s), 4326)::geography
limit %(limit)s
```

**MySQL**

```sql
select l.id_, st_distance_sphere(l.location_, st_geomfromtext(%(point)s, 4326, 'axis-order=long-lat')) as distance_
from lockermat_ l
where mbrcontains(st_geomfromtext(%(box)s, 4326, 'axis-order=long-lat'), l.location_)
  and l.status_ = 'ACTIVE'
  and st_distance_sphere(l.location_, st_geomfromtext(%(point)s, 4326, 'axis-order=long-lat')) <= %(radius)s
  and exists (select 1 from lockermat_cell_ c
              where c.lockermat_id_ = l.id_ and c.size_ = %(size)s and c.status_ = 'IN_SERVICE'
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ in ('BOOKED', 'OCCUPIED')
                                  and r.from_ < %(to)s and r.to_ > %(from)s)
                and not exists (select 1 from reservation_ r
                                where r.cell_id_ = c.id_ and r.status_ = 'OCCUPIED' and r.to_ <= %(now)s))
order by distance_, l.id_
limit %(limit)s
```

**MongoDB**

```javascript
lockermats.aggregate([
  {$geoNear: {near: {type: 'Point', coordinates: [:lng, :lat]}, key: 'location', distanceField: 'distance',
              maxDistance: :radius, spherical: true,
              query: {status: 'ACTIVE', cells: {$elemMatch: {size: :size, status: 'IN_SERVICE'}}}}},
  {$project: {distance: 1, cells: <ids of cells with size :size and status IN_SERVICE>}},
  {$lookup: {from: 'orders', localField: 'cells', foreignField: 'reservations.cellId', let: {cells: '$cells'},
             pipeline: [{$match: {$or: [{reservations: {$elemMatch: {status: {$in: ['BOOKED', 'OCCUPIED']}, from: {$lt: :to}, to: {$gt: :from}}}},
                                        {reservations: {$elemMatch: {status: 'OCCUPIED', to: {$lte: :now}}}}]}},
                        {$unwind: '$reservations'},
                        {$match: {$expr: {$in: ['$reservations.cellId', '$$cells']}, $or: <the same two conditions on reservations>}},
                        {$project: {_id: 0, cellId: '$reservations.cellId'}}],
             as: 'busy'}},
  {$match: {$expr: {$gt: [{$size: {$setDifference: ['$cells', '$busy.cellId']}}, 0]}}},
  {$limit: :limit},
  {$project: {distance: 1}}
])
```

**Neo4j**

```cypher
MATCH (l:Lockermat)
WHERE point.distance(l.location, point({longitude: $lng, latitude: $lat})) <= $radius
  AND l.status = 'ACTIVE'
  AND EXISTS {
      MATCH (l)-[:HAS_CELL]->(c:Cell {size: $size, status: 'IN_SERVICE'})
      WHERE NOT EXISTS {
          MATCH (c)<-[:IN_CELL]-(r:Reservation)
          WHERE (r.status IN ['BOOKED', 'OCCUPIED'] AND r.from < $to AND r.to > $from)
             OR (r.status = 'OCCUPIED' AND r.to <= $now)
      }
  }
WITH l, point.distance(l.location, point({longitude: $lng, latitude: $lat})) AS distance
ORDER BY distance, l.id
LIMIT $limit
RETURN l.id, distance
```

### R4 — odczyt (SELECT)

„Do odbioru”: przesyłki na numer telefonu odbiorcy, których skrytka docelowa jest zajęta, z punktem i numerem skrytki, ×100 numerów

Flagi: BA, CX, H1-S. Indeks IDX: IX1. Ustawienia z `ops.yaml`: `ops: 100`, `ops_xs: 10`.

**PostgreSQL**

```sql
select s.order_id_, r.id_, r.from_, r.to_, l.id_, l.name_, l.address_, c.number_
from shipment_ s
join reservation_ r on r.order_id_ = s.order_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
where s.recipient_phone_ = %(phone)s and r.leg_ = 'DESTINATION' and r.status_ = 'OCCUPIED'
```

**MySQL**

```sql
select s.order_id_, r.id_, r.from_, r.to_, l.id_, l.name_, l.address_, c.number_
from shipment_ s
join reservation_ r on r.order_id_ = s.order_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
join lockermat_ l on l.id_ = c.lockermat_id_
where s.recipient_phone_ = %(phone)s and r.leg_ = 'DESTINATION' and r.status_ = 'OCCUPIED'
```

**MongoDB**

```javascript
orders.aggregate([
  {$match: {'shipment.recipientPhone': :phone, reservations: {$elemMatch: {leg: 'DESTINATION', status: 'OCCUPIED'}}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': 'DESTINATION', 'reservations.status': 'OCCUPIED'}},
  {$lookup: {from: 'lockermats', localField: 'reservations.lockermatId', foreignField: '_id',
             let: {cell: '$reservations.cellId'},
             pipeline: [{$project: {name: 1, address: 1, cell: {$first: {$filter: {input: '$cells', cond: {$eq: ['$$this.id', '$$cell']}}}}}}],
             as: 'locker'}},
  {$unwind: '$locker'},
  {$project: {reservation: '$reservations.id', from: '$reservations.from', to: '$reservations.to',
              lockermat: '$locker._id', name: '$locker.name', address: '$locker.address', number: '$locker.cell.number'}}
])
```

**Neo4j**

```cypher
MATCH (s:Shipment {recipientPhone: $phone})-[:HAS_LEG]->(r:Reservation {leg: 'DESTINATION', status: 'OCCUPIED'}),
      (r)-[:IN_CELL]->(c:Cell)<-[:HAS_CELL]-(l:Lockermat)
RETURN s.id, r.id, r.from, r.to, l.id, l.name, l.address, c.number
```

### R5 — odczyt (SELECT)

Ranking 20 punktów według liczby zamówień utworzonych w ostatnich 30 dniach i teraz zakończonych (punkt skrytki przechowania albo nadania; filtr na dacie utworzenia, nie zakończenia)

Flagi: BA, CX, H1-S. Indeks IDX: IX2. Ustawienia z `ops.yaml`: `ops: 1`, `ops_xs: 1`, `days: 30`, `limit: 20`.

**PostgreSQL**

```sql
select c.lockermat_id_, count(*) as orders_
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.status_ = 'COMPLETED' and o.created_at_ >= %(since)s and o.created_at_ < %(now)s
  and r.leg_ in ('STORAGE', 'ORIGIN')
group by c.lockermat_id_
order by orders_ desc, c.lockermat_id_
limit %(limit)s
```

**MySQL**

```sql
select c.lockermat_id_, count(*) as orders_
from order_ o
join reservation_ r on r.order_id_ = o.id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.status_ = 'COMPLETED' and o.created_at_ >= %(since)s and o.created_at_ < %(now)s
  and r.leg_ in ('STORAGE', 'ORIGIN')
group by c.lockermat_id_
order by orders_ desc, c.lockermat_id_
limit %(limit)s
```

**MongoDB**

```javascript
orders.aggregate([
  {$match: {status: 'COMPLETED', createdAt: {$gte: :since, $lt: :now}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': {$in: ['STORAGE', 'ORIGIN']}}},
  {$group: {_id: '$reservations.lockermatId', orders: {$sum: 1}}},
  {$sort: {orders: -1, _id: 1}},
  {$limit: :limit}
])
```

**Neo4j**

```cypher
MATCH (o:Order)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
WHERE o.status = 'COMPLETED' AND o.createdAt >= $since AND o.createdAt < $now AND r.leg IN ['STORAGE', 'ORIGIN']
RETURN l.id AS lockermat, count(*) AS orders
ORDER BY orders DESC, lockermat
LIMIT $limit
```

### R6 — odczyt (SELECT)

Przychód netto każdego punktu w jednym miesiącu (zrealizowane opłaty minus zwroty i rekompensaty, w groszach), ×12 miesięcy; płatność należy do punktu skrytki przechowania albo, dla przesyłki, skrytki nadania

Flagi: BA, CX, H1-S. Indeks IDX: IX3. Ustawienia z `ops.yaml`: `ops: 12`, `ops_xs: 3`.

**PostgreSQL**

```sql
select c.lockermat_id_, sum(case when p.kind_ in ('REFUND', 'COMPENSATION') then -p.amount_ else p.amount_ end) as net_
from payment_ p
join reservation_ r on r.order_id_ = p.order_id_ and r.leg_ in ('STORAGE', 'ORIGIN')
join lockermat_cell_ c on c.id_ = r.cell_id_
where p.status_ = 'COMPLETED' and p.created_at_ >= %(since)s and p.created_at_ < %(until)s
group by c.lockermat_id_
```

**MySQL**

```sql
select c.lockermat_id_, sum(case when p.kind_ in ('REFUND', 'COMPENSATION') then -p.amount_ else p.amount_ end) as net_
from payment_ p
join reservation_ r on r.order_id_ = p.order_id_ and r.leg_ in ('STORAGE', 'ORIGIN')
join lockermat_cell_ c on c.id_ = r.cell_id_
where p.status_ = 'COMPLETED' and p.created_at_ >= %(since)s and p.created_at_ < %(until)s
group by c.lockermat_id_
```

**MongoDB**

```javascript
orders.aggregate([
  {$match: {payments: {$elemMatch: {status: 'COMPLETED', createdAt: {$gte: :since, $lt: :until}}},
            'payments.createdAt': {$exists: true}}},
  {$unwind: '$payments'},
  {$match: {'payments.status': 'COMPLETED', 'payments.createdAt': {$gte: :since, $lt: :until}}},
  {$unwind: '$reservations'},
  {$match: {'reservations.leg': {$in: ['STORAGE', 'ORIGIN']}}},
  {$group: {_id: '$reservations.lockermatId',
            net: {$sum: {$cond: [{$in: ['$payments.kind', ['REFUND', 'COMPENSATION']]},
                                 {$subtract: [0, '$payments.amount']}, '$payments.amount']}}}}
])
```

**Neo4j**

```cypher
MATCH (p:Payment)
WHERE p.createdAt >= $since AND p.createdAt < $until AND p.status = 'COMPLETED'
MATCH (p)<-[:HAS_PAYMENT]-(:Order)-[:HAS_LEG]->(r:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
WHERE r.leg IN ['STORAGE', 'ORIGIN']
RETURN l.id AS lockermat, sum(CASE WHEN p.kind IN ['REFUND', 'COMPENSATION'] THEN -p.amount ELSE p.amount END) AS net
```

### R7 — odczyt (SELECT)

Aktywność drzwi każdego punktu w oknie 24 h: liczba otwarć kodem i liczba nieudanych (DOOR_FAILED), z której wynika ich udział, bez otwarć serwisowych; ×30 dni

Flagi: BA, CX, H1-S. Indeks IDX: IX4. Ustawienia z `ops.yaml`: `ops: 30`, `ops_xs: 5`.

**PostgreSQL**

```sql
select c.lockermat_id_, count(*) as openings_, count(*) filter (where o.result_ = 'DOOR_FAILED') as door_failed_
from cell_opening_ o
join access_code_ a on a.id_ = o.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.requested_at_ >= %(since)s and o.requested_at_ < %(until)s
group by c.lockermat_id_
```

**MySQL**

```sql
select c.lockermat_id_, count(*) as openings_, sum(o.result_ = 'DOOR_FAILED') as door_failed_
from cell_opening_ o
join access_code_ a on a.id_ = o.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join lockermat_cell_ c on c.id_ = r.cell_id_
where o.requested_at_ >= %(since)s and o.requested_at_ < %(until)s
group by c.lockermat_id_
```

**MongoDB**

```javascript
orders.aggregate([
  {$match: {'reservations.accessCodes.openings': {$elemMatch: {requestedAt: {$gte: :since, $lt: :until}}},
            'reservations.accessCodes.openings.requestedAt': {$exists: true}}},
  {$unwind: '$reservations'},
  {$unwind: '$reservations.accessCodes'},
  {$unwind: '$reservations.accessCodes.openings'},
  {$match: {'reservations.accessCodes.openings.requestedAt': {$gte: :since, $lt: :until}}},
  {$group: {_id: '$reservations.lockermatId', openings: {$sum: 1},
            doorFailed: {$sum: {$cond: [{$eq: ['$reservations.accessCodes.openings.result', 'DOOR_FAILED']}, 1, 0]}}}}
])
```

**Neo4j**

```cypher
MATCH (o:CellOpening)
WHERE o.requestedAt >= $since AND o.requestedAt < $until
MATCH (o)-[:OPENED_WITH]->(:AccessCode)<-[:HAS_CODE]-(:Reservation)-[:IN_CELL]->(:Cell)<-[:HAS_CELL]-(l:Lockermat)
RETURN l.id AS lockermat, count(*) AS openings, sum(CASE o.result WHEN 'DOOR_FAILED' THEN 1 ELSE 0 END) AS doorFailed
```

### R8 — odczyt (SELECT)

Punkty osiągalne z danego punktu po połączeniach przesyłek z ostatnich 90 dni z najmniejszą liczbą przeskoków ≤ 3, ×50 punktów startowych

Flagi: CX. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 50`, `ops_xs: 3`, `days: 90`, `max_hops: 3`.

**PostgreSQL**

```sql
with recursive link (from_, to_) as (
    select oc.lockermat_id_, dc.lockermat_id_
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    join reservation_ dl on dl.order_id_ = s.order_id_ and dl.leg_ = 'DESTINATION'
    join lockermat_cell_ dc on dc.id_ = dl.cell_id_
    where o.created_at_ >= %(since)s
), reach (lockermat_id_, hops_) as (
    select %(lockermat)s::bigint, 0
    union
    select k.to_, r.hops_ + 1
    from reach r
    join link k on k.from_ = r.lockermat_id_
    where r.hops_ < %(max_hops)s
)
select lockermat_id_, min(hops_)
from reach
where lockermat_id_ <> %(lockermat)s
group by lockermat_id_
```

**MySQL**

```sql
with recursive link (from_, to_) as (
    select oc.lockermat_id_, dc.lockermat_id_
    from shipment_ s
    join order_ o on o.id_ = s.order_id_
    join reservation_ ol on ol.order_id_ = s.order_id_ and ol.leg_ = 'ORIGIN'
    join lockermat_cell_ oc on oc.id_ = ol.cell_id_
    join reservation_ dl on dl.order_id_ = s.order_id_ and dl.leg_ = 'DESTINATION'
    join lockermat_cell_ dc on dc.id_ = dl.cell_id_
    where o.created_at_ >= %(since)s
), reach (lockermat_id_, hops_) as (
    select cast(%(lockermat)s as signed), 0
    union distinct
    select k.to_, r.hops_ + 1
    from reach r
    join link k on k.from_ = r.lockermat_id_
    where r.hops_ < %(max_hops)s
)
select lockermat_id_, min(hops_)
from reach
where lockermat_id_ <> %(lockermat)s
group by lockermat_id_
```

**MongoDB**

```javascript
lockermats.aggregate([
  {$match: {_id: :lockermat}},
  {$project: {_id: 1}},
  {$graphLookup: {from: 'shipLinks', startWith: '$_id', connectFromField: 'to', connectToField: 'from',
                  as: 'links', maxDepth: :max_hops - 1, depthField: 'depth', restrictSearchWithMatch: {at: {$gte: :since}}}},
  {$unwind: '$links'},
  {$group: {_id: '$links.to', hops: {$min: {$add: ['$links.depth', 1]}}}},
  {$match: {_id: {$ne: :lockermat}}}
])
```

**Neo4j**

```cypher
MATCH p = SHORTEST 1 (a:Lockermat {id: $lockermat})-[r:SHIPS_TO WHERE r.at >= $since]->{1,3}(b:Lockermat)
WHERE b <> a
RETURN b.id, length(p)
```

### U1 — aktualizacja (UPDATE)

Zamknięcie 5000 opłaconych zamówień (PAID → COMPLETED) według id, w transakcjach po 1000 zamówień

Flagi: BA, H1-U. Indeks IDX: IX2. Ustawienia z `ops.yaml`: `ops: 5000`, `ops_xs: 100`, `batch: 1000`.

**PostgreSQL**

```sql
update order_ set status_ = 'COMPLETED', closed_at_ = %(now)s
where id_ = any(%(orders)s) and status_ = 'PAID'
```

**MySQL**

```sql
update order_ set status_ = 'COMPLETED', closed_at_ = %s
where id_ in ({marks}) and status_ = 'PAID'
```

**MongoDB**

```javascript
orders.updateMany({_id: {$in: :orders}, status: 'PAID'}, {$set: {status: 'COMPLETED', closedAt: :now}})
in one transaction per batch
```

**Neo4j**

```cypher
UNWIND $orders AS id
MATCH (o:Order {id: id})
WHERE o.status = 'PAID'
SET o.status = 'COMPLETED', o.closedAt = $now
```

### U2 — aktualizacja (UPDATE)

Użycie kodu nadania ×1000: otwarcie skrytki → OPENED, kod → USED, noga → OCCUPIED w jednej transakcji, z kontrolą faktycznego zajęcia skrytki

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 10`, `batch: 1`.

**PostgreSQL**

```sql
select o.id_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join order_ o on o.id_ = r.order_id_
where x.id_ = %(opening)s
for update of o;

with opening as (
    update cell_opening_ set result_ = 'OPENED'
    where id_ = %(opening)s and result_ = 'PENDING'
    returning access_code_id_, requested_at_
), code as (
    update access_code_ a set status_ = 'USED', used_at_ = o.requested_at_
    from opening o
    where a.id_ = o.access_code_id_ and a.status_ = 'ACTIVE' and a.purpose_ = 'DROP_OFF'
    returning a.reservation_id_, o.requested_at_
)
update reservation_ r
set status_ = 'OCCUPIED', deposited_at_ = c.requested_at_
from code c
where r.id_ = c.reservation_id_ and r.status_ = 'BOOKED'
returning r.id_
```

**MySQL**

```sql
select a.id_, r.id_, x.requested_at_
from cell_opening_ x
join access_code_ a on a.id_ = x.access_code_id_
join reservation_ r on r.id_ = a.reservation_id_
join order_ o on o.id_ = r.order_id_
where x.id_ = %(opening)s
for update of o;
update cell_opening_ set result_ = 'OPENED' where id_ = %(opening)s and result_ = 'PENDING';
update access_code_ set status_ = 'USED', used_at_ = %(at)s
where id_ = %(code)s and status_ = 'ACTIVE' and purpose_ = 'DROP_OFF';
update reservation_ set status_ = 'OCCUPIED', deposited_at_ = %(at)s
where id_ = %(leg)s and status_ = 'BOOKED'
```

**MongoDB**

```javascript
orders.findOne({'reservations.accessCodes.openings.id': :opening}, {<leg, code and opening ids, cell, locker, requestedAt>});
lockermats.updateOne({_id: <leg lockermatId>, 'cells.id': <leg cellId>}, {$inc: {'cells.$.guardSeq': 1}});
orders.findOne({reservations: {$elemMatch: {cellId: <leg cellId>, depositedAt: {$exists: true},
                                           $or: [{collectedAt: {$exists: false}}, {collectedAt: {$gt: <requestedAt>}}]}}});
orders.updateOne({_id: <order>, reservations: {$elemMatch: {id: <leg>, status: 'BOOKED', accessCodes: {$elemMatch: {
                      id: <code>, status: 'ACTIVE', purpose: 'DROP_OFF', openings: {$elemMatch: {id: :opening, result: 'PENDING'}}}}}}},
                 {$set: {'reservations.$[leg].status': 'OCCUPIED', 'reservations.$[leg].depositedAt': <requestedAt>,
                         'reservations.$[leg].accessCodes.$[code].status': 'USED',
                         'reservations.$[leg].accessCodes.$[code].usedAt': <requestedAt>,
                         'reservations.$[leg].accessCodes.$[code].openings.$[opening].result': 'OPENED'}},
                 {arrayFilters: [{'leg.id': <leg>}, {'code.id': <code>}, {'opening.id': :opening}]})
in one transaction per redemption
```

**Neo4j**

```cypher
MATCH (x:CellOpening {id: $opening})-[:OPENED_WITH]->(a:AccessCode)<-[:HAS_CODE]-(r:Reservation)-[:IN_CELL]->(c:Cell)
WHERE x.result = 'PENDING' AND a.status = 'ACTIVE' AND a.purpose = 'DROP_OFF' AND r.status = 'BOOKED'
SET c._guard = coalesce(c._guard, 0) + 1
WITH x, a, r, c
WHERE NOT EXISTS {
    MATCH (c)<-[:IN_CELL]-(y:Reservation)
    WHERE y.depositedAt IS NOT NULL AND (y.collectedAt IS NULL OR y.collectedAt > x.requestedAt)
}
SET x.result = 'OPENED', a.status = 'USED', a.usedAt = x.requestedAt,
    r.status = 'OCCUPIED', r.depositedAt = x.requestedAt
RETURN r.id
```

### U3 — aktualizacja (UPDATE)

Wygaszenie nieopłaconych zamówień po terminie płatności (→ EXPIRED) i anulowanie ich nóg (→ CANCELLED), partiami po 5000 zamówień

Flagi: BA. Indeks IDX: IX2. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`.

**PostgreSQL**

```sql
select id_ from order_ where status_ = 'AWAITING_PAYMENT' and payment_deadline_ < %(now)s order by id_;

with expired as (
    update order_ set status_ = 'EXPIRED', closed_at_ = %(now)s
    where id_ = any(%(orders)s) and status_ = 'AWAITING_PAYMENT' and payment_deadline_ < %(now)s
    returning id_
)
update reservation_ r set status_ = 'CANCELLED'
from expired e
where r.order_id_ = e.id_ and r.status_ = 'BOOKED'
```

**MySQL**

```sql
select id_ from order_ where (case when status_ = 'AWAITING_PAYMENT' then payment_deadline_ end) < %(now)s order by id_;

update order_ o
left join reservation_ r on r.order_id_ = o.id_ and r.status_ = 'BOOKED'
set o.status_ = 'EXPIRED', o.closed_at_ = %s, r.status_ = 'CANCELLED'
where o.id_ in ({marks}) and (case when o.status_ = 'AWAITING_PAYMENT' then o.payment_deadline_ end) < %s
```

**MongoDB**

```javascript
orders.find({status: 'AWAITING_PAYMENT', paymentDeadline: {$lt: :now}}, {_id: 1}).sort({_id: 1});
orders.updateMany({_id: {$in: <batch of 5000>}, status: 'AWAITING_PAYMENT', paymentDeadline: {$lt: :now}},
                  {$set: {status: 'EXPIRED', closedAt: :now, 'reservations.$[leg].status': 'CANCELLED'}},
                  {arrayFilters: [{'leg.status': 'BOOKED'}]})
in one transaction per batch
```

**Neo4j**

```cypher
MATCH (o:Order)
WHERE o.status = 'AWAITING_PAYMENT' AND o.paymentDeadline < $now
RETURN o.id ORDER BY o.id;

UNWIND $orders AS id
MATCH (o:Order {id: id})
WHERE o.status = 'AWAITING_PAYMENT' AND o.paymentDeadline < $now
SET o.status = 'EXPIRED', o.closedAt = $now
WITH o
MATCH (o)-[:HAS_LEG]->(r:Reservation {status: 'BOOKED'})
SET r.status = 'CANCELLED'
```

### U4 — aktualizacja (UPDATE)

Wycofanie 20 automatów z eksploatacji w jednej transakcji: ich skrytki → OUT_OF_SERVICE, przyszłe zarezerwowane nogi → CANCELLED, aktywne kody tych nóg → REVOKED

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 20`, `ops_xs: 2`, `batch: 5000`.

**PostgreSQL**

```sql
with cells as (
    update lockermat_cell_ set status_ = 'OUT_OF_SERVICE'
    where lockermat_id_ = any(%(lockers)s) and status_ = 'IN_SERVICE'
), legs as (
    update reservation_ r set status_ = 'CANCELLED'
    from lockermat_cell_ c
    where c.id_ = r.cell_id_ and c.lockermat_id_ = any(%(lockers)s) and r.status_ = 'BOOKED' and r.from_ > %(now)s
    returning r.id_
)
update access_code_ a set status_ = 'REVOKED'
from legs l
where a.reservation_id_ = l.id_ and a.status_ = 'ACTIVE'
```

**MySQL**

```sql
update lockermat_cell_ c
left join reservation_ r on r.cell_id_ = c.id_ and r.status_ = 'BOOKED' and r.from_ > %s
left join access_code_ a on a.reservation_id_ = r.id_ and a.status_ = 'ACTIVE'
set c.status_ = 'OUT_OF_SERVICE', r.status_ = 'CANCELLED', a.status_ = 'REVOKED'
where c.lockermat_id_ in ({marks})
```

**MongoDB**

```javascript
lockermats.find({_id: {$in: :lockers}}, {'cells.id': 1});
lockermats.updateMany({_id: {$in: :lockers}}, {$set: {'cells.$[cell].status': 'OUT_OF_SERVICE'}},
                      {arrayFilters: [{'cell.status': 'IN_SERVICE'}]});
orders.updateMany({reservations: {$elemMatch: {cellId: {$in: <cells>}, status: 'BOOKED', from: {$gt: :now}}}},
                  {$set: {'reservations.$[leg].accessCodes.$[code].status': 'REVOKED'}},
                  {arrayFilters: [{'leg.cellId': {$in: <cells>}, 'leg.status': 'BOOKED', 'leg.from': {$gt: :now},
                                   'leg.accessCodes': {$exists: true}}, {'code.status': 'ACTIVE'}]});
orders.updateMany({reservations: {$elemMatch: {cellId: {$in: <cells>}, status: 'BOOKED', from: {$gt: :now}}}},
                  {$set: {'reservations.$[leg].status': 'CANCELLED'}},
                  {arrayFilters: [{'leg.cellId': {$in: <cells>}, 'leg.status': 'BOOKED', 'leg.from': {$gt: :now}}]})
in one transaction per batch
```

**Neo4j**

```cypher
MATCH (l:Lockermat)-[:HAS_CELL]->(c:Cell)
WHERE l.id IN $lockers
SET c.status = 'OUT_OF_SERVICE'
WITH c
MATCH (c)<-[:IN_CELL]-(r:Reservation)
WHERE r.status = 'BOOKED' AND r.from > $now
SET r.status = 'CANCELLED'
WITH r
MATCH (r)-[:HAS_CODE]->(a:AccessCode)
WHERE a.status = 'ACTIVE'
SET a.status = 'REVOKED'
```

### U5 — aktualizacja (UPDATE)

Korekta numeru telefonu odbiorcy 5000 przesyłek według id zamówienia, w transakcjach po 1000 przesyłek

Flagi: BA, H1-U. Indeks IDX: IX1. Ustawienia z `ops.yaml`: `ops: 5000`, `ops_xs: 100`, `batch: 1000`.

**PostgreSQL**

```sql
update shipment_ s set recipient_phone_ = v.phone
from unnest(%(orders)s::bigint[], %(phones)s::varchar[]) as v (order_id, phone)
where s.order_id_ = v.order_id
```

**MySQL**

```sql
update shipment_ s
join (values {rows}) as v (order_id, phone) on v.order_id = s.order_id_
set s.recipient_phone_ = v.phone
```

**MongoDB**

```javascript
orders.bulkWrite([{updateOne: {filter: {_id: :order, shipment: {$exists: true}}, update: {$set: {'shipment.recipientPhone': :phone}}}}, …]) in one transaction per batch
```

**Neo4j**

```cypher
UNWIND $rows AS row
MATCH (s:Order:Shipment {id: row.order})
SET s.recipientPhone = row.phone
```

### U6 — aktualizacja (UPDATE)

Unieważnienie wszystkich aktywnych kodów dostępu po upływie ich ważności (ACTIVE → REVOKED), partiami po 5000 kodów

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`.

**PostgreSQL**

```sql
select id_ from access_code_ where status_ = 'ACTIVE' and valid_to_ < %(now)s order by id_;
update access_code_ set status_ = 'REVOKED' where id_ = any(%(codes)s) and status_ = 'ACTIVE'
```

**MySQL**

```sql
select id_ from access_code_ where status_ = 'ACTIVE' and valid_to_ < %(now)s order by id_;
update access_code_ set status_ = 'REVOKED' where id_ in ({marks}) and status_ = 'ACTIVE'
```

**MongoDB**

```javascript
orders.aggregate([{$match: {'reservations.accessCodes': {$elemMatch: {status: 'ACTIVE', validTo: {$lt: :now}}}}},
                  {$unwind: '$reservations'}, {$unwind: '$reservations.accessCodes'},
                  {$match: {'reservations.accessCodes.status': 'ACTIVE', 'reservations.accessCodes.validTo': {$lt: :now}}},
                  {$project: {_id: 0, id: '$reservations.accessCodes.id'}}, {$sort: {id: 1}}]);
orders.updateMany({'reservations.accessCodes.id': {$in: <batch of 5000>}},
                  {$set: {'reservations.$[leg].accessCodes.$[code].status': 'REVOKED'}},
                  {arrayFilters: [{'leg.accessCodes': {$exists: true}},
                                  {'code.id': {$in: <batch of 5000>}, 'code.status': 'ACTIVE'}]})
in one transaction per batch
```

**Neo4j**

```cypher
MATCH (a:AccessCode)
WHERE a.status = 'ACTIVE' AND a.validTo < $now
RETURN a.id ORDER BY a.id;

UNWIND $codes AS id
MATCH (a:AccessCode {id: id})
WHERE a.status = 'ACTIVE'
SET a.status = 'REVOKED'
```

### D1 — usuwanie (DELETE)

Usunięcie wpisów dziennika otwarć skrytek według id, w transakcjach po 100 wpisów

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 50`, `batch: 100`.

**PostgreSQL**

```sql
delete from cell_opening_ where id_ = any(%s)
```

**MySQL**

```sql
delete from cell_opening_ where id_ in ({marks})
```

**MongoDB**

```javascript
orders.update_many({"reservations.accessCodes.openings.id": {"$in": :openings}}, {"$pull": {"reservations.$[leg].accessCodes.$[code].openings": {"id": {"$in": :openings}}}}, {"arrayFilters": [{"leg.accessCodes": {"$exists": true}}, {"code.openings": {"$exists": true}}]});
incidents.update_many({"serviceOpenings.id": {"$in": :openings}}, {"$pull": {"serviceOpenings": {"id": {"$in": :openings}}}})
```

**Neo4j**

```cypher
MATCH (o:CellOpening) WHERE o.id IN $openings DETACH DELETE o
```

### D2 — usuwanie (DELETE)

Usunięcie zamówień ze wszystkimi zależnymi wierszami, od dzieci do rodzica w 7 tabelach, jedno zamówienie na transakcję

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1000`, `ops_xs: 20`, `batch: 1`.

**PostgreSQL**

```sql
delete from cell_opening_ co using access_code_ a, reservation_ r where co.access_code_id_ = a.id_ and a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from cell_opening_ co using incident_ i, reservation_ r where co.incident_id_ = i.id_ and i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from access_code_ a using reservation_ r where a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from payment_ where order_id_ = any(%(orders)s);
delete from incident_ i using reservation_ r where i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from reservation_ where order_id_ = any(%(orders)s);
delete from shipment_ where order_id_ = any(%(orders)s);
delete from order_ where id_ = any(%(orders)s)
```

**MySQL**

```sql
delete co from cell_opening_ co join access_code_ a on a.id_ = co.access_code_id_ join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ in ({marks});
delete co from cell_opening_ co join incident_ i on i.id_ = co.incident_id_ join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks});
delete a from access_code_ a join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ in ({marks});
delete from payment_ where order_id_ in ({marks}) order by refund_of_id_ is null;
delete i from incident_ i join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks});
delete from reservation_ where order_id_ in ({marks});
delete from shipment_ where order_id_ in ({marks});
delete from order_ where id_ in ({marks})
```

**MongoDB**

```javascript
orders.delete_one({_id: :order});
incidents.delete_many({orderId: {$in: :orders}});
shipLinks.delete_many({orderId: {$in: :orders}})
```

**Neo4j**

```cypher
MATCH (o:Order) WHERE o.id IN $orders
OPTIONAL MATCH ()-[link:SHIPS_TO {orderId: o.id}]->()
DELETE link
WITH o
OPTIONAL MATCH (o)-[:HAS_LEG]->(leg:Reservation)
OPTIONAL MATCH (leg)-[:HAS_CODE]->(code:AccessCode)
OPTIONAL MATCH (code)<-[:OPENED_WITH]-(opening:CellOpening)
OPTIONAL MATCH (leg)<-[:ABOUT]-(incident:Incident)
OPTIONAL MATCH (incident)<-[:OPENED_FOR]-(service:CellOpening)
OPTIONAL MATCH (o)-[:HAS_PAYMENT]->(payment:Payment)
DETACH DELETE service, opening, code, payment, incident, leg, o
```

### D3 — usuwanie (DELETE)

Usunięcie wpisów dziennika otwarć skrytek starszych niż 540 dni przed T0, partiami po 5000

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`, `cutoff_days: 540`.

**PostgreSQL**

```sql
select id_ from cell_opening_ where requested_at_ < %s order by id_;
delete from cell_opening_ where id_ = any(%s)
```

**MySQL**

```sql
select id_ from cell_opening_ where requested_at_ < %s order by id_;
delete from cell_opening_ where id_ in ({marks})
```

**MongoDB**

```javascript
orders.aggregate([{"$match": {"reservations.accessCodes.openings.requestedAt": {"$lt": :cutoff, "$exists": true}}}, {"$unwind": "$reservations"}, {"$unwind": "$reservations.accessCodes"}, {"$unwind": "$reservations.accessCodes.openings"}, {"$match": {"reservations.accessCodes.openings.requestedAt": {"$lt": :cutoff}}}, {"$project": {"_id": 0, "id": "$reservations.accessCodes.openings.id"}}]);
incidents.aggregate([{"$match": {"serviceOpenings.requestedAt": {"$lt": :cutoff}}}, {"$unwind": "$serviceOpenings"}, {"$match": {"serviceOpenings.requestedAt": {"$lt": :cutoff}}}, {"$project": {"_id": 0, "id": "$serviceOpenings.id"}}]);
orders.update_many({"reservations.accessCodes.openings.id": {"$in": :openings}}, {"$pull": {"reservations.$[leg].accessCodes.$[code].openings": {"id": {"$in": :openings}}}}, {"arrayFilters": [{"leg.accessCodes": {"$exists": true}}, {"code.openings": {"$exists": true}}]});
incidents.update_many({"serviceOpenings.id": {"$in": :openings}}, {"$pull": {"serviceOpenings": {"id": {"$in": :openings}}}})
```

**Neo4j**

```cypher
MATCH (o:CellOpening) WHERE o.requestedAt < $cutoff RETURN o.id ORDER BY o.id;
MATCH (o:CellOpening) WHERE o.id IN $openings DETACH DELETE o
```

### D4 — usuwanie (DELETE)

Usunięcie klientów bez żadnego zamówienia (antyzłączenie), partiami po 5000 klientów

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`.

**PostgreSQL**

```sql
select c.id_ from customer_ c
where not exists (select 1 from order_ o where o.customer_id_ = c.id_)
order by c.id_;
delete from customer_ where id_ = any(%s)
```

**MySQL**

```sql
select c.id_ from customer_ c
where not exists (select 1 from order_ o where o.customer_id_ = c.id_)
order by c.id_;
delete from customer_ where id_ in ({marks})
```

**MongoDB**

```javascript
customers.aggregate([{"$lookup": {"from": "orders", "localField": "_id", "foreignField": "customerId", "pipeline": [{"$limit": 1}, {"$project": {"_id": 1}}], "as": "orders"}}, {"$match": {"orders": {"$size": 0}}}, {"$project": {"_id": 1}}]);
customers.delete_many({"_id": {"$in": :batch}})
```

**Neo4j**

```cypher
MATCH (c:Customer) WHERE COUNT { (c)-[:PLACED]->() } = 0 RETURN c.id ORDER BY c.id;
MATCH (c:Customer) WHERE c.id IN $customers DELETE c
```

### D5 — usuwanie (DELETE)

Usunięcie anulowanych i wygasłych zamówień starszych niż rok przed T0 ze wszystkimi zależnymi wierszami, partiami po 5000 zamówień

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`, `cutoff_years: 1`.

**PostgreSQL**

```sql
select id_ from order_ where status_ in ('CANCELLED', 'EXPIRED') and created_at_ < %s order by id_;
delete from cell_opening_ co using access_code_ a, reservation_ r where co.access_code_id_ = a.id_ and a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from cell_opening_ co using incident_ i, reservation_ r where co.incident_id_ = i.id_ and i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from access_code_ a using reservation_ r where a.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from payment_ where order_id_ = any(%(orders)s);
delete from incident_ i using reservation_ r where i.reservation_id_ = r.id_ and r.order_id_ = any(%(orders)s);
delete from reservation_ where order_id_ = any(%(orders)s);
delete from shipment_ where order_id_ = any(%(orders)s);
delete from order_ where id_ = any(%(orders)s)
```

**MySQL**

```sql
select id_ from order_ where status_ in ('CANCELLED', 'EXPIRED') and created_at_ < %s order by id_;
delete co from cell_opening_ co join access_code_ a on a.id_ = co.access_code_id_ join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ in ({marks});
delete co from cell_opening_ co join incident_ i on i.id_ = co.incident_id_ join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks});
delete a from access_code_ a join reservation_ r on r.id_ = a.reservation_id_ where r.order_id_ in ({marks});
delete from payment_ where order_id_ in ({marks}) order by refund_of_id_ is null;
delete i from incident_ i join reservation_ r on r.id_ = i.reservation_id_ where r.order_id_ in ({marks});
delete from reservation_ where order_id_ in ({marks});
delete from shipment_ where order_id_ in ({marks});
delete from order_ where id_ in ({marks})
```

**MongoDB**

```javascript
orders.find({"status": {"$in": ["CANCELLED", "EXPIRED"]}, "createdAt": {"$lt": :cutoff}}, {"_id": 1});
orders.delete_many({"_id": {"$in": :batch}});
incidents.delete_many({"orderId": {"$in": :batch}});
shipLinks.delete_many({"orderId": {"$in": :batch}})
```

**Neo4j**

```cypher
MATCH (o:Order) WHERE o.status IN ['CANCELLED', 'EXPIRED'] AND o.createdAt < $cutoff RETURN o.id ORDER BY o.id;
MATCH (o:Order) WHERE o.id IN $orders
OPTIONAL MATCH ()-[link:SHIPS_TO {orderId: o.id}]->()
DELETE link
WITH o
OPTIONAL MATCH (o)-[:HAS_LEG]->(leg:Reservation)
OPTIONAL MATCH (leg)-[:HAS_CODE]->(code:AccessCode)
OPTIONAL MATCH (code)<-[:OPENED_WITH]-(opening:CellOpening)
OPTIONAL MATCH (leg)<-[:ABOUT]-(incident:Incident)
OPTIONAL MATCH (incident)<-[:OPENED_FOR]-(service:CellOpening)
OPTIONAL MATCH (o)-[:HAS_PAYMENT]->(payment:Payment)
DETACH DELETE service, opening, code, payment, incident, leg, o
```

### D6 — usuwanie (DELETE)

Usunięcie nieużywanych punktów razem ze skrytkami i godzinami otwarcia po sprawdzeniu, że żadna rezerwacja ani zgłoszenie nie wskazuje ich skrytek, partiami po 5000 punktów

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`.

**PostgreSQL**

```sql
select l.id_ from lockermat_ l
where not exists (
    select 1 from lockermat_cell_ c
    where c.lockermat_id_ = l.id_
      and (exists (select 1 from reservation_ r where r.cell_id_ = c.id_)
           or exists (select 1 from incident_ i where i.cell_id_ = c.id_))
)
order by l.id_;
delete from lockermat_opening_hours_ where lockermat_id_ = any(%s);
delete from lockermat_cell_ where lockermat_id_ = any(%s);
delete from lockermat_ where id_ = any(%s)
```

**MySQL**

```sql
select l.id_ from lockermat_ l
where not exists (
    select 1 from lockermat_cell_ c
    where c.lockermat_id_ = l.id_
      and (exists (select 1 from reservation_ r where r.cell_id_ = c.id_)
           or exists (select 1 from incident_ i where i.cell_id_ = c.id_))
)
order by l.id_;
delete from lockermat_opening_hours_ where lockermat_id_ in ({marks});
delete from lockermat_cell_ where lockermat_id_ in ({marks});
delete from lockermat_ where id_ in ({marks})
```

**MongoDB**

```javascript
lockermats.aggregate([{"$project": {"cells.id": 1}}, {"$lookup": {"from": "orders", "localField": "cells.id", "foreignField": "reservations.cellId", "pipeline": [{"$limit": 1}, {"$project": {"_id": 1}}], "as": "legs"}}, {"$match": {"legs": {"$size": 0}}}, {"$lookup": {"from": "incidents", "localField": "cells.id", "foreignField": "cellId", "pipeline": [{"$limit": 1}, {"$project": {"_id": 1}}], "as": "incidents"}}, {"$match": {"incidents": {"$size": 0}}}, {"$project": {"_id": 1}}]);
lockermats.delete_many({"_id": {"$in": :batch}})
```

**Neo4j**

```cypher
MATCH (l:Lockermat)
WHERE NOT EXISTS { (l)-[:HAS_CELL]->(:Cell)<-[:IN_CELL|AT_CELL]-() }
RETURN l.id ORDER BY l.id;
MATCH (l:Lockermat) WHERE l.id IN $lockers
OPTIONAL MATCH (l)-[link:HAS_CELL|HAS_HOURS]->(child)
DELETE link, child
WITH DISTINCT l
DELETE l
```

## Scenariusze JSON

### J1 — tworzenie (INSERT)

Dopisanie 10 000 zdarzeń audytu (migawka aktora i lista zmian w JSON) partiami po 1000 w jednej transakcji na partię; rodzaje aktorów i zmiany jak w danych

Flagi: BA, H1-I. Indeks IDX: JX1, JX2. Ustawienia z `ops.yaml`: `ops: 10000`, `ops_xs: 100`, `batch: 1000`.

**PostgreSQL**

```sql
insert into audit_event_ (id_, at_, entity_, entity_id_, action_, actor_, changes_)
select * from unnest(%(id)s::bigint[], %(at)s::timestamptz[], %(entity)s::varchar[], %(entity_id)s::bigint[],
                     %(action)s::varchar[], %(actor)s::jsonb[], %(changes)s::jsonb[])
```

**MySQL**

```sql
insert into audit_event_ (id_, at_, entity_, entity_id_, action_, actor_, changes_, changes_new_)
values (%s, %s, %s, %s, %s, %s, %s, %s)
```

**MongoDB**

```javascript
auditEvents.insertMany([{_id, at, entity, entityId, action, actor: {kind, …}, changes: [{f, old, new}]}, …]) in one transaction per batch
```

### J2 — odczyt (SELECT)

RODO art. 15: wszystkie zdarzenia audytu osoby w kolejności czasu, wyszukane w migawce aktora po e-mailu lub telefonie (klient: e-mail i telefon, odbiorca: telefon), ×100 osób

Flagi: BA, H1-S. Indeks IDX: JX1. Ustawienia z `ops.yaml`: `ops: 100`, `ops_xs: 10`.

**PostgreSQL**

```sql
select id_, at_, entity_, entity_id_, action_, actor_, changes_
from audit_event_
where actor_ ->> 'email' = %(email)s or actor_ ->> 'phone' = %(phone)s
order by at_, id_
```

**MySQL**

```sql
select id_, at_, entity_, entity_id_, action_, actor_, changes_
from audit_event_
where cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin = %(email)s
   or cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin = %(phone)s
order by at_, id_
```

**MongoDB**

```javascript
auditEvents.aggregate([
  {$match: {$or: [{'actor.email': :email}, {'actor.phone': :phone}]}},
  {$sort: {at: 1, _id: 1}}
])
where an unknown e-mail or phone leaves its clause out of $or
```

### J3 — odczyt (SELECT)

Istnienie kluczy JSON: liczba zdarzeń audytu na rodzaj aktora, w tym z e-mailem i tylko z imieniem lub telefonem (cała tabela)

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: 1`, `ops_xs: 1`.

**PostgreSQL**

```sql
select actor_ ->> 'kind', count(*),
       count(*) filter (where actor_ ? 'email'),
       count(*) filter (where actor_ ?| array['name', 'phone'] and not actor_ ? 'email')
from audit_event_
group by 1
```

**MySQL**

```sql
select actor_ ->> '$.kind', count(*),
       sum(json_contains_path(actor_, 'one', '$.email')),
       sum(json_contains_path(actor_, 'one', '$.name', '$.phone') and not json_contains_path(actor_, 'one', '$.email'))
from audit_event_
group by 1
```

**MongoDB**

```javascript
auditEvents.aggregate([
  {$group: {_id: '$actor.kind', events: {$sum: 1},
            withEmail: {$sum: {$cond: [<email exists>, 1, 0]}},
            nameOrPhoneOnly: {$sum: {$cond: [{$and: [{$not: [<email exists>]}, {$or: [<name exists>, <phone exists>]}]}, 1, 0]}}}}
])
where <key exists> = {$ne: [{$type: '$actor.<key>'}, 'missing']}
```

### J4 — odczyt (SELECT)

Wyszukiwanie elementu tablicy JSON: zdarzenia audytu z jednego miesiąca, których lista zmian zawiera zmianę status_ na CANCELLED, policzone według encji, ×12 miesięcy

Flagi: BA, H1-S. Indeks IDX: JX2. Ustawienia z `ops.yaml`: `ops: 12`, `ops_xs: 3`.

**PostgreSQL**

```sql
select entity_, count(*)
from audit_event_
where changes_ @> jsonb_build_array(jsonb_build_object('f', 'status_', 'new', %(value)s::text))
  and at_ >= %(since)s and at_ < %(until)s
group by entity_
```

**MySQL**

```sql
select entity_, count(*)
from audit_event_
where %(value)s member of (changes_new_)
  and json_contains(changes_, json_object('f', 'status_', 'new', %(value)s))
  and at_ >= %(since)s and at_ < %(until)s
group by entity_
```

**MongoDB**

```javascript
auditEvents.aggregate([
  {$match: {changes: {$elemMatch: {f: 'status_', new: :value}}, at: {$gte: :since, $lt: :until}}},
  {$group: {_id: '$entity', events: {$sum: 1}}}
])
```

### J5 — aktualizacja (UPDATE)

RODO art. 17: pseudonimizacja 100 osób (klient: e-mail i telefon, odbiorca: telefon) we wszystkich ich zdarzeniach audytu: e-mail zastąpiony skrótem HMAC-SHA256 z kluczem, imię i telefon usunięte z migawki aktora, partiami po 5000 zdarzeń

Flagi: BA. Indeks IDX: JX1. Ustawienia z `ops.yaml`: `ops: 100`, `ops_xs: 10`, `batch: 5000`.

**PostgreSQL**

```sql
select id_, actor_ ->> 'email'
from audit_event_
where actor_ ->> 'email' = any(%(emails)s) or actor_ ->> 'phone' = any(%(phones)s)
order by id_
;

update audit_event_ a
set actor_ = case when t.pseudonym is null then a.actor_
                  else jsonb_set(a.actor_, '{email}', to_jsonb(t.pseudonym)) end - 'name' - 'phone'
from unnest(%(id)s::bigint[], %(pseudonym)s::text[]) as t (id_, pseudonym)
where a.id_ = t.id_
```

**MySQL**

```sql
select id_, actor_ ->> '$.email'
from audit_event_
where cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin in (:emails)
   or cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin in (:phones)
order by id_
;

update audit_event_ a
join json_table(%s, '$[*]' columns (id_ bigint path '$[0]', pseudonym varchar(64) path '$[1]')) t on t.id_ = a.id_
set a.actor_ = json_remove(json_replace(a.actor_, '$.email', t.pseudonym), '$.name', '$.phone')
```

**MongoDB**

```javascript
auditEvents.find({$or: [{'actor.email': {$in: :emails}}, {'actor.phone': {$in: :phones}}]}, {'actor.email': 1})
;

auditEvents.bulkWrite([
  {updateMany: {filter: {_id: {$in: <events with this e-mail>}},
                update: {$set: {'actor.email': :pseudonym}, $unset: {'actor.name': '', 'actor.phone': ''}}}}, …,
  {updateMany: {filter: {_id: {$in: <events without e-mail>}}, update: {$unset: {'actor.name': '', 'actor.phone': ''}}}}
]) in one transaction per batch
```

### J6 — usuwanie (DELETE)

Retencja: usunięcie zdarzeń audytu niedotyczących płatności, starszych niż 18 miesięcy przed T0, partiami po 5000

Flagi: —. Indeks IDX: —. Ustawienia z `ops.yaml`: `ops: null`, `ops_xs: null`, `batch: 5000`, `cutoff_months: 18`.

**PostgreSQL**

```sql
select id_ from audit_event_ where at_ < %s and entity_ <> 'PAYMENT' order by id_;
delete from audit_event_ where id_ = any(%s)
```

**MySQL**

```sql
select id_ from audit_event_ where at_ < %s and entity_ <> 'PAYMENT' order by id_;
delete from audit_event_ where id_ in ({marks})
```

**MongoDB**

```javascript
auditEvents.find({at: {$lt: :cutoff}, entity: {$ne: 'PAYMENT'}}, {_id: 1});
auditEvents.deleteMany({_id: {$in: :events}}) in one transaction per batch
```

## Indeksy IDX

| Indeks | PostgreSQL | MySQL | MongoDB | Neo4j | Obsługuje | Utrzymują |
|---|---|---|---|---|---|---|
| IX1 | `ix1__idx` na `shipment_` (`recipient_phone_`) | `ix1__idx` na `shipment_` (`recipient_phone_`) | `ix1__idx` na `orders` (`shipment.recipientPhone`) | `ix1__idx` na `Shipment` (`recipientPhone`) | R4 | C4, U5 |
| IX2 | `ix2__idx` na `order_` (`status_`, `created_at_`) | `ix2__idx` na `order_` (`status_`, `created_at_`) | `ix2__idx` na `orders` (`status`, `createdAt`) | `ix2__idx` na `Order` (`status`, `createdAt`) | R5 | C3, C4, U1, U3 |
| IX3 | `ix3__idx` na `payment_` (`created_at_`) | `ix3__idx` na `payment_` (`created_at_`) | `ix3__idx` na `orders` (`payments.createdAt`) | `ix3__idx` na `Payment` (`createdAt`) | R6 | C3, C4, C6 |
| IX4 | `ix4__idx` na `cell_opening_` (`requested_at_`) | `ix4__idx` na `cell_opening_` (`requested_at_`) | `ix4__idx` na `orders` (`reservations.accessCodes.openings.requestedAt`) | `ix4__idx` na `CellOpening` (`requestedAt`) | R7 | C2 |
| JX1 | `jx1_email__idx` na `audit_event_` (`actor_->>'email'`); `jx1_phone__idx` na `audit_event_` (`actor_->>'phone'`) | `jx1_email__idx` na `audit_event_` (`CAST(actor_->>'$.email' AS CHAR(320) CHARACTER SET utf8mb4) COLLATE utf8mb4_0900_bin`); `jx1_phone__idx` na `audit_event_` (`CAST(actor_->>'$.phone' AS CHAR(16) CHARACTER SET utf8mb4) COLLATE utf8mb4_0900_bin`) | `jx1_email__idx` na `auditEvents` (`actor.email`); `jx1_phone__idx` na `auditEvents` (`actor.phone`) | — | J2 | J1, J5 |
| JX2 | `jx2__idx` na `audit_event_` (`changes_`) | `jx2__idx` na `audit_event_` (`CAST(changes_new_ AS CHAR(32) ARRAY)`) | `jx2__idx` na `auditEvents` (`changes.f`, `changes.new`) | — | J4 | J1 |

### PostgreSQL — `bench/ddl/pg/idx/indexes.sql`

```sql
create index ix1__idx on shipment_ (recipient_phone_);
create index ix2__idx on order_ (status_, created_at_);
create index ix3__idx on payment_ (created_at_);
create index ix4__idx on cell_opening_ (requested_at_);
create index jx1_email__idx on audit_event_ ((actor_ ->> 'email'));
create index jx1_phone__idx on audit_event_ ((actor_ ->> 'phone'));
create index jx2__idx on audit_event_ using gin (changes_ jsonb_path_ops) with (fastupdate = off);
```

### MySQL — `bench/ddl/mysql/idx/indexes.sql`

```sql
create index ix1__idx on shipment_ (recipient_phone_);
create index ix2__idx on order_ (status_, created_at_);
create index ix3__idx on payment_ (created_at_);
create index ix4__idx on cell_opening_ (requested_at_);
create index jx1_email__idx on audit_event_ ((cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin));
create index jx1_phone__idx on audit_event_ ((cast(actor_ ->> '$.phone' as char(16) character set utf8mb4) collate utf8mb4_0900_bin));
create index jx2__idx on audit_event_ ((cast(changes_new_ as char(32) array)));
```

### MongoDB — `bench/ddl/mongo/idx/indexes.json`

```json
[
  {
    "createIndexes": "orders",
    "indexes": [
      {
        "key": {
          "shipment.recipientPhone": 1
        },
        "name": "ix1__idx",
        "partialFilterExpression": {
          "shipment.recipientPhone": {
            "$exists": true
          }
        }
      },
      {
        "key": {
          "status": 1,
          "createdAt": 1
        },
        "name": "ix2__idx"
      },
      {
        "key": {
          "payments.createdAt": 1
        },
        "name": "ix3__idx",
        "partialFilterExpression": {
          "payments.createdAt": {
            "$exists": true
          }
        }
      },
      {
        "key": {
          "reservations.accessCodes.openings.requestedAt": 1
        },
        "name": "ix4__idx",
        "partialFilterExpression": {
          "reservations.accessCodes.openings.requestedAt": {
            "$exists": true
          }
        }
      }
    ]
  },
  {
    "createIndexes": "auditEvents",
    "indexes": [
      {
        "key": {
          "actor.email": 1
        },
        "name": "jx1_email__idx",
        "partialFilterExpression": {
          "actor.email": {
            "$exists": true
          }
        }
      },
      {
        "key": {
          "actor.phone": 1
        },
        "name": "jx1_phone__idx",
        "partialFilterExpression": {
          "actor.phone": {
            "$exists": true
          }
        }
      },
      {
        "key": {
          "changes.f": 1,
          "changes.new": 1
        },
        "name": "jx2__idx"
      }
    ]
  }
]
```

### Neo4j — `bench/ddl/neo4j/idx/indexes.cypher`

```cypher
create range index ix1__idx for (n:Shipment) on (n.recipientPhone);
create range index ix2__idx for (n:Order) on (n.status, n.createdAt);
create range index ix3__idx for (n:Payment) on (n.createdAt);
create range index ix4__idx for (n:CellOpening) on (n.requestedAt);
call db.resampleOutdatedIndexes();
call db.awaitIndexes(3600);
```
