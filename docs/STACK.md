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
