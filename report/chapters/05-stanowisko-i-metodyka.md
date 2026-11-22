# Stanowisko i metodyka pomiarów

Rozdział opisuje stanowisko pomiarowe, ustawienia czterech SZBD, sposób mierzenia czasu, kolejność przebiegów, kontrolę zgodności wyników i zasady rysowania wykresów. Wszystkie kroki wykonuje aplikacja testowa (rozdz. 4) w kontenerze `runner`. Parametry stanowiska zapisuje ona na początku każdej sesji pomiarowej w pliku `results/env.json`, a @tab:env powstaje z tego pliku automatycznie.

## Stanowisko pomiarowe

Pomiary wykonujemy na jednym komputerze Apple z procesorem Apple Silicon (architektura arm64). Kontenery działają w maszynie wirtualnej Linuksa OrbStack. W danej chwili działa tylko jeden kontener SZBD z limitem 6 procesorów i 8 GiB pamięci, a obok niego kontener `runner` z limitem 4 procesorów. Oba kontenery łączy ta sama sieć Dockera. Runner odmawia pomiaru, gdy działa druga baza projektu. Na macOS Makefile uruchamia pomiar pod `caffeinate -ims`, więc komputer nie przechodzi w stan uśpienia. Przez cały pomiar istnieje plik blokady `results/.bench-lock`: w tym czasie na komputerze nie budujemy obrazów i nie uruchamiamy testów.

Obrazy SZBD są wskazane przez digest, a obraz PostgreSQL z PostGIS budujemy z `docker/postgres-postgis/Dockerfile`. Wersje serwerów runner odczytuje z działających baz. Kopie migawek danych powstają poleceniem `cp -a --reflink=auto`. Gdy system plików maszyny wirtualnej obsługuje reflink, kopia współdzieli bloki z oryginałem i trwa krótko.

{{ dataset("env", "Stanowisko pomiarowe według results/env.json, kolumna na rozmiar zbioru danych") }}

## Konfiguracja SZBD i równe warunki

Jedynym strojeniem SZBD są ustawienia z katalogu `docker/conf/`, zebrane w @tab:konfiguracja. Zasady są wspólne dla czterech SZBD:

- około połowy pamięci kontenera dostaje główna pamięć podręczna danych;
- zatwierdzenie transakcji jest w pełni trwałe: czeka na zapis dziennika na dysk;
- PostgreSQL i MySQL działają na poziomie izolacji READ COMMITTED, a MongoDB i Neo4j na swoich ustawieniach domyślnych;
- żaden SZBD nie wczytuje pamięci podręcznej z poprzedniego uruchomienia;
- statystyki optymalizatora są zamrożone, więc plan zapytania nie zmienia się między przebiegami.

| Ustawienie | PostgreSQL 17 | MySQL 8.4 | MongoDB 8.0 | Neo4j 5.26 |
|------|-------|-------|-------|-------|
| Pamięć podręczna danych | shared_buffers = 2GB i pamięć podręczna systemu | innodb-buffer-pool-size=5G | WiredTiger cacheSizeGB: 4 | sterta 2 GB, pamięć podręczna stron 4 GB |
| Trwałość zatwierdzenia | synchronous_commit = on | innodb-flush-log-at-trx-commit=1, dziennik binarny wyłączony | zapis w: 1, j: true, oplogSizeMB: 1024 | domyślna |
| Dziennik i punkty kontrolne | max_wal_size = 4GB, checkpoint_timeout = 15min | innodb-redo-log-capacity=4G | domyślne | domyślne |
| Poziom izolacji | READ COMMITTED | READ COMMITTED | domyślny | domyślny |
| Wczytanie pamięci podręcznej | autoprewarm z pg_prewarm wyłączony | zrzut i wczytanie puli buforów wyłączone | — | — |
| Statystyki | autovacuum = off | innodb-stats-auto-recalc=OFF | — | próbkowanie indeksów w tle wyłączone |
| Limit czasu transakcji | — | — | 600 s | — |

: Ustawienia SZBD z katalogu docker/conf/ {#tab:konfiguracja}

Statystyki ustalamy raz, przed zapisem migawki BASE. PostgreSQL wykonuje `VACUUM (FREEZE, ANALYZE)`, MySQL `ANALYZE TABLE` na 13 tabelach, a Neo4j `db.resampleOutdatedIndexes()` i czeka na indeksy. Migawka IDX zachowuje statystyki BASE i analizuje tylko to, czego potrzebują nowe indeksy. PostgreSQL analizuje `audit_event_` (statystyki wyrażeń JX1). MySQL również analizuje `audit_event_`: w MySQL 8.4 utworzenie indeksu funkcyjnego JX1 lub JX2 usuwa trwałe statystyki tej tabeli, a przy wyłączonym automatycznym przeliczaniu nikt by ich nie odtworzył. Utworzenie zwykłego indeksu B-drzewa IX1–IX4 w MySQL przelicza na nowo trwałe statystyki całej tabeli. W MySQL tabele `shipment_`, `order_`, `payment_` i `cell_opening_` mają więc w IDX nową próbkę statystyk, a nie statystyki BASE. Jest to własność MySQL, którą uwzględniamy przy analizie planów (rozdz. 8).

Dane każdego rozmiaru ładujemy raz i zapisujemy jako migawki BASE i IDX (rozdz. 3). Czyste zatrzymanie bazy stosujemy tylko przed zapisem migawki. Po przebiegu zapisu dane są odrzucane, więc runner zatrzymuje bazę poleceniem `docker kill` i odtwarza migawkę na jej woluminie. Każdy przebieg zapisu zaczyna się więc od tych samych danych, bez narosłych martwych wierszy.

## Pomiar czasu

Czas mierzy klient funkcją `time.perf_counter_ns()`, od pierwszego polecenia partii do pobrania ostatniego wiersza i potwierdzenia zatwierdzenia. Połączenia z bazą runner otwiera przed pomiarem, a polecenia mają parametry.

Jeden przebieg mierzony obejmuje całą pracę scenariusza: wszystkie zestawy parametrów odczytu (np. 1000 zamówień w R1) albo wszystkie partie zapisu. Czas przebiegu jest więc dużo większy od dokładności zegara. Liczby operacji i rozmiary partii są stałe dla rozmiarów S, M i L i pochodzą z `bench/scenarios/ops.yaml` (rozdz. 6):

- zapisy punktowe w partiach (C1, C2, C5, D1, J1, U1, U5) wykonują jedną transakcję na partię we wszystkich SZBD, w MongoDB jako transakcję wielodokumentową;
- zapisy zbiorowe (C6, U3, U4, U6, D3, D4, D5, D6, J5, J6) mają jedną jednostkę atomową we wszystkich SZBD: deterministyczne partie do 5000 kluczy głównych celu, jedno zatwierdzenie na partię;
- wyszukanie celów zapisu odbywa się wewnątrz mierzonego czasu we wszystkich SZBD.

Runner zapisuje dla każdego przebiegu zapisu liczbę zatwierdzeń transakcji, więc jednostkę pracy scenariusza można porównać między SZBD.

## Przebiegi

Dla każdego SZBD, rozmiaru i konfiguracji runner wykonuje kroki w tej kolejności:

- odtwarza migawkę, sprawdza jej `state_id`, uruchamia bazę i ją rozgrzewa;
- każdy odczyt wykonuje raz bez zapisu wyniku, a potem trzy razy z pomiarem, zawsze z tymi samymi parametrami;
- po odczytach bez pomiaru porównuje liczby wierszy 13 tabel z manifestem migawki;
- każdy przebieg zapisu zaczyna od odtworzenia migawki i uruchomienia bazy. Przed rozgrzewką uruchamia sondę kluczy, czyli wyszukanie celów zapisu, i odczytuje ich stan. Na XS i S robi to w każdym przebiegu, a na M i L w pierwszym. Potem rozgrzewa bazę, wykonuje zapis z pomiarem i bez pomiaru sprawdza jego skutki. Na końcu zatrzymuje bazę poleceniem `docker kill`;
- zapisuje czas, liczbę zwróconych lub zmienionych wierszy, liczbę zatwierdzeń, skrót wyniku i status przebiegu: `ok`, `timeout`, `skipped` albo `error`.

Scenariusze mierzone w BASE i IDX runner mierzy parami: dla każdego najpierw BASE, zaraz potem IDX. Pozostałe scenariusze mierzy na końcu, w IDX.

W Neo4j każdy przebieg zapisu trafia na świeżo uruchomioną JVM, więc zmierzony czas obejmuje pierwszą kompilację zapytań Cypher i kod jeszcze nieskompilowany przez JIT.

Na XS i S po każdym przebiegu zapisu liczby wierszy 13 tabel muszą równać się manifestowi migawki powiększonemu o wstawione i pomniejszonemu o usunięte wiersze. Na M i L ta kontrola odbywa się raz na sesję, po odczytach.

Dla zapisów runner zapisuje też przyrost licznika odczytów z dysku: `blks_read` w PostgreSQL, `Innodb_buffer_pool_reads` w MySQL, „bytes read into cache” WiredTiger w MongoDB. Neo4j Community nie udostępnia licznika braków w pamięci stron, więc runner zapisuje `rchar` procesu JVM. Licznik służy tylko do wyjaśniania nietypowych wyników i nie decyduje o poprawności przebiegu.

### Rozgrzewka

Rozgrzewka to jeden skrypt na SZBD (`bench/runner/warmup.py`), wspólny dla BASE i IDX. Tabele, kolekcje, etykiety i typy relacji bierze z tekstów zapytań scenariusza, a przed odczytami z tekstów wszystkich odczytów konfiguracji. Indeksy bierze z katalogu działającej bazy, więc w IDX obejmuje też indeksy IDX. @Tab:rozgrzewka opisuje skrypt każdego SZBD.

| SZBD | Rozgrzewka |
|---|---|
| PostgreSQL | `pg_prewarm(…, 'buffer')` dla tabeli i każdego jej indeksu |
| MySQL | `count(*)` z `force index` dla każdego indeksu B-drzewa, także `PRIMARY`; JX2 przez `json_overlaps` w partiach po 1000 wartości z danych kanonicznych |
| MongoDB | skan `$natural` każdej kolekcji, który pobiera każdy dokument, i liczenie z podpowiedzią każdego indeksu; indeks częściowy z jego filtrem, 2dsphere przez `$geoWithin` w prostokącie Polski |
| Neo4j | odczyt właściwości każdej etykiety i typu relacji oraz `PROFILE` skanu każdego indeksu z `USING RANGE INDEX` albo `USING POINT INDEX`; plan musi pokazać operator na tym indeksie, a nie skan etykiety ani typu |

: Skrypt rozgrzewki każdego SZBD {#tab:rozgrzewka}

W MySQL indeksów SPATIAL (`lockermat_location_geog__idx`) i FULLTEXT (`lockermat_address_trgm__idx`) nie da się przejrzeć, więc rozgrzewka ich nie obejmuje. Żaden scenariusz mierzony w BASE i IDX nie zapisuje tabeli `lockermat_`. Rozgrzewka ma limit czasu, który chroni przed zawieszeniem przebiegu. Ustalamy go z pomiaru rozgrzewki całego zestawu odczytów przy rozmiarze L. Rozgrzewka, która przekroczy limit, kończy przebieg statusem `error`.

## Wartość raportowana i limit czasu

Wynikiem komórki (SZBD, rozmiar, konfiguracja, scenariusz) jest średnia z trzech przebiegów mierzonych. Minimum, maksimum, medianę i współczynnik zmienności CV podaje dodatek A. CV powyżej 15% to ostrzeżenie w `results/qa.json`. Runner nie powtarza automatycznie takiej komórki. Ponowny pomiar komórki wymaga polecenia `make forget`, które usuwa jej przebiegi z `results/runs.jsonl` i zapisuje powód w `results/notes.md`. Pełna komórka ma więc zawsze dokładnie trzy przebiegi `ok`.

Limit przebiegu wynosi 600 s. Runner ustawia go tylko w swoich sesjach: `statement_timeout` w PostgreSQL, `max_execution_time` w MySQL, `maxTimeMS` w MongoDB i limit transakcji sterownika w Neo4j. Serwer MongoDB ma też własny limit transakcji `transactionLifetimeLimitSeconds`, równy 600 s (@tab:konfiguracja). Niezależnie od tego zegar runnera po 600 s przerywa polecenia przebiegu w bazie i sprawdza, że żadne nie działa dalej. Po pierwszym przekroczeniu limitu pozostałe przebiegi komórki dostają status `skipped`, a komórka pokazuje „> 600 s” zamiast liczby. Przekroczenie limitu w IDX przerywa pomiary: liczbę operacji lub próg daty scenariusza zmniejszamy wtedy we wszystkich SZBD i rozmiarach. Przekroczenie limitu w BASE daje komórkę ocenzurowaną bez średniej (rozdz. 11).

Wyniki trafiają do `results/runs.jsonl`, jedna linia na przebieg. Kluczem przebiegu jest SZBD, rozmiar, konfiguracja, scenariusz, numer przebiegu, `qhash` i `state_id`. `qhash` to skrót scenariusza: tekstów zapytań, parametrów, ziarna, polityki pomiaru i wersji sterowników. `state_id` to skrót danych, skryptów DDL, transformacji, ładowania, ustawień i obrazu SZBD. Każda zmiana zapytania, danych lub ustawień zmienia jeden z tych skrótów, więc dotknięte komórki są mierzone ponownie, a stare linie są pomijane. Przerwany pomiar po ponownym uruchomieniu mierzy tylko brakujące przebiegi.

## Zgodność wyników

Każdy scenariusz ma normalizację wyniku (typy, kolejność wierszy, kwoty w groszach, czas w milisekundach UTC, sparsowany JSON) i skrót SHA-256 wyniku. Odczyt musi dać ten sam skrót we wszystkich SZBD, które go wykonują, oraz w BASE i IDX. Na XS i S każdy zestaw parametrów musi zwrócić co najmniej jeden wiersz. W R3 odległości porównujemy poza skrótem z tolerancją 1%, bo SZBD liczą je na sferze albo na elipsoidzie.

Zapis porównujemy po kluczach logicznych. Sonda kluczy przed przebiegiem i sonda po przebiegu dają dla każdej tabeli liczbę wstawionych, zmienionych i usuniętych wierszy oraz skrót ich kluczy i starych i nowych wartości. Te liczby i skróty muszą być równe we wszystkich SZBD. Na XS i S dodatkowo odbudowujemy 13 tabel kanonicznych przed przebiegiem i po nim. Różnica musi być równa we wszystkich SZBD i równa różnicy z sond. Niezgodność kończy przebieg błędem. Kontrolę wszystkich komórek po pomiarach wykonuje `make qa`.

## Plany zapytań

Plany zapisujemy w osobnym kroku po pomiarach, bez pomiaru czasu, na świeżo odtworzonej bazie. Krok obejmuje rozmiary XS (tylko testy), S i L. Rozmiar M daje tylko czasy. W IDX zapisujemy plan każdego odczytu, a w BASE każdego odczytu mierzonego w obu konfiguracjach. Plan dotyczy pierwszego zestawu parametrów i jest planem wykonanym (@tab:plany).

| SZBD | Plan |
|---|---|
| PostgreSQL | `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` i ten sam plan tekstowo |
| MySQL | `EXPLAIN FORMAT=JSON` i drzewo `EXPLAIN ANALYZE` |
| MongoDB | `explain` z `executionStats` |
| Neo4j | `PROFILE`: drzewo operatorów z liczbą wierszy i `dbHits` |

: Sposób zapisu planu zapytania w każdym SZBD {#tab:plany}

Plik `results/explain_summary.csv` zbiera z planów ścieżkę dostępu (skan tabeli albo indeks), użyty indeks oraz liczbę wierszy przejrzanych i zwróconych. Na nim opiera się kontrola planów hipotezy H1 (rozdz. 11) i analiza planów w rozdz. 8.

## Wykresy

Wykresy rysuje aplikacja testowa (biblioteka matplotlib, PNG 300 dpi) z `results/runs.jsonl`. Na wykres trafia tylko pełna komórka bieżącej wersji: trzy przebiegi `ok`. Zasady są wspólne dla wszystkich wykresów:

- każdy SZBD ma stały kolor: PostgreSQL niebieski, MySQL pomarańczowy, MongoDB zielony, Neo4j bursztynowy; sąsiednie słupki są rozróżnialne także przy zaburzeniach widzenia barw;
- oś wartości ma jednostkę: [ms], a [s], gdy najdłuższy przebieg na wykresie trwa co najmniej 1000 ms;
- liczby mają przecinek dziesiętny i spację tysięcy;
- wykres scenariusza pokazuje konfigurację IDX: grupy słupków według rozmiaru, słupek na SZBD i wąsy min–max;
- wykres pary BASE / IDX ma panel na SZBD z parą słupków dla każdego rozmiaru i ilorazem IDX / BASE nad parą. Takie wykresy są tylko w rozdz. 8, 9 i 11, a pozostałe wykresy i tabele porównawcze pokazują IDX.
- mapa cieplna (rozdz. 7) ma wiersz na scenariusz podstawowy i kolumnę na SZBD; komórka to średni czas w IDX podzielony przez czas najszybszego SZBD w scenariuszu, a kolor jednego odcienia ciemnieje na skali logarytmicznej.

Zasada osi logarytmicznej: wykres scenariusza ma oś logarytmiczną, gdy największa średnia jest co najmniej 50 razy większa od najmniejszej. Wykres pary BASE / IDX ma zawsze oś logarytmiczną. Oś logarytmiczna ma dopisek „skala logarytmiczna”, a podpis takiego wykresu w sprawozdaniu zawiera te same słowa.
