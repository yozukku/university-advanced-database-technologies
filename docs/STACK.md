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
