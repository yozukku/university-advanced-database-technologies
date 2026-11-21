# Aplikacja testowa i aplikacja Bagażomat

Projekt ma dwie aplikacje. Aplikacja testowa (harness, katalog `bench/`) generuje dane, ładuje je do czterech SZBD, mierzy scenariusze i buduje wyniki. Aplikacja Bagażomat (katalog `app/`) to aplikacja internetowa przypadku biznesowego. Działa tylko na PostgreSQL i pokazuje, jak schemat z rozdz. 3 obsługuje rzeczywiste operacje klienta, w tym historię zamówienia z `audit_event_`.

## Wymagania funkcjonalne

### Aplikacja testowa (harness)

- Generowanie danych: deterministyczny zbiór 13 tabel w rozmiarach XS, S, M i L z jednego profilu i ziarna (rozdz. 3).
- Kontrola danych przed ładowaniem: liczby wierszy, reguły schematu, warunki wstępne scenariuszy i skróty plików.
- Ładowanie czterech SZBD: te same dane w PostgreSQL, MySQL, MongoDB i Neo4j, każdy w swoim modelu danych, oraz zapis migawek konfiguracji BASE i IDX.
- Kontrola równoważności: dane odtworzone z każdej bazy mają te same skróty 13 tabel co dane kanoniczne, odczyty zwracają w czterech bazach ten sam wynik, a zapisy zmieniają te same wiersze w ten sam sposób.
- Wykonanie scenariuszy: 26 scenariuszy CRUD w czterech SZBD i 6 scenariuszy JSON w trzech SZBD, w konfiguracji IDX, a scenariusze z porównaniem indeksów także w BASE. Każdy odczyt ma jeden przebieg odrzucany i trzy mierzone (1 + 3). Każdy z trzech mierzonych przebiegów zapisu zaczyna się od danych odtworzonych z migawki.
- Plany zapytań: zapis planu wykonania odczytów (EXPLAIN w PostgreSQL i MySQL, `explain` w MongoDB, PROFILE w Neo4j) w konfiguracji IDX, a odczytów z porównaniem indeksów także w BASE.
- Generowanie wykresów i sprawozdania: kontrola komórek pomiarów, ocena hipotezy H1, wykresy, a na końcu sprawozdanie DOCX i PDF oraz prezentacja PPTX.

### Aplikacja Bagażomat

- Logowanie przez Keycloak. Konta demonstracyjne to `anna` i `jan`.
- Wyszukiwanie automatu na liście i na mapie: fraza, rozmiar skrytki (S, M, L) i okno czasu („+ 4 h”, „+ 1 dzień”, „+ 3 dni”). Każdy automat pokazuje cenę i liczbę wolnych skrytek wybranego rozmiaru.
- Rezerwacja wolnej skrytki wybranego rozmiaru w wybranym oknie.
- Symulowana płatność najwyżej 15 minut po rezerwacji. Po płatności klient widzi numer skrytki i PIN.
- „Moje rezerwacje” z zakładkami „Aktywne”, „Do odbioru” i „Zakończone” oraz szczegóły rezerwacji z aktualnym PIN-em.
- Anulowanie opłaconej rezerwacji z pełnym zwrotem, dopóki bagaż nie trafi do skrytki.
- „Otwórz skrytkę”: zdalne otwarcie skrytki, aby zostawić bagaż, odebrać bagaż albo odebrać przesyłkę. Każde otwarcie trafia do dziennika otwarć `cell_opening_`.
- „Symuluj przesyłkę”: przycisk deweloperski, który tworzy przesyłkę do zalogowanego klienta. Odbiorcą jest klient, którego numer telefonu jest numerem odbiorcy przesyłki. Przesyłka pojawia się w zakładce „Do odbioru”.
- „Historia zamówienia”: lista zdarzeń zamówienia, jego rezerwacji i płatności z `audit_event_`.
- Automatyczne wygaśnięcie nieopłaconego zamówienia po terminie płatności.

## Wymagania niefunkcjonalne

### Aplikacja testowa (harness)

- Powtarzalność: ten sam profil daje te same dane i te same parametry scenariuszy. Każdy scenariusz bierze „teraz” z parametru T0, a nie z zegara.
- Jednakowe warunki: w czasie pomiaru działa tylko jedna baza. Każda baza ma te same limity kontenera (6 CPU, 8 GB pamięci), a obrazy mają ustalony digest.
- Limit czasu: przebieg trwa najwyżej 600 s. Po przekroczeniu harness przerywa polecenie w bazie i zapisuje status `timeout`.
- Wznawianie: wynik każdego przebiegu trafia od razu do `results/runs.jsonl`. Przerwany pomiar po ponownym uruchomieniu mierzy tylko brakujące przebiegi.
- Przenośność: host potrzebuje tylko Dockera i make. Generator, bazy, pomiary i budowanie dokumentów działają w kontenerach.

### Aplikacja Bagażomat

- Interfejs tylko po polsku: ceny w złotych, daty i godziny w strefie Europe/Warsaw.
- Układ dla telefonu i komputera. Od szerokości 960 px lista i mapa są obok siebie, a na węższym ekranie przełącznik „Lista / Mapa” pokazuje jeden z widoków.
- Bezpieczeństwo: backend przyjmuje tylko token Keycloak, którego użytkownik jest klientem w `customer_`. Klient widzi tylko swoje zamówienia i przesyłki do siebie. Baza nie przechowuje PIN-u, tylko jego skrót HMAC-SHA256 z tajnym kluczem. Komunikat błędu nie zawiera tekstu SQL.
- Spójność: reguły rezerwacji pilnuje PostgreSQL (rozdz. 3). Po naruszeniu wykluczenia operacja zaczyna się od nowa w nowej transakcji, najwyżej trzy razy. Zdarzenie `audit_event_` powstaje w tej samej transakcji co zmiana.
- Schemat bazy tworzy Flyway z pliku `docs/design/schema.sql`, a Hibernate tylko sprawdza mapowanie encji (`ddl-auto: validate`).

## Technologie i narzędzia

Aplikacja testowa działa w Pythonie 3.13, a zależności instaluje uv 0.13.8. Testowane SZBD to PostgreSQL 17 z PostGIS 3.6.4, MySQL 8.4, MongoDB 8.0 i Neo4j 5.26 Community. Backend Bagażomatu korzysta z Javy 21, Spring Boot 4.1.3, Maven 3.10.1, Spring Data JPA z Hibernate i Flyway. Frontend korzysta z Node.js 22, Vite, React, TypeScript, React Router, TanStack Query i MapLibre GL z mapą OpenFreeMap. Logowanie obsługuje Keycloak 26.4. Sprawozdanie buduje Pandoc 3.1.11 z LibreOffice 25.2, a prezentację python-pptx.

@Tab:biblioteki zestawia wszystkie bezpośrednie zależności z plików `pyproject.toml`, `app/backend/pom.xml`, `app/frontend/package.json` i `e2e/package.json`. Wersje Pythona pochodzą z `uv.lock`, a wersje npm z `package-lock.json`. Maven nie ma pliku blokady: wersje zależności bez numeru w `pom.xml` ustala Spring Boot 4.1.3 (`spring-boot-starter-parent`), a tabela podaje wersje rozwiązane przez Maven.

| Plik | Biblioteka | Wersja | Zastosowanie |
|---|---|---|---|
| `pyproject.toml` | docker | 7.1.0 | Sterowanie kontenerami baz i migawkami |
| `pyproject.toml` | duckdb | 2.0.1 | Kontrola i przekształcanie plików Parquet |
| `pyproject.toml` | Faker | 40.54.0 | Dane osobowe i adresy (`pl_PL`) |
| `pyproject.toml` | mysql-connector-python | 26.10.0 | Sterownik MySQL |
| `pyproject.toml` | neo4j | 6.4.1 | Sterownik Neo4j |
| `pyproject.toml` | numpy | 2.5.5 | Losowanie wierszy |
| `pyproject.toml` | psycopg\[binary\] | 3.3.9 | Sterownik PostgreSQL |
| `pyproject.toml` | pyarrow | 26.0.1 | Zapis i odczyt Parquet |
| `pyproject.toml` | pymongo | 4.19.0 | Sterownik MongoDB |
| `pyproject.toml` | pytest | 9.2.0 | Testy |
| `pyproject.toml` | PyYAML | 6.0.3 | Profile, scenariusze i mapa indeksów |
| `pyproject.toml` (grupa `report`) | matplotlib | 3.11.2 | Wykresy |
| `pyproject.toml` (grupa `report`) | python-pptx | 1.0.2 | Prezentacja PPTX |
| `pom.xml` | spring-boot-starter-data-jpa | 4.1.3 | Spring Data JPA i Hibernate |
| `pom.xml` | spring-boot-starter-flyway | 4.1.3 | Migracje schematu |
| `pom.xml` | spring-boot-starter-security-oauth2-resource-server | 4.1.3 | Weryfikacja tokenów JWT |
| `pom.xml` | spring-boot-starter-webmvc | 4.1.3 | REST API |
| `pom.xml` | flyway-database-postgresql | 12.4.0 | Flyway dla PostgreSQL |
| `pom.xml` | postgresql | 42.7.14 | Sterownik JDBC |
| `pom.xml` (test) | spring-boot-starter-webmvc-test | 4.1.3 | Testy API |
| `pom.xml` (test) | spring-boot-starter-security-oauth2-resource-server-test | 4.1.3 | Tokeny w testach |
| `pom.xml` (test) | spring-boot-testcontainers | 4.1.3 | Baza w kontenerze w testach |
| `pom.xml` (test) | testcontainers-junit-jupiter | 2.0.5 | Testcontainers z JUnit |
| `pom.xml` (test) | testcontainers-postgresql | 2.0.5 | Kontener PostgreSQL w testach |
| `package.json` | @tanstack/react-query | 5.107.1 | Zapytania do API i pamięć podręczna |
| `package.json` | maplibre-gl | 6.16.0 | Mapa automatów |
| `package.json` | oidc-client-ts | 3.5.0 | Klient OpenID Connect |
| `package.json` | react | 19.3.1 | Interfejs |
| `package.json` | react-dom | 19.3.1 | Interfejs w przeglądarce |
| `package.json` | react-oidc-context | 3.3.1 | Logowanie w React |
| `package.json` | react-router | 8.5.1 | Trasy |
| `package.json` (dev) | @types/node | 22.20.5 | Typy Node.js |
| `package.json` (dev) | @types/react | 19.3.0 | Typy React |
| `package.json` (dev) | @types/react-dom | 19.3.0 | Typy React DOM |
| `package.json` (dev) | @vitejs/plugin-react | 6.3.0 | React w Vite |
| `package.json` (dev) | typescript | 6.0.3 | Kompilator TypeScript |
| `package.json` (dev) | vite | 8.3.8 | Serwer deweloperski i budowanie |
| `e2e/package.json` (dev) | @playwright/test | 1.65.1 | Testy end-to-end i zrzuty ekranów |

: Bezpośrednie zależności z rozwiązanymi wersjami {#tab:biblioteki}

## Docker i Docker Compose

Wszystkie usługi działają w Dockerze na hoście ARM64. Dwa pliki Compose dzielą projekt na część pomiarową i aplikację.

`compose.bench.yaml` ma usługi `pg`, `mysql`, `mongo` i `neo4j`. Każda baza ma własny profil Compose, własny wolumin danych, konfigurację z `docker/conf/` i limit 6 CPU oraz 8 GB pamięci. Obrazy MySQL, MongoDB i Neo4j mają ustalony digest. PostgreSQL ma własny obraz `docker/postgres-postgis/`: `postgres:17` z ustalonym digestem i pakietem PostGIS w ustalonej wersji. MongoDB działa jako jednowęzłowy zbiór replik, bo transakcje go wymagają. Usługa `runner` uruchamia aplikację testową. Widzi gniazdo Dockera, więc sama zatrzymuje, uruchamia i odtwarza bazy. Migawkę BASE lub IDX zapisuje kopia zatrzymanego woluminu (`cp -a --reflink=auto`) w kontenerze pomocniczym. Usługa `report` ma Pandoc i LibreOffice i buduje wykresy, sprawozdanie i prezentację.

`compose.app.yaml` uruchamia Bagażomat poleceniem `make app-up`: `postgres` (ten sam obraz z PostGIS), `keycloak` (import realmu `bagazomat`, własny wolumin), `backend` (Spring Boot) i `frontend` (Vite). Każda usługa ma healthcheck, a `depends_on` uruchamia backend dopiero po bazie i Keycloak, a frontend po backendzie. Porty są dostępne tylko na `localhost`: aplikacja na 5173, API na 8080, Keycloak na 8081.

## Opis działania

### Aplikacja testowa (harness)

Każdy krok to jedno polecenie `make`, które uruchamia moduł Pythona w kontenerze `runner` albo `report`:

1. `make data SIZE=S` tworzy pliki Parquet, a `make validate SIZE=S` sprawdza je w DuckDB.
2. `make load SIZE=S` ładuje dane do czterech baz po kolei, a `make verify SIZE=S` porównuje skróty 13 tabel z danymi kanonicznymi i zapisuje `results/load/S.json`.
3. `make snapshots SIZE=S` zapisuje migawkę BASE, dodaje indeksy IDX i zapisuje migawkę IDX każdej bazy.
4. `make bench SIZE=S` mierzy brakujące przebiegi. Przed odczytami i przed każdym zapisem odtwarza migawkę i rozgrzewa bazę. Każdy przebieg dopisuje wiersz do `results/runs.jsonl`.
5. `make explain SIZE=S` zapisuje plany zapytań w `results/explain/`.
6. `make qa SIZE=S` sprawdza komplet przebiegów i równość wyników między bazami, a `make h1` ocenia hipotezę H1.
7. `make charts` rysuje wykresy, a `make report` buduje sprawozdanie i prezentację.

Scenariusz to moduł Pythona z jednym zapytaniem na bazę i wspólnym selektorem parametrów. Selektor wybiera parametry z plików Parquet, więc wszystkie bazy dostają te same parametry. Rozdział 10 opisuje uruchomienie całego procesu jednym poleceniem.

### Aplikacja Bagażomat

Po zalogowaniu klient widzi automaty (@fig:app-punkty). Wpisuje frazę, wybiera rozmiar i okno, a lista i mapa pokazują te same automaty z ceną i liczbą wolnych skrytek. Na telefonie przełącznik pokazuje listę albo mapę (@fig:app-telefon). Przycisk „Zarezerwuj” w jednej transakcji tworzy zamówienie, wybiera wolną skrytkę i zapisuje zdarzenie `CREATED`.

![Widok „Punkty”: lista i mapa automatów](report/assets/app/punkty.png){#fig:app-punkty}

![Widok „Punkty” na telefonie](report/assets/app/punkty-telefon.png){#fig:app-telefon width=6cm}

Płatność jest symulowana. Po płatności zamówienie ma status PAID, rezerwacja dostaje kody zostawienia i odbioru, a ekran pokazuje numer skrytki i PIN (@fig:app-platnosc). PIN backend wylicza za każdym razem z id kodu i tajnego klucza.

![Ekran po płatności: numer skrytki i PIN](report/assets/app/platnosc.png){#fig:app-platnosc}

„Moje rezerwacje” dzielą zamówienia na zakładki (@fig:app-rezerwacje). Szczegóły rezerwacji mają przycisk „Otwórz skrytkę”. Backend zapisuje polecenie otwarcia w `cell_opening_` ze stanem PENDING, wysyła je do symulowanych drzwiczek i w drugiej transakcji zapisuje wynik. Po otwarciu rezerwacja zmienia status, a historia zamówienia pokazuje kolejne zdarzenia z `audit_event_` (@fig:app-historia).

![„Moje rezerwacje”: zakładka „Aktywne”](report/assets/app/rezerwacje.png){#fig:app-rezerwacje}

![Szczegóły zakończonej rezerwacji z historią zamówienia](report/assets/app/historia.png){#fig:app-historia}

Przycisk „Symuluj przesyłkę” w zakładce „Do odbioru” tworzy opłaconą przesyłkę do zalogowanego klienta, której bagaż czeka już w automacie docelowym. Odbiorca otwiera skrytkę z ekranu przesyłki (@fig:app-przesylka), a zdarzenie odbioru ma wykonawcę `RECIPIENT`.

![Przesyłka do odbioru](report/assets/app/przesylka.png){#fig:app-przesylka}
