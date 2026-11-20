# Stos aplikacji

Backend korzysta z Javy 21, Spring Boot 4.1.3 i Maven Wrapper z Maven 3.10.1. Test integracyjny uruchamia obraz `bagazomat-postgres:17-postgis`. Obraz można zbudować z katalogu głównego poleceniem `docker compose -f compose.bench.yaml build pg`. Następnie uruchom `./mvnw verify` w `app/backend`.

| Obszar | Zależność |
|---|---|
| HTTP i Jackson 3 | `spring-boot-starter-webmvc` |
| JPA i Hibernate | `spring-boot-starter-data-jpa` |
| JWT | `spring-boot-starter-security-oauth2-resource-server` |
| Migracje | `spring-boot-starter-flyway` i `flyway-database-postgresql` |
| Sterownik | `org.postgresql:postgresql` |

Spring Boot zarządza wersjami zależności. Do drzew JSON służy `tools.jackson.databind.JsonNode` z Jacksona 3. Pola JPA o typie `jsonb` mapuj przez `@JdbcTypeCode(SqlTypes.JSON)`. Flyway uruchamia V1, a Hibernate sprawdza mapowanie z `ddl-auto: validate`.

- `location_` nie jest polem encji. Współrzędne czytaj przez `@Formula("st_x(location_)")` i `@Formula("st_y(location_)")`.
- Stosuj `allocationSize = 1` przy każdej sekwencji. Wszystkie sekwencje w schemacie mają krok 1.
- Mapuj `smallint` na `Short`, a `timestamptz` na `Instant`.
- Kolumny wyliczane przez bazę pomijaj w encji lub mapuj z `insertable = false, updatable = false`.
- Przed zapisem `access_code_` pobierz id poleceniem `select nextval('access_code_id_seq_')`. Wyprowadź z niego PIN i `code_hmac_`, a następnie wstaw rekord z tym samym id.

Migracja `V2__demo_seed.sql` zapisuje dane demonstracyjne: 12 punktów w Krakowie, Warszawie, Gdańsku i Wrocławiu, po 12 skrytek w każdym (6 S, 4 M, 2 L), trzy otwarte taryfy oraz klientów `anna`, `jan` i nadawcę przesyłek demonstracyjnych bez konta w Keycloak. Punkty nie mają godzin otwarcia, więc działają całą dobę. API przyjmuje tylko token, którego `sub` jest równy `keycloak_id_` klienta z `customer_`. Inny token dostaje 403. Profil `dev`, włączony w `compose.app.yaml`, udostępnia `POST /api/dev/reset`. Endpoint czyści zamówienia, ich tabele zależne i `audit_event_`, a dane demonstracyjne zostawia.

Encje JPA obejmują tabele, których używa aplikacja. Aplikacja tylko czyta `lockermat_`, `lockermat_cell_`, `tariff_` i `customer_`, więc ich encje mają `@Immutable` i nie mają generatora id. Encje zamówień, rezerwacji, przesyłek, kodów, otwarć, płatności i zdarzeń audytowych biorą id z sekwencji swojej tabeli. `AccessCode` dostaje je z `AccessCodeRepository.nextId()`. Kolumny z domyślnym `now()` mają `@Generated`, więc wartość nadaje baza. Tabele `lockermat_opening_hours_` i `incident_` nie mają encji.

Błąd API ma postać `{code, message}` z polskim komunikatem i bez tekstu SQL. Brakujący lub błędny parametr żądania daje 400 `BAD_REQUEST`. Naruszenie unikalności (23505) lub wykluczenia (23P01) daje 409 `CONFLICT`. Inne naruszenie integralności daje 500 `INTERNAL_ERROR`. `AuditWriter.write` zapisuje `audit_event_` w transakcji wywołującego, a bez transakcji rzuca wyjątek. Aktora tworzą `AuditActor.customer(jwt)`, `AuditActor.recipient(jwt, phone)` i `AuditActor.system(job)`. Zmiana pola to `AuditChange` zapisywany jako `{f, old, new}`.

`GET /api/lockermats?q=…&from=…&to=…` wyszukuje punkty. `from` i `to` to chwile ISO-8601, np. `2026-11-21T10:00:00Z`, a `from` musi być wcześniej niż `to`. `q` jest opcjonalne. Wynik obejmuje aktywne punkty, których adres lub nazwa zawiera `q` bez względu na wielkość liter, posortowane po `address_`, a potem po `name_`. Każdy punkt ma `id`, `name`, `address`, `lng`, `lat` i listę `sizes` z rozmiarami S, M i L. Dla każdego rozmiaru `free` to liczba skrytek wolnych w oknie `[from, to)` według NOTES §1.3, a `price` to cena przechowania według NOTES §1.2: stawka dobowa obecnej taryfy razy liczba rozpoczętych dób.

`POST /api/orders` przyjmuje `{lockermatId, size, from, to}` i zwraca 201 z zamówieniem. W jednej transakcji tworzy zamówienie STORAGE według NOTES §1.2, wybiera skrytkę i wstawia rezerwację według §1.3 oraz zapisuje zdarzenie `ORDER`/`CREATED` z aktorem CUSTOMER. Numer zamówienia to `BAG-` i id uzupełnione zerami do 10 cyfr, jak w danych benchmarku. `to` musi być późniejsze niż `now()`. Termin płatności to wcześniejsza z chwil `now() + 15 min` i `to`. Brak wolnej skrytki daje 409 `CONFLICT`. Po naruszeniu wykluczenia (23P01) rezerwacja zaczyna się od nowa w nowej transakcji z nowym kontekstem utrwalania, najwyżej trzy próby łącznie. `GET /api/orders` zwraca zamówienia STORAGE zalogowanego klienta od najnowszego. `GET /api/orders/{id}` zwraca jedno z nich, a zamówienie innego klienta lub nieistniejące daje 404 `NOT_FOUND`.

Keycloak 26.4 używa własnego woluminu z bazą deweloperską. `make app-up` uruchamia PostgreSQL, Keycloak, backend i frontend. W przeglądarce issuer to `http://localhost:8081/realms/bagazomat`. Backend weryfikuje ten issuer i pobiera klucze z wewnętrznego adresu `http://keycloak:8080/realms/bagazomat/protocol/openid-connect/certs`.

Frontend korzysta z Node.js 22, Vite 8, React 19, TypeScript 6 i `react-oidc-context`. Po `make app-up` otwórz `http://localhost:5173`. Konto demonstracyjne to `anna` lub `jan` z hasłem `demo`. Uruchom `npm ci && npm run build` w `app/frontend`. Testy uruchomisz w `e2e` poleceniami `npm ci`, `npx playwright install chromium` oraz `npx playwright test`.

## Generator benchmarku

Runner używa Pythona 3.13 i uv 0.13.8. Zależności generatora to Faker 40.54.0, NumPy 2.5.5, PyArrow 26.0.1 i PyYAML 6.0.3. `uv.lock` ustala też wersje zależności pośrednich. `make data SIZE=XS` zapisuje dane w `out/xs/data/`. Rozmiary S, M i L trafiają do `data/<rozmiar>/`. Współrzędne w kolumnie `location_` są binarnym EWKB Point o SRID 4326, w kolejności długość, szerokość.

DuckDB 2.0.1 sprawdza pliki Parquet bez uruchamiania testowanych SZBD.

`make validate SIZE=S` sprawdza spójność Parquet, warunki scenariuszy z `bench/scenarios/ops.yaml` i sumy SHA-256 z manifestu. Parametry R2 mogą ponownie wybierać tego samego klienta z dużą liczbą zamówień. W XS scenariusze korzystają z liczby operacji `ops_xs`.

## Ładowanie PostgreSQL

`make load ENGINE=pg SIZE=S` uruchamia PostgreSQL i tworzy od nowa bazę `bagazomat`. Loader korzysta z psycopg 3.3.9. W jednej transakcji wykonuje `bench/ddl/pg/base/tables.sql` i `COPY … FREEZE` dla 13 tabel. Następnie `base/constraints.sql` dodaje klucze, CHECK, FK, EXCLUDE i indeksy schematu, więc PostgreSQL sprawdza każdy wiersz. `base/fk_support.sql` dodaje dwa indeksy wspierające FK. Na końcu loader wykonuje `VACUUM (FREEZE, ANALYZE)`. Sesja ładowania wymaga `statement_timeout = 0`.

Funkcja `apply_index` z `bench/load/pg/loader.py` dodaje indeksy z `bench/ddl/pg/idx/`, analizuje tylko `audit_event_` i wykonuje `VACUUM`.

Test katalogu porównuje `base/` bez `fk_support.sql` ze schematem `docs/design/schema.sql` zastosowanym wprost. Przy działającym PostgreSQL uruchom go poleceniem `docker compose -f compose.bench.yaml run --rm runner python -m unittest discover -s bench/load/tests`.

## Schemat MySQL

`bench/ddl/mysql/base/` odwzorowuje 13 tabel w InnoDB w kolejności ładowania z ROADMAP. `tables.sql` tworzy kolumny, kolumny wyliczane, PK, zwykłe UNIQUE, CHECK oraz tabelę blokad `excl_guard_`. `foreign_keys.sql` dodaje klucze obce. `indexes.sql` dodaje unikalne indeksy funkcyjne zamiast indeksów częściowych, indeksy CASE, indeksy schematu, indeksy sond, SPATIAL i FULLTEXT z parserem ngram. `triggers.sql` zastępuje pięć reguł EXCLUDE parami wyzwalaczy BEFORE INSERT i BEFORE UPDATE. `idx/indexes.sql` dodaje IX1–IX4, JX1 i JX2.

Testy reguł korzystają z mysql-connector-python 26.10.0 i pytest 9.2.0. Przy działającym MySQL (`make up ENGINE=mysql`) uruchom je poleceniem `docker compose -f compose.bench.yaml run --rm runner python -m pytest -p no:cacheprovider bench/ddl/mysql/tests`. Testy łączą się jako root, tworzą własną bazę `ddl_rules_` i usuwają ją na końcu, więc nie zmieniają bazy `bagazomat`.

## Ładowanie MySQL

`make load ENGINE=mysql SIZE=S` uruchamia MySQL i tworzy od nowa bazę `bagazomat`. Loader łączy się jako root przez mysql-connector-python i zachowuje kolejność ładowania z ROADMAP. `base/tables.sql` tworzy tabele z PK, zwykłymi UNIQUE i CHECK. `LOAD DATA LOCAL INFILE` ładuje 13 tabel przy `unique_checks = 0`. `base/foreign_keys.sql` dodaje FK przy `foreign_key_checks = 0`. Potem `base/indexes.sql` dodaje indeksy funkcyjne i indeksy CASE, a `base/triggers.sql` wyzwalacze. Na końcu `ANALYZE TABLE` liczy statystyki 13 tabel. Przy `innodb_stats_auto_recalc = OFF` loader wymaga wiersza w `mysql.innodb_table_stats` dla każdej z nich.

DuckDB zapisuje każdą tabelę do tymczasowego pliku CSV. Każda wartość jest w cudzysłowie, a NULL to słowo `NULL` bez cudzysłowu. Plik nie ma znaku ucieczki (`escaped by ''`). Znaczniki czasu trafiają do pliku jako czas UTC bez strefy. `code_hmac_` przechodzi jako hex przez `unhex`, a `location_` jako WKT przez `ST_GeomFromText(…, 4326, 'axis-order=long-lat')`. Loader wylicza `changes_new_` z `changes_`. Skrót `code_hmac_` o długości innej niż 32 bajty przerywa ładowanie, bo `BINARY(32)` dopełnia krótszą wartość zerami. `LOAD DATA LOCAL` zamienia błędy wierszy na ostrzeżenia, więc każde ostrzeżenie też przerywa ładowanie. `docker/conf/mysql/my.cnf` włącza `local-infile`.

Test przekształcenia nie wymaga bazy. Uruchom go poleceniem `docker compose -f compose.bench.yaml run --rm runner python -m unittest bench.load.tests.test_mysql`.

## Ładowanie MongoDB

`make load ENGINE=mongo SIZE=S` uruchamia MongoDB i tworzy od nowa bazę `bagazomat`. Transformacja `bench/transform/mongo/` buduje w DuckDB dokumenty Extended JSON siedmiu kolekcji: `lockermats`, `tariffs`, `customers`, `orders`, `incidents`, `auditEvents` i `shipLinks`. Zapisuje je w `data/<rozmiar>/mongo/`, a dla XS w `out/xs/data/mongo/`. Transformacja pomija pola z wartością NULL i puste tablice osadzone.

Loader korzysta z pymongo 4.19.0 i działa tylko w kontenerze `runner`. Najpierw `bench/ddl/mongo/base/collections.json` tworzy kolekcje z walidatorami `$jsonSchema`. Następnie `mongoimport` z obrazu MongoDB importuje każdą kolekcję, a walidatory sprawdzają każdy dokument. Narzędzie działa w kontenerze pomocniczym, który widzi katalog roboczy tylko do odczytu. Potem `base/indexes.json` tworzy indeksy BASE. Na końcu loader porównuje liczbę wierszy każdej tabeli logicznej, także elementów osadzonych, z manifestem.

Funkcja `apply_index` z `bench/load/mongo/loader.py` dodaje indeksy z `bench/ddl/mongo/idx/indexes.json`.

Testy MongoDB wymagają danych XS (`make data SIZE=XS`) i działającego MongoDB (`make up ENGINE=mongo`). Uruchom je poleceniem `docker compose -f compose.bench.yaml run --rm runner python -m pytest -p no:cacheprovider bench/load/tests/test_mongo.py`. Testy importują zamówienia i zdarzenia audytowe XS do osobnej bazy `ddl_rules_`. Porównują jedno zamówienie przesyłki i jedno zdarzenie audytowe z plikami w `bench/load/tests/golden/`. Sprawdzają też odrzucenie niepoprawnego statusu i tworzą indeksy BASE oraz IDX. Na końcu usuwają bazę `ddl_rules_`.

## Ładowanie Neo4j

`make load ENGINE=neo4j SIZE=S` uruchamia Neo4j. Loader korzysta ze sterownika neo4j 6.4.1 i działa tylko w kontenerze `runner`, bo ścieżkę plików importu na hoście odczytuje z montowań tego kontenera. `bench/transform/neo4j/` zapisuje pliki CSV w katalogu `neo4j/` obok plików Parquet. Powstaje 12 etykiet węzłów, a zamówienie przesyłki ma dodatkowo etykietę `Shipment`. Do tego dochodzi 15 typów relacji, w tym `SHIPS_TO`. Znaczniki czasu mają strefę UTC i milisekundy. Kwoty są w groszach, a `codeHmac` jest zapisany szesnastkowo. Pola `actor` i `changes` zdarzeń audytu pozostają tekstem JSON.

Loader zatrzymuje kontener Neo4j i uruchamia `neo4j-admin database import full` w kontenerze pomocniczym. Ten kontener ma ten sam obraz, wolumin danych i limity. Import przerywa się przy pierwszym błędnym wierszu, a loader usuwa wtedy niepełny magazyn bazy `neo4j`. Potem loader uruchamia bazę, usuwa pliki CSV i porównuje liczbę węzłów każdej etykiety oraz relacji każdego typu z danymi kanonicznymi. Na końcu wykonuje `bench/ddl/neo4j/base/constraints.cypher` i `base/indexes.cypher`. Skrypty indeksów kończą się wywołaniem `db.resampleOutdatedIndexes()`, a po nim `db.awaitIndexes(3600)`. Próbkowanie indeksów w tle wyłącza `docker/conf/neo4j/settings.env`.

Funkcja `apply_index` z `bench/load/neo4j/loader.py` wykonuje `bench/ddl/neo4j/idx/indexes.cypher` z IX1–IX4.

## Weryfikacja danych

`make verify SIZE=S` porównuje dane czterech baz z plikami Parquet. Polecenie zatrzymuje bazy pomiarowe i uruchamia je po kolei. Dla każdej bazy `python -m bench.check.verify --size S --engine <baza>` odtwarza 13 tabel kanonicznych. PostgreSQL i MySQL czytają tabele wprost. MongoDB rozwija dokumenty osadzone, a Neo4j czyta węzły i końce relacji. Wartości są normalizowane: czas to milisekundy UTC, kwoty to grosze, godziny to tekst `HH:MM:SS.ffffff`, skrót kodu to hex, punkt to długość i szerokość, a JSON jest parsowany. Skrót tabeli to suma SHA-256 jej wierszy modulo 2^256, więc kolejność wierszy nie ma znaczenia.

Weryfikacja sprawdza też dane pochodne: `lockermatId` nóg, punkty przesyłki i `shipLinks` w MongoDB, `SHIPS_TO` w Neo4j oraz `changes_new_` w MySQL. W Neo4j skopiowane identyfikatory (np. `Order.customerId`) muszą zgadzać się z końcem relacji, a węzeł ma najwyżej jedną taką relację. Każda baza liczy własną funkcją odległość Kraków Główny → Warszawa Centralna. Wynik musi mieścić się w 250–253 km.

Na końcu `python -m bench.check.verify --size S` liczy te same skróty z Parquet i drukuje tabelę 13 × 4. Każda różnica kończy polecenie błędem. Wynik trafia do `results/load/<rozmiar>.json`, a dla XS do `out/xs/results/load/XS.json`. Plik zawiera liczby wierszy, skróty, odległości, czas ładowania i rozmiar bazy na dysku. Czas ładowania zapisuje `make load`. Rozmiar to `pg_database_size` w PostgreSQL, suma plików przestrzeni tabel w MySQL, `totalSize` z `dbStats` w MongoDB i `du` katalogu bazy w Neo4j.
