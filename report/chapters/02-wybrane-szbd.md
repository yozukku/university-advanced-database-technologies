# Wybrane systemy zarządzania bazami danych

Projekt porównuje dwa relacyjne i dwa nierelacyjne SZBD. Każdy z nich opisujemy według tej samej siatki jedenastu punktów: najpierw relacyjne PostgreSQL 17 i MySQL 8.4 LTS, potem dokumentowy MongoDB 8.0 i grafowy Neo4j 5.26 Community. Rozdział zamyka tabela porównawcza. Opisy opierają się na dokumentacji i stronach producentów, sprawdzonych 20 listopada 2026 r.

## PostgreSQL 17

### Opis

PostgreSQL to obiektowo-relacyjny SZBD. Wywodzi się z projektu POSTGRES Uniwersytetu Kalifornijskiego w Berkeley, którego implementację rozpoczęto w 1986 r.[^pg-history] Rozwija go społeczność PostgreSQL Global Development Group na licencji podobnej do BSD i MIT, która pozwala bezpłatnie używać go w dowolnym celu, także komercyjnym[^pg-licence][^pg-whatis]. Nowa wersja główna ukazuje się mniej więcej raz w roku i ma 5 lat wsparcia. Wersja 17 ukazała się 26 września 2024 r., a jej wsparcie kończy się 8 listopada 2029 r.[^pg-versioning] PostgreSQL spełnia co najmniej 170 ze 177 obowiązkowych cech rdzenia standardu SQL:2023[^pg-sql]. Domyślny poziom izolacji to READ COMMITTED[^pg-iso].

### Zalety

Współbieżność opiera się na wielowersyjności (MVCC). Odczyt nie blokuje zapisu, a zapis nie blokuje odczytu, także na poziomie SERIALIZABLE[^pg-mvcc]. Oprócz kluczy, UNIQUE i CHECK baza ma ograniczenia wykluczające (EXCLUDE). Razem z typami zakresowymi wyrażają one regułę „przedziały tego samego obiektu się nie nakładają”[^pg-constraints][^pg-range]. Schemat Bagażomatu ma pięć takich reguł, m.in. zakaz podwójnej rezerwacji skrytki (rozdz. 3). Wbudowanych typów indeksów jest sześć: B-tree, Hash, GiST, SP-GiST, GIN i BRIN[^pg-idx]. Indeks częściowy obejmuje tylko wiersze spełniające predykat[^pg-partial]. Użytkownik może dodawać własne typy danych, funkcje, operatory i metody indeksowania[^pg-whatis].

### Wady

MVCC ma swój koszt. UPDATE i DELETE nie usuwają od razu starej wersji wiersza, więc miejsce odzyskuje dopiero VACUUM. Zwykle uruchamia go demon autovacuum, którego parametry czasem trzeba dostroić do obciążenia[^pg-vacuum]. Każde połączenie klienta obsługuje osobny proces serwera, tworzony przez proces nadzorczy postmaster[^pg-connect]. Format katalogu danych zmienia się między wersjami głównymi, więc aktualizacja wymaga zrzutu i odtworzenia albo narzędzia pg_upgrade[^pg-versioning].

### Udogodnienia

Rozszerzenie łączy typy, funkcje i operatory w jeden pakiet. Instaluje się je poleceniem CREATE EXTENSION, usuwa jednym DROP EXTENSION, a pg_dump zapisuje w zrzucie tylko polecenie CREATE EXTENSION[^pg-ext]. Schemat Bagażomatu korzysta z rozszerzeń PostGIS, btree_gist i pg_trgm (rozdz. 3). PostGIS dodaje przechowywanie, indeksowanie i analizę danych przestrzennych[^postgis]. Typ jsonb zapisuje JSON w postaci binarnej: wstawianie jest nieco wolniejsze, ale przetwarzanie szybsze, a kolumnę można indeksować[^pg-json]. Wersja 17 dodała JSON_TABLE, kopie przyrostowe w pg_basebackup oraz opcje SERIALIZE i MEMORY polecenia EXPLAIN[^pg-17].

### Ograniczenia

Twarde limity są wysokie: tabela do 32 TB przy domyślnym bloku 8 kB, do 1600 kolumn, pole do 1 GB, identyfikator do 63 bajtów, indeks do 32 kolumn[^pg-limits]. PostgreSQL nie oferuje synchronicznej replikacji z wieloma serwerami przyjmującymi zapisy[^pg-repl]. Serwer zapasowy w trybie hot standby przyjmuje wyłącznie odczyty i nie pozwala nawet na tabele tymczasowe[^pg-hot]. Sumy kontrolne stron danych są domyślnie wyłączone[^pg-checksums].

### Awaryjność

Podstawą jest dziennik zapisu z wyprzedzeniem (WAL). Zmiana trafia do plików danych dopiero po utrwaleniu opisującego ją rekordu WAL, więc po awarii baza odtwarza brakujące zmiany z dziennika[^pg-wal]. Kopia bazowa z archiwum WAL pozwala odtworzyć stan z dowolnej chwili po wykonaniu kopii (PITR)[^pg-pitr]. Replikacja może być asynchroniczna lub synchroniczna. W trybie synchronicznym przełączenie na serwer zapasowy nie traci zatwierdzonych transakcji[^pg-ha]. PostgreSQL nie zawiera jednak oprogramowania, które wykrywa awarię serwera głównego i powiadamia serwer zapasowy[^pg-failover]. Sumy kontrolne stron włącza się w initdb albo później, przy zatrzymanym serwerze[^pg-checksums].

### Bezpieczeństwo

Dostępem zarządzają role. Rola może być użytkownikiem, grupą albo jednym i drugim, jest właścicielem obiektów i nadaje do nich uprawnienia innym rolom[^pg-roles]. Polityki bezpieczeństwa wierszy (RLS) ograniczają, które wiersze dany użytkownik odczyta lub zmieni[^pg-rls]. Serwer uwierzytelnia m.in. hasłem, przez GSSAPI (Kerberos, Active Directory), LDAP, RADIUS i certyfikaty[^pg-auth]. Hasła przechowuje jako skróty, preferując SCRAM. Połączenia szyfruje TLS, a plik pg_hba.conf może wymusić szyfrowanie dla wybranych hostów[^pg-enc]. Moduł pgcrypto szyfruje wybrane kolumny. Do szyfrowania danych w spoczynku dokumentacja wskazuje szyfrowanie systemu plików lub urządzenia blokowego[^pg-enc].

### Migracje

pg_dump tworzy logiczny, spójny zrzut i nie blokuje przy tym zwykłych operacji. Zrzut można wczytać do nowszej wersji i na serwer o innej architekturze[^pg-dump]. pg_upgrade przenosi pliki danych do nowej wersji głównej bez zrzutu, a z opcją --link lub --clone prawie bez kopiowania[^pg-upgrade]. Replikacja logiczna działa między wersjami głównymi, więc serwer można zaktualizować przez przełączenie na zsynchronizowaną kopię[^pg-upgrading]. Przy aktualizacji z wersji 17 nie trzeba już usuwać slotów replikacji logicznej[^pg-17]. DDL jest transakcyjny, więc nieudaną migrację schematu, nawet z CREATE TABLE, można wycofać[^pg-ddl]. COPY przenosi dane między tabelami a plikami[^pg-copy].

### Integracje

Dystrybucja zawiera biblioteki libpq (C) i ECPG. Pozostałe sterowniki, np. JDBC, to osobne projekty[^pg-extif]. Opakowania danych obcych (FDW, część standardu SQL/MED) pokazują zewnętrzne źródła jako tabele w zwykłych zapytaniach[^pg-fdw]. LISTEN i NOTIFY przekazują powiadomienia między procesami jednej bazy[^pg-notify]. Dekodowanie logiczne przesyła strumień zmian do odbiorców zewnętrznych, np. do replikacji lub audytu[^pg-logdec]. Replikacja logiczna działa w modelu publikacji i subskrypcji[^pg-logrep]. PostGIS współpracuje z narzędziami GIS, m.in. QGIS i GeoServer[^postgis].

### Skalowalność

W pionie PostgreSQL wykorzystuje wiele procesorów. Z wykonaniem równoległym wiele zapytań działa ponad dwa razy szybciej, choć nie każde zapytanie na tym zyskuje[^pg-parallel]. Partycjonowanie dzieli dużą tabelę na mniejsze części fizyczne. Według dokumentacji opłaca się zwykle wtedy, gdy tabela przekracza pamięć RAM serwera[^pg-partition]. Odczyty skalują się poziomo przez serwery hot standby[^pg-hot]. Podział danych między serwery i zapytanie na wielu serwerach wymagają aplikacji lub zewnętrznych narzędzi, np. PL/Proxy[^pg-repl]. Producent podaje, że w produkcji działają klastry z wieloma terabajtami danych, a wyspecjalizowane systemy obsługują petabajty[^pg-about].

### Obszary biznesowe

Producent podkreśla niezawodność, integralność danych i rozszerzalność. PostgreSQL jest zgodny z ACID od 2001 r. i ma rozszerzenie geoprzestrzenne PostGIS[^pg-about]. Z tych cech wynikają zastosowania w systemach transakcyjnych, w których błąd danych kosztuje: rezerwacjach, płatnościach i ewidencji. Dokumentacja typów zakresowych podaje jako przykład właśnie rezerwacje sali[^pg-range]. PostGIS otwiera zastosowania lokalizacyjne i GIS[^postgis], a jsonb pozwala trzymać dane półstrukturalne obok relacyjnych[^pg-json]. Bagażomat korzysta z tych cech wprost: reguły EXCLUDE blokują podwójną rezerwację skrytki, PostGIS obsługuje mapę skrytek, a jsonb przechowuje historię zmian w `audit_event_`, więc aplikacja działa na PostgreSQL (rozdz. 4).

[^pg-history]: Dokumentacja PostgreSQL 17, rozdz. 2, <https://www.postgresql.org/docs/17/history.html>.
[^pg-licence]: PostgreSQL, „License”, <https://www.postgresql.org/about/licence/>.
[^pg-whatis]: Dokumentacja PostgreSQL 17, rozdz. 1, <https://www.postgresql.org/docs/17/intro-whatis.html>.
[^pg-versioning]: PostgreSQL, „Versioning Policy”, <https://www.postgresql.org/support/versioning/>.
[^pg-sql]: Dokumentacja PostgreSQL 17, dodatek D, <https://www.postgresql.org/docs/17/features.html>.
[^pg-iso]: Dokumentacja PostgreSQL 17, rozdz. 13.2, <https://www.postgresql.org/docs/17/transaction-iso.html>.
[^pg-mvcc]: Dokumentacja PostgreSQL 17, rozdz. 13.1, <https://www.postgresql.org/docs/17/mvcc-intro.html>.
[^pg-constraints]: Dokumentacja PostgreSQL 17, rozdz. 5.5, <https://www.postgresql.org/docs/17/ddl-constraints.html>.
[^pg-range]: Dokumentacja PostgreSQL 17, rozdz. 8.17, <https://www.postgresql.org/docs/17/rangetypes.html>.
[^pg-idx]: Dokumentacja PostgreSQL 17, rozdz. 11.2, <https://www.postgresql.org/docs/17/indexes-types.html>.
[^pg-partial]: Dokumentacja PostgreSQL 17, rozdz. 11.8, <https://www.postgresql.org/docs/17/indexes-partial.html>.
[^pg-vacuum]: Dokumentacja PostgreSQL 17, rozdz. 24.1, <https://www.postgresql.org/docs/17/routine-vacuuming.html>.
[^pg-connect]: Dokumentacja PostgreSQL 17, rozdz. 50.2, <https://www.postgresql.org/docs/17/connect-estab.html>.
[^pg-failover]: Dokumentacja PostgreSQL 17, rozdz. 26.3, <https://www.postgresql.org/docs/17/warm-standby-failover.html>.
[^pg-ext]: Dokumentacja PostgreSQL 17, rozdz. 36.17, <https://www.postgresql.org/docs/17/extend-extensions.html>.
[^postgis]: PostGIS, strona projektu, <https://postgis.net/>.
[^pg-json]: Dokumentacja PostgreSQL 17, rozdz. 8.14, <https://www.postgresql.org/docs/17/datatype-json.html>.
[^pg-17]: PostgreSQL, „PostgreSQL 17 Released!”, <https://www.postgresql.org/about/news/postgresql-17-released-2936/>.
[^pg-limits]: Dokumentacja PostgreSQL 17, dodatek K, <https://www.postgresql.org/docs/17/limits.html>.
[^pg-repl]: Dokumentacja PostgreSQL 17, rozdz. 26.1, <https://www.postgresql.org/docs/17/different-replication-solutions.html>.
[^pg-hot]: Dokumentacja PostgreSQL 17, rozdz. 26.4, <https://www.postgresql.org/docs/17/hot-standby.html>.
[^pg-checksums]: Dokumentacja PostgreSQL 17, rozdz. 28.2, <https://www.postgresql.org/docs/17/checksums.html>.
[^pg-wal]: Dokumentacja PostgreSQL 17, rozdz. 28.3, <https://www.postgresql.org/docs/17/wal-intro.html>.
[^pg-pitr]: Dokumentacja PostgreSQL 17, rozdz. 25.3, <https://www.postgresql.org/docs/17/continuous-archiving.html>.
[^pg-ha]: Dokumentacja PostgreSQL 17, rozdz. 26, <https://www.postgresql.org/docs/17/high-availability.html>.
[^pg-roles]: Dokumentacja PostgreSQL 17, rozdz. 21, <https://www.postgresql.org/docs/17/user-manag.html>.
[^pg-rls]: Dokumentacja PostgreSQL 17, rozdz. 5.9, <https://www.postgresql.org/docs/17/ddl-rowsecurity.html>.
[^pg-auth]: Dokumentacja PostgreSQL 17, rozdz. 20.3, <https://www.postgresql.org/docs/17/auth-methods.html>.
[^pg-enc]: Dokumentacja PostgreSQL 17, rozdz. 18.8, <https://www.postgresql.org/docs/17/encryption-options.html>.
[^pg-dump]: Dokumentacja PostgreSQL 17, rozdz. 25.1, <https://www.postgresql.org/docs/17/backup-dump.html>.
[^pg-upgrade]: Dokumentacja PostgreSQL 17, pg_upgrade, <https://www.postgresql.org/docs/17/pgupgrade.html>.
[^pg-upgrading]: Dokumentacja PostgreSQL 17, rozdz. 18.6, <https://www.postgresql.org/docs/17/upgrading.html>.
[^pg-ddl]: PostgreSQL Wiki, „Transactional DDL in PostgreSQL: A Competitive Analysis”, <https://wiki.postgresql.org/wiki/Transactional_DDL_in_PostgreSQL:_A_Competitive_Analysis>.
[^pg-copy]: Dokumentacja PostgreSQL 17, COPY, <https://www.postgresql.org/docs/17/sql-copy.html>.
[^pg-extif]: Dokumentacja PostgreSQL 17, dodatek H.1, <https://www.postgresql.org/docs/17/external-interfaces.html>.
[^pg-fdw]: Dokumentacja PostgreSQL 17, rozdz. 5.13, <https://www.postgresql.org/docs/17/ddl-foreign-data.html>.
[^pg-notify]: Dokumentacja PostgreSQL 17, NOTIFY, <https://www.postgresql.org/docs/17/sql-notify.html>.
[^pg-logdec]: Dokumentacja PostgreSQL 17, rozdz. 47, <https://www.postgresql.org/docs/17/logicaldecoding.html>.
[^pg-logrep]: Dokumentacja PostgreSQL 17, rozdz. 29, <https://www.postgresql.org/docs/17/logical-replication.html>.
[^pg-parallel]: Dokumentacja PostgreSQL 17, rozdz. 15, <https://www.postgresql.org/docs/17/parallel-query.html>.
[^pg-partition]: Dokumentacja PostgreSQL 17, rozdz. 5.12, <https://www.postgresql.org/docs/17/ddl-partitioning.html>.
[^pg-about]: PostgreSQL, „About”, <https://www.postgresql.org/about/>.

## MySQL 8.4 LTS

### Opis

MySQL to relacyjny SZBD typu klient-serwer z wielowątkowym serwerem SQL. Rozwija go Oracle Corporation. Kod jest dostępny na licencji GPL, a do osadzenia w produkcie komercyjnym Oracle sprzedaje licencję komercyjną[^my-what]. Wydania dzielą się na linię Innovation z nowymi funkcjami i linię LTS z samymi poprawkami, 5 latami wsparcia podstawowego i 3 latami rozszerzonego[^my-releases]. Wersja 8.4.0 ukazała się 30 kwietnia 2024 r.[^my-840] Domyślnym silnikiem składowania jest InnoDB, a jego domyślny poziom izolacji to REPEATABLE READ[^my-innodb][^my-iso].

### Zalety

Silnik InnoDB spełnia ACID i odtwarza dane po awarii. Blokady wierszy i spójne odczyty w stylu Oracle zwiększają współbieżność. Dane każdej tabeli porządkuje indeks klastrowy klucza głównego, więc wyszukiwanie po kluczu wymaga mało operacji wejścia-wyjścia. Klucze obce pilnują spójności między tabelami[^my-innodb]. Wbudowana replikacja pozwala rozłożyć odczyty na repliki, a analizy prowadzić na replice bez wpływu na wydajność serwera źródłowego[^my-repl].

### Wady

Reguły obejmującej wiele wierszy nie zapisze się w CHECK, bo warunek nie może zawierać podzapytań ani funkcji składowanych[^my-check]. Składnia CREATE INDEX nie ma też predykatu WHERE, czyli indeksu częściowego[^my-index]. Dlatego w Bagażomacie pary wyzwalaczy BEFORE INSERT i BEFORE UPDATE z blokadą zastępują pięć reguł EXCLUDE, a indeksy funkcyjne z wyrażeniem CASE zastępują indeksy częściowe (rozdz. 3). Audyt, zapora SQL, maskowanie danych i pula wątków są tylko w płatnej edycji Enterprise[^my-ee].

### Udogodnienia

Typ JSON sprawdza poprawność dokumentu i przechowuje go binarnie, więc serwer czyta element po kluczu bez parsowania tekstu. JSON_SET, JSON_REPLACE i JSON_REMOVE mogą zmienić dokument częściowo, w miejscu[^my-json]. Indeks wielowartościowy indeksuje tablice JSON, a funkcyjna część klucza – wartość wyrażenia[^my-index]. Indeks niewidoczny dla optymalizatora pozwala sprawdzić skutek usunięcia indeksu bez kosztownego DROP i CREATE[^my-invisible]. EXPLAIN ANALYZE wykonuje zapytanie i pokazuje rzeczywiste czasy oraz liczby wierszy obok szacunków[^my-explain]. InnoDB ma indeksy SPATIAL dla typów przestrzennych zgodnych z OGC[^my-spatial]. Parser ngram dzieli tekst na ciągi n znaków na potrzeby wyszukiwania pełnotekstowego[^my-ngram].

### Ograniczenia

Serwer dopuszcza najwyżej 4096 kolumn w tabeli i 65 535 bajtów w wierszu[^my-cols]. InnoDB ma niższe limity: 1017 kolumn, 64 indeksy pomocnicze, 16 kolumn w indeksie złożonym i tabelę do 64 TB przy stronie 16 kB[^my-innolimits]. Wyzwalacz nie może zmieniać tabeli, której używa wywołujące go polecenie[^my-sp]. Partycjonowane tabele InnoDB nie obsługują kluczy obcych[^my-partlim]. Kolumny JSON nie indeksuje się wprost, tylko przez kolumnę generowaną albo indeks wielowartościowy[^my-json].

### Awaryjność

InnoDB zapisuje zmiany w dzienniku redo. Po awarii serwer odtwarza z niego niedokończone zmiany, zanim przyjmie połączenia[^my-redo]. Bufor podwójnego zapisu (doublewrite) trzyma kopię strony, więc przerwany zapis strony da się naprawić podczas odtwarzania[^my-dblwr]. Dziennik binarny rejestruje zmiany danych dla replik i dla odtwarzania stanu z wybranej chwili: po przywróceniu kopii serwer wykonuje ponownie zdarzenia zapisane po niej[^my-binlog]. Replikacja jest domyślnie asynchroniczna. W trybie półsynchronicznym zatwierdzenie czeka, aż co najmniej jedna replika potwierdzi odbiór transakcji[^my-repl]. Group Replication uzgadnia kolejność transakcji algorytmem Paxos i sama wykrywa awarię członka grupy[^my-gr]. InnoDB Cluster łączy co najmniej trzy serwery z Group Replication, MySQL Router i MySQL Shell, a po awarii serwera głównego sam promuje serwer zapasowy[^my-cluster].

### Bezpieczeństwo

Uprawnienia nadaje się kontom i rolom, czyli nazwanym zbiorom uprawnień[^my-roles]. Domyślna wtyczka uwierzytelniania caching_sha2_password przechowuje hasło jako skrót SHA-256[^my-sha2]. Od wersji 8.4.0 przestarzała wtyczka mysql_native_password jest domyślnie wyłączona, a słabych szyfrów TLS nie można już ustawić[^my-new]. Klienci domyślnie próbują połączenia szyfrowanego, a zmienna require_secure_transport każe serwerowi odrzucać połączenia nieszyfrowane[^my-tls]. InnoDB szyfruje w spoczynku przestrzenie tabel oraz dzienniki redo i undo. Klucz główny z modułu keyring szyfruje klucze przestrzeni tabel. Każda edycja ma moduł keyring zapisujący klucze w pliku lokalnym, a moduły dla zewnętrznych sejfów kluczy należą do edycji Enterprise[^my-tde].

### Migracje

mysqldump tworzy kopię logiczną: polecenia SQL, które odtwarzają obiekty i dane, także na innym serwerze. Z opcją --single-transaction zapisuje spójny stan tabel InnoDB bez blokowania aplikacji. Dokumentacja zastrzega, że przy dużych danych nie jest to rozwiązanie szybkie ani skalowalne, i poleca narzędzia MySQL Shell, które zrzucają dane wieloma wątkami i z kompresją[^my-dump][^my-shell]. Wtyczka clone kopiuje fizyczny stan danych InnoDB z innego serwera i służy do zakładania replik[^my-clone]. W obrębie serii LTS można aktualizować i cofać wersję w miejscu, a przejście do kolejnej serii LTS nie może żadnej pominąć[^my-releases]. Słownik danych i tabele systemowe serwer aktualizuje sam przy starcie[^my-upgrade]. DDL nie jest transakcyjny: każde polecenie DDL niejawnie kończy bieżącą transakcję, więc nieudanej migracji schematu nie wycofa ROLLBACK[^my-atomic]. Dodanie kolumny domyślnie zmienia tylko metadane, a indeks pomocniczy powstaje bez blokowania zapisów[^my-ddl].

### Integracje

Oracle rozwija sterowniki Connector/J (JDBC), Connector/ODBC, Connector/NET, Connector/Python, Connector/C++ i Connector/Node.js oraz API języka C. Inne języki mają sterowniki zewnętrzne[^my-conn]. Domyślnie włączony X Plugin obsługuje X Protocol, przez który MySQL Shell i sterowniki używają MySQL jako magazynu dokumentów bez schematu (X DevAPI)[^my-docstore]. Narzędzia zrzutu MySQL Shell zapisują dane do Oracle Cloud Infrastructure Object Storage i sprawdzają zgodność z usługą MySQL HeatWave[^my-shell].

### Skalowalność

W pionie serwer korzysta z wielu wątków[^my-what]. Partycjonowanie dzieli tabelę według reguł RANGE, LIST, HASH lub KEY na najwyżej 8192 partycje[^my-part][^my-partlim]. Odczyty skalują się poziomo przez repliki, ale wszystkie zapisy trafiają do serwera źródłowego[^my-repl]. Group Replication w trybie wielu serwerów głównych przyjmuje zapisy na każdym członku grupy[^my-gr]. Grupa liczy jednak najwyżej 9 serwerów, a ten tryb nie obsługuje kaskadowych kluczy obcych ani, domyślnie, poziomu SERIALIZABLE[^my-grlim]. Klaster bez współdzielonych zasobów (shared-nothing) z danymi w pamięci daje osobna technologia NDB Cluster[^my-ndb].

### Obszary biznesowe

Producent podaje, że MySQL obsługuje witryny o dużym ruchu, systemy krytyczne dla biznesu i oprogramowanie pakietowe. Wśród użytkowników wymienia Facebooka, Twittera, Booking.com i Verizon, a w materiałach wyróżnia stos LAMP, SaaS i bazy osadzone (OEM/ISV)[^my-why]. Bagażomat mógłby trzymać w MySQL zamówienia i płatności, ale reguły wykluczeń wymagają tu wyzwalaczy z blokadą (rozdz. 3). Aplikacja korzysta z PostgreSQL, a MySQL występuje tylko w pomiarach.

[^my-what]: Dokumentacja MySQL 8.4, rozdz. 1.2.1, <https://dev.mysql.com/doc/refman/8.4/en/what-is-mysql.html>.
[^my-releases]: Dokumentacja MySQL 8.4, rozdz. 1.3, <https://dev.mysql.com/doc/refman/8.4/en/mysql-releases.html>.
[^my-840]: Informacje o wydaniu MySQL 8.4.0, <https://dev.mysql.com/doc/relnotes/mysql/8.4/en/news-8-4-0.html>.
[^my-innodb]: Dokumentacja MySQL 8.4, rozdz. 17.1, <https://dev.mysql.com/doc/refman/8.4/en/innodb-introduction.html>.
[^my-iso]: Dokumentacja MySQL 8.4, rozdz. 17.7.2.1, <https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html>.
[^my-repl]: Dokumentacja MySQL 8.4, rozdz. 19, <https://dev.mysql.com/doc/refman/8.4/en/replication.html>.
[^my-check]: Dokumentacja MySQL 8.4, rozdz. 15.1.20.6, <https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html>.
[^my-index]: Dokumentacja MySQL 8.4, rozdz. 15.1.15, <https://dev.mysql.com/doc/refman/8.4/en/create-index.html>.
[^my-ee]: MySQL, „MySQL Enterprise Edition”, <https://www.mysql.com/products/enterprise/>.
[^my-json]: Dokumentacja MySQL 8.4, rozdz. 13.5, <https://dev.mysql.com/doc/refman/8.4/en/json.html>.
[^my-invisible]: Dokumentacja MySQL 8.4, rozdz. 10.3.12, <https://dev.mysql.com/doc/refman/8.4/en/invisible-indexes.html>.
[^my-explain]: Dokumentacja MySQL 8.4, rozdz. 15.8.2, <https://dev.mysql.com/doc/refman/8.4/en/explain.html>.
[^my-spatial]: Dokumentacja MySQL 8.4, rozdz. 13.4, <https://dev.mysql.com/doc/refman/8.4/en/spatial-types.html>.
[^my-ngram]: Dokumentacja MySQL 8.4, rozdz. 14.9.8, <https://dev.mysql.com/doc/refman/8.4/en/fulltext-search-ngram.html>.
[^my-cols]: Dokumentacja MySQL 8.4, rozdz. 10.4.7, <https://dev.mysql.com/doc/refman/8.4/en/column-count-limit.html>.
[^my-innolimits]: Dokumentacja MySQL 8.4, rozdz. 17.21, <https://dev.mysql.com/doc/refman/8.4/en/innodb-limits.html>.
[^my-sp]: Dokumentacja MySQL 8.4, rozdz. 27.8, <https://dev.mysql.com/doc/refman/8.4/en/stored-program-restrictions.html>.
[^my-partlim]: Dokumentacja MySQL 8.4, rozdz. 26.6, <https://dev.mysql.com/doc/refman/8.4/en/partitioning-limitations.html>.
[^my-redo]: Dokumentacja MySQL 8.4, rozdz. 17.6.5, <https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html>.
[^my-dblwr]: Dokumentacja MySQL 8.4, rozdz. 17.6.4, <https://dev.mysql.com/doc/refman/8.4/en/innodb-doublewrite-buffer.html>.
[^my-binlog]: Dokumentacja MySQL 8.4, rozdz. 7.4.4, <https://dev.mysql.com/doc/refman/8.4/en/binary-log.html>.
[^my-gr]: Dokumentacja MySQL 8.4, rozdz. 20.1, <https://dev.mysql.com/doc/refman/8.4/en/group-replication-background.html>.
[^my-cluster]: Dokumentacja MySQL Shell 26.10, rozdz. 8, <https://dev.mysql.com/doc/mysql-shell/26.10/en/mysql-innodb-cluster.html>.
[^my-roles]: Dokumentacja MySQL 8.4, rozdz. 8.2.10, <https://dev.mysql.com/doc/refman/8.4/en/roles.html>.
[^my-sha2]: Dokumentacja MySQL 8.4, rozdz. 8.4.1.2, <https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html>.
[^my-new]: Dokumentacja MySQL 8.4, rozdz. 1.4, <https://dev.mysql.com/doc/refman/8.4/en/mysql-nutshell.html>.
[^my-tls]: Dokumentacja MySQL 8.4, rozdz. 8.3.1, <https://dev.mysql.com/doc/refman/8.4/en/using-encrypted-connections.html>.
[^my-tde]: Dokumentacja MySQL 8.4, rozdz. 17.13, <https://dev.mysql.com/doc/refman/8.4/en/innodb-data-encryption.html>.
[^my-dump]: Dokumentacja MySQL 8.4, rozdz. 6.5.4, <https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html>.
[^my-shell]: Dokumentacja MySQL Shell 26.10, rozdz. 12.6, <https://dev.mysql.com/doc/mysql-shell/26.10/en/mysql-shell-utilities-dump-instance-schema.html>.
[^my-clone]: Dokumentacja MySQL 8.4, rozdz. 7.6.7, <https://dev.mysql.com/doc/refman/8.4/en/clone-plugin.html>.
[^my-upgrade]: Dokumentacja MySQL 8.4, rozdz. 3.4, <https://dev.mysql.com/doc/refman/8.4/en/upgrading-what-is-upgraded.html>.
[^my-atomic]: Dokumentacja MySQL 8.4, rozdz. 15.1.1, <https://dev.mysql.com/doc/refman/8.4/en/atomic-ddl.html>.
[^my-ddl]: Dokumentacja MySQL 8.4, rozdz. 17.12.1, <https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html>.
[^my-conn]: Dokumentacja MySQL 8.4, rozdz. 31, <https://dev.mysql.com/doc/refman/8.4/en/connectors-apis.html>.
[^my-docstore]: Dokumentacja MySQL 8.4, rozdz. 22, <https://dev.mysql.com/doc/refman/8.4/en/document-store.html>.
[^my-part]: Dokumentacja MySQL 8.4, rozdz. 26.1, <https://dev.mysql.com/doc/refman/8.4/en/partitioning-overview.html>.
[^my-grlim]: Dokumentacja MySQL 8.4, rozdz. 20.3.2, <https://dev.mysql.com/doc/refman/8.4/en/group-replication-limitations.html>.
[^my-ndb]: Dokumentacja MySQL 8.4, rozdz. 25.2, <https://dev.mysql.com/doc/refman/8.4/en/mysql-cluster-overview.html>.
[^my-why]: MySQL, „Why MySQL?”, <https://www.mysql.com/why-mysql/>.

## MongoDB 8.0

### Opis

MongoDB to dokumentowa baza danych. Rekord jest dokumentem, czyli zbiorem par pole–wartość podobnym do obiektu JSON[^mg-intro]. Dokumenty są zapisane w binarnym formacie BSON[^mg-bson]. Firmę MongoDB, wcześniej 10gen, założono w 2007 r.[^mg-company] Wersje Community Server wydane od 16 października 2018 r. mają licencję SSPL. OSI jej nie zatwierdziła, więc według OSI nie jest to licencja open source[^mg-sspl]. Wersja 8.0.0 ukazała się 2 października 2024 r. jako wydanie główne[^mg-80]. Producent wspiera ją do 31 października 2029 r.[^mg-lifecycle] Operacja na jednym dokumencie jest atomowa[^mg-tx].

### Zalety

Dokumenty odpowiadają typom danych języków programowania. Osadzone dokumenty i tablice ograniczają kosztowne złączenia, a dynamiczny schemat pozwala na różną strukturę dokumentów jednej kolekcji[^mg-intro]. Główna zasada modelowania brzmi: dane czytane razem przechowuj razem[^mg-model]. Gdy operacja obejmuje wiele dokumentów, baza oferuje transakcje ACID[^mg-tx]. Replikacja z automatycznym przełączaniem i podział danych między serwery (sharding) są wbudowane[^mg-intro]. Według producenta wersja 8.0 ma do 36% większą przepustowość odczytów niż 7.0[^mg-80].

### Wady

Transakcja na wielu dokumentach zwykle kosztuje więcej niż zapis jednego dokumentu i nie zastępuje dobrego projektu schematu[^mg-tx]. Osadzanie powiela dane. Zwiększa to zajętość dysku, a częste zmiany powielonych danych obciążają bazę[^mg-dup]. Walidacja schematu sprawdza pola dokumentu, np. typy i zakresy wartości[^mg-validation]. Regułę obejmującą wiele dokumentów, np. zakaz podwójnej rezerwacji skrytki, musi więc pilnować aplikacja (rozdz. 3). Kontrola dostępu jest domyślnie wyłączona[^mg-authz]. We własnej instalacji szyfrowanie plików danych i audyt są tylko w edycji Enterprise[^mg-ear][^mg-audit].

### Udogodnienia

Potok agregacji przetwarza dokumenty etapami: filtruje je, grupuje i liczy wartości[^mg-agg]. Etap `$lookup` wykonuje lewe złączenie zewnętrzne z kolekcją tej samej bazy[^mg-lookup], a `$graphLookup` przeszukuje kolekcję rekurencyjnie[^mg-graphlookup]. Indeksy mogą być złożone, wielokluczowe (na polach tablic) i geoprzestrzenne[^mg-indexes]. Indeks 2dsphere znajduje punkty w obszarze i liczy odległość od punktu na modelu kuli ziemskiej[^mg-2dsphere]. Indeks częściowy obejmuje tylko dokumenty spełniające filtr, a indeks TTL sam usuwa dokumenty po upływie czasu[^mg-idxprop]. Reguły walidacji, np. w JSON Schema, domyślnie odrzucają wstawienie lub zmianę, która dałaby niepoprawny dokument[^mg-validation]. Metoda `explain()` w trybie `executionStats` wykonuje zapytanie i zwraca statystyki wybranego planu[^mg-explain].

### Ograniczenia

Dokument BSON ma najwyżej 16 MiB i 100 poziomów zagnieżdżenia. Kolekcja ma najwyżej 64 indeksy, a indeks złożony do 32 pól[^mg-limits]. Unikalny indeks wielokluczowy działa tylko między dokumentami: jeden dokument może mieć w tablicy powtórzone wartości klucza[^mg-unique]. Transakcja domyślnie musi skończyć się w ciągu minuty. Samodzielny serwer (standalone) nie obsługuje transakcji[^mg-txprod], dlatego stanowisko pomiarowe uruchamia MongoDB jako zbiór replik (rozdz. 5). Etap `$graphLookup` musi zmieścić się w 100 MB pamięci[^mg-graphlookup].

### Awaryjność

Silnik WiredTiger zapisuje punkty kontrolne i dziennik (journal). Po awarii baza wraca do ostatniego punktu kontrolnego i powtarza operacje z dziennika. Dziennik trafia na dysk co 100 ms albo od razu przy zapisie z `j: true`. Zmiany czekające jeszcze w buforze mogą zginąć przy nagłym wyłączeniu serwera[^mg-journal]. Zbiór replik (replica set) to grupa serwerów z tymi samymi danymi. Gdy serwer główny milczy dłużej niż 10 s, serwer zapasowy ogłasza wybór nowego serwera głównego. Mediana czasu wyboru zwykle nie przekracza 12 s[^mg-repl]. Od wersji 5.0 domyślne potwierdzenie zapisu to `w: "majority"`[^mg-tx]. Kopie zapasowe tworzy się migawkami systemu plików, narzędziem `mongodump` albo w Ops Managerze i Cloud Managerze[^mg-backup].

### Bezpieczeństwo

Dostęp opiera się na rolach (RBAC). Rola nadaje uprawnienia do akcji na zasobie: bazie, kolekcji lub klastrze. Są role wbudowane i definiowane przez użytkownika. Kontrolę dostępu włącza opcja `security.authorization`[^mg-authz]. Domyślny mechanizm uwierzytelniania to SCRAM. Edycja Community obsługuje też certyfikaty x.509, a Kerberos, LDAP i OpenID Connect są w edycji Enterprise[^mg-authn]. Producent zaleca TLS dla wszystkich połączeń[^mg-checklist]. Szyfrowanie w spoczynku (AES-256) obejmuje wszystkie pliki danych, tylko w edycji Enterprise[^mg-ear]. Queryable Encryption szyfruje pola po stronie klienta i pozwala je przeszukiwać bez ujawniania danych serwerowi. Od wersji 8.0 obsługuje też zapytania zakresowe[^mg-qe][^mg-80].

### Migracje

`mongodump` tworzy binarną kopię zawartości bazy, a `mongorestore` ją wczytuje[^mg-dump]. Producent przeznacza te narzędzia dla małych wdrożeń[^mg-backup]. `mongoimport` importuje pliki Extended JSON, CSV i TSV[^mg-import]. Tak ładujemy dane w projekcie (rozdz. 3). Do wersji 8.0 przechodzi się z serii 7.0, a starsze wdrożenie aktualizuje się kolejno przez każdą wersję główną. Nowe funkcje 8.0 włącza dopiero zmiana `featureCompatibilityVersion`[^mg-upgrade]. Nowe pola można dodawać bez przepisywania dokumentów i bez migracji schematu[^mg-model]. Bezpłatny Relational Migrator przenosi dane z Oracle, SQL Server, MySQL i PostgreSQL. Klucze obce może przy tym zamienić na osadzone dokumenty i tablice[^mg-relmig].

### Integracje

Producent rozwija oficjalne sterowniki dla 13 języków, m.in. C, C#, Go, Javy, Pythona i Rusta[^mg-drivers]. Sterowniki i konektory mają licencję Apache 2.0[^mg-sspl]. Strumienie zmian (change streams) pozwalają subskrybować zmiany kolekcji, bazy lub całego wdrożenia bez ręcznego czytania dziennika operacji (oplog). Działają w zbiorach replik i klastrach z shardingiem[^mg-cs]. Konektor Apache Kafka zapisuje dane z tematów Kafki w MongoDB i publikuje zmiany z MongoDB do Kafki[^mg-kafka].

### Skalowalność

MongoDB skaluje się poziomo przez sharding, czyli podział danych i obciążenia między serwery, kosztem bardziej złożonej infrastruktury. Klucz shardingu rozdziela dokumenty kolekcji między shardy, a każdy shard jest zbiorem replik. Router `mongos` kieruje zapytania, a serwery konfiguracyjne trzymają metadane klastra. Podział zakresowy kieruje zapytanie o zakres kluczy tylko do potrzebnych shardów. Podział haszowy równo rozkłada klucze rosnące, ale wtedy zapytania o zakres trafiają do wielu shardów[^mg-shard]. Wersja 8.0 pozwala cofnąć sharding kolekcji i przenieść kolekcję na inny shard, a resharding trwa w niej wyraźnie krócej[^mg-80]. Indeks unikalny działa między shardami tylko wtedy, gdy zaczyna się od klucza shardingu[^mg-limits]. Odczyty można kierować do serwerów zapasowych, ale replikacja jest asynchroniczna, więc mogą zwrócić nieaktualne dane[^mg-repl].

### Obszary biznesowe

Producent podaje ponad 70 tys. klientów[^mg-company]. Wśród zastosowań wymienia katalogi produktów, zarządzanie treścią, Internet rzeczy, aplikacje mobilne, płatności, personalizację, gry i jednolity widok danych operacyjnych[^mg-usecases]. W Bagażomacie MongoDB zapisuje zamówienie z odcinkami, kodami i płatnościami w jednym dokumencie, ale zakazu podwójnej rezerwacji skrytki musi pilnować aplikacja (rozdz. 3), więc MongoDB występuje tylko w pomiarach.

[^mg-intro]: Dokumentacja MongoDB 8.0, „What is MongoDB?”, <https://www.mongodb.com/docs/v8.0/>.
[^mg-bson]: Dokumentacja MongoDB 8.0, „BSON Types”, <https://www.mongodb.com/docs/v8.0/reference/bson-types/>.
[^mg-company]: MongoDB, „About MongoDB”, <https://www.mongodb.com/company>.
[^mg-sspl]: MongoDB, „Server Side Public License FAQ”, <https://www.mongodb.com/legal/licensing/server-side-public-license/faq>.
[^mg-80]: Dokumentacja MongoDB 8.0, „Release Notes for MongoDB 8.0”, <https://www.mongodb.com/docs/v8.0/release-notes/8.0/>.
[^mg-lifecycle]: MongoDB, „Software Lifecycle Schedules”, <https://www.mongodb.com/legal/support-policy/lifecycles>.
[^mg-tx]: Dokumentacja MongoDB 8.0, „Transactions”, <https://www.mongodb.com/docs/v8.0/core/transactions/>.
[^mg-model]: Dokumentacja MongoDB 8.0, „Data Modeling”, <https://www.mongodb.com/docs/v8.0/data-modeling/>.
[^mg-dup]: Dokumentacja MongoDB 8.0, „Handle Duplicate Data”, <https://www.mongodb.com/docs/v8.0/data-modeling/handle-duplicate-data/>.
[^mg-validation]: Dokumentacja MongoDB 8.0, „Schema Validation”, <https://www.mongodb.com/docs/v8.0/core/schema-validation/>.
[^mg-authz]: Dokumentacja MongoDB 8.0, „Role-Based Access Control”, <https://www.mongodb.com/docs/v8.0/core/authorization/>.
[^mg-ear]: Dokumentacja MongoDB 8.0, „Encryption at Rest”, <https://www.mongodb.com/docs/v8.0/core/security-encryption-at-rest/>.
[^mg-audit]: Dokumentacja MongoDB 8.0, „Auditing”, <https://www.mongodb.com/docs/v8.0/core/auditing/>.
[^mg-agg]: Dokumentacja MongoDB 8.0, „Aggregation Operations”, <https://www.mongodb.com/docs/v8.0/aggregation/>.
[^mg-lookup]: Dokumentacja MongoDB 8.0, „$lookup”, <https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/lookup/>.
[^mg-graphlookup]: Dokumentacja MongoDB 8.0, „$graphLookup”, <https://www.mongodb.com/docs/v8.0/reference/operator/aggregation/graphlookup/>.
[^mg-indexes]: Dokumentacja MongoDB 8.0, „Indexes”, <https://www.mongodb.com/docs/v8.0/indexes/>.
[^mg-2dsphere]: Dokumentacja MongoDB 8.0, „2dsphere Indexes”, <https://www.mongodb.com/docs/v8.0/core/indexes/index-types/geospatial/2dsphere/>.
[^mg-idxprop]: Dokumentacja MongoDB 8.0, „Index Properties”, <https://www.mongodb.com/docs/v8.0/core/indexes/index-properties/>.
[^mg-explain]: Dokumentacja MongoDB 8.0, „db.collection.explain()”, <https://www.mongodb.com/docs/v8.0/reference/method/db.collection.explain/>.
[^mg-limits]: Dokumentacja MongoDB 8.0, „MongoDB Limits and Thresholds”, <https://www.mongodb.com/docs/v8.0/reference/limits/>.
[^mg-unique]: Dokumentacja MongoDB 8.0, „Unique Indexes”, <https://www.mongodb.com/docs/v8.0/core/index-unique/>.
[^mg-txprod]: Dokumentacja MongoDB 8.0, „Production Considerations”, <https://www.mongodb.com/docs/v8.0/core/transactions-production-consideration/>.
[^mg-journal]: Dokumentacja MongoDB 8.0, „Journaling”, <https://www.mongodb.com/docs/v8.0/core/journaling/>.
[^mg-repl]: Dokumentacja MongoDB 8.0, „Replication”, <https://www.mongodb.com/docs/v8.0/replication/>.
[^mg-backup]: Dokumentacja MongoDB 8.0, „Backup Methods”, <https://www.mongodb.com/docs/v8.0/core/backups/>.
[^mg-authn]: Dokumentacja MongoDB 8.0, „Authentication”, <https://www.mongodb.com/docs/v8.0/core/authentication/>.
[^mg-checklist]: Dokumentacja MongoDB 8.0, „Security Checklist”, <https://www.mongodb.com/docs/v8.0/administration/security-checklist/>.
[^mg-qe]: Dokumentacja MongoDB 8.0, „Queryable Encryption”, <https://www.mongodb.com/docs/v8.0/core/queryable-encryption/>.
[^mg-dump]: Dokumentacja MongoDB Database Tools, „mongodump”, <https://www.mongodb.com/docs/database-tools/mongodump/>.
[^mg-import]: Dokumentacja MongoDB Database Tools, „mongoimport”, <https://www.mongodb.com/docs/database-tools/mongoimport/>.
[^mg-upgrade]: Dokumentacja MongoDB 8.0, „Upgrade a Replica Set to 8.0”, <https://www.mongodb.com/docs/v8.0/release-notes/8.0-upgrade-replica-set/>.
[^mg-relmig]: Dokumentacja MongoDB Relational Migrator, <https://www.mongodb.com/docs/relational-migrator/>.
[^mg-drivers]: Dokumentacja MongoDB, „MongoDB Drivers”, <https://www.mongodb.com/docs/drivers/>.
[^mg-cs]: Dokumentacja MongoDB 8.0, „Change Streams”, <https://www.mongodb.com/docs/v8.0/changestreams/>.
[^mg-kafka]: Dokumentacja MongoDB Kafka Connector, <https://www.mongodb.com/docs/kafka-connector/current/>.
[^mg-shard]: Dokumentacja MongoDB 8.0, „Sharding”, <https://www.mongodb.com/docs/v8.0/sharding/>.
[^mg-usecases]: MongoDB, „Use Cases”, <https://www.mongodb.com/solutions/use-cases>.

## Neo4j 5.26 Community

### Opis

Neo4j to grafowa baza danych. Zapisuje dane jako węzły, relacje i właściwości, a nie jako tabele czy dokumenty[^neo-graphdb]. Stosuje model grafu właściwości (property graph)[^neo-intro]. Pierwszy prototyp powstał w 2000 r., a w 2007 r. powstała szwedzka firma, która go rozwija[^neo-company]. Edycja Community ma otwarty kod na licencji GPLv3. Obejmuje transakcje ACID, język Cypher i interfejsy programistyczne, ale jest przeznaczona na jeden serwer[^neo-intro]. Wersja 5.26 ukazała się 6 grudnia 2024 r.[^neo-versions] Jest ostatnią z serii 5 i wersją z długim wsparciem (LTS) do czerwca 2028 r. Po niej zmienia się numeracja, a pierwsza nowa wersja to 2025.01[^neo-lts].

### Zalety

Relacje są zapisane natywnie, obok węzłów[^neo-graphdb]. Każdy węzeł wskazuje bezpośrednio swoich sąsiadów (index-free adjacency). Przejście po relacji nie wymaga więc wyszukiwania w indeksie, a czas zapytania zależy od ilości przetworzonych danych[^neo-native]. Cypher jest deklaratywny jak SQL. Wzorce zapisuje się składnią przypominającą rysunek, np. `(a)-[:SHIPS_TO]->(b)`, a zapytania są często krótsze niż w SQL[^neo-cypher]. Cypher obsługuje większość obowiązkowych cech standardu ISO/IEC 39075:2024 (GQL)[^neo-gql]. Model grafu można zmieniać wraz z aplikacją[^neo-graphdb].

### Wady

Edycja Community nie ma klastra, kopii zapasowych online, kontroli dostępu opartej na rolach ani baz poza systemową i domyślną[^neo-intro]. Z ograniczeń integralności ma tylko unikalność właściwości. Ograniczenia istnienia, typu i klucza są w edycji Enterprise, a ograniczeń CHECK nie ma wcale[^neo-constraints]. Właściwość nie może przechowywać mapy, tylko wartość prostą albo jednorodną listę[^neo-types]. Zagnieżdżony JSON trzeba więc zapisać jako tekst. Tak Neo4j przechowuje zdarzenia `audit_event_` i dlatego pomija scenariusze JSON (rozdz. 9). Community wykonuje zapytania tylko środowiskiem slotted, a środowiska potokowe i równoległe są w edycji Enterprise[^neo-intro].

### Udogodnienia

Słowo kluczowe `SHORTEST` (od wersji 5.21) znajduje najkrótsze ścieżki, a `ANY` sprawdza osiągalność węzłów[^neo-shortest]. Typ `POINT` przechowuje współrzędne WGS-84 lub kartezjańskie. Indeksuje się go indeksem punktowym, a odległość liczy funkcja `point.distance()`[^neo-spatial]. Indeksy zakresowe, tekstowe, punktowe oraz etykiet i typów relacji planista wybiera sam. Indeksy pełnotekstowe i wektorowe służą do wyszukiwania leksykalnego i semantycznego[^neo-indexes]. `EXPLAIN` pokazuje plan bez wykonania zapytania, a `PROFILE` wykonuje je i podaje rzeczywiste wartości, np. liczbę odwołań do bazy (db hits)[^neo-plans]. Biblioteka APOC Core ma ponad 450 procedur i funkcji, a wtyczkę Graph Data Science instaluje się osobno[^neo-intro]. `neo4j-admin database import` zapisuje dane z plików CSV wprost w natywnym formacie bazy[^neo-import].

### Ograniczenia

Domyślny format magazynu w Community (aligned) mieści do 2^35^ (ok. 34 mld) węzłów i tyle samo relacji, 2^36^ właściwości i 65 536 typów relacji[^neo-formats]. Community ma tylko bazę systemową i jedną bazę domyślną[^neo-intro]. Kopię zapasową, czyli zrzut `neo4j-admin database dump`, wykonuje się przy zatrzymanym serwerze[^neo-dump]. Import `neo4j-admin` też wymaga wyłączenia bazy, a import przyrostowy jest tylko w edycji Enterprise[^neo-import]. Szybkość zależy od pamięci. Pamięć podręczna stron trzyma dane z dysku i zwykle opłaca się zmieścić w niej jak najwięcej danych i indeksów[^neo-memory].

### Awaryjność

Dziennik transakcji zapisuje wszystkie zmiany danych, indeksów i ograniczeń[^neo-txlog]. Punkt kontrolny zapisuje oczekujące zmiany z pamięci na dysk, domyślnie co 15 min lub co 100 000 transakcji. Po awarii baza przy starcie powtarza transakcje, których nie utrwalił jeszcze punkt kontrolny[^neo-checkpoint]. Edycja Community nie ma klastra ani automatycznego przełączania na inny serwer. Kopie zapasowe wykonuje tylko offline[^neo-intro][^neo-dump]. W edycji Enterprise baza przyjmuje zapisy, dopóki działa większość jej serwerów głównych. Trzy takie serwery przetrwają awarię jednego, a pięć – awarię dwóch[^neo-cluster].

### Bezpieczeństwo

Edycja Community uwierzytelnia użytkowników natywnie, hasłem. Nie ma w niej ról, a każdy użytkownik ma uprawnienia administratora[^neo-users]. Kontrola dostępu oparta na rolach i do podgrafu, integracja z LDAP i Active Directory oraz Kerberos są tylko w edycji Enterprise[^neo-intro]. Połączenia przez Bolt i HTTPS szyfruje TLS[^neo-ssl].

### Migracje

`neo4j-admin database import` ładuje pliki CSV do nowej, pustej bazy przy wyłączonym serwerze. Użytkownicy bez uprawnień administratora mogą wczytać CSV poleceniem Cypher `LOAD CSV`[^neo-import]. W projekcie Neo4j dostaje dane pierwszym sposobem (rozdz. 3). Edycja Community potrafi też odtworzyć bazę ze zrzutu[^neo-backup]. Z wersji 5.26 LTS bazę można zaktualizować online do każdej wersji 2025–2026. Przejście z 4.4 na 5.26 wymaga migracji baz na nowy serwer[^neo-upgrade].

### Integracje

Klienci łączą się z bazą protokołem Bolt. Oficjalne sterowniki są dla .NET, Go, Javy, JavaScriptu i Pythona[^neo-intro]. Interfejs HTTP wykonuje polecenia Cypher przez żądania HTTP, ale dokumentacja zaleca sterownik, jeśli istnieje dla danego języka[^neo-http]. Konektor Kafka zapisuje w bazie komunikaty z tematów Kafki i publikuje do nich zmiany z bazy[^neo-kafka]. Jest też konektor Apache Spark[^neo-spark]. Przechwytywanie zmian (Change Data Capture) jest tylko w edycji Enterprise[^neo-intro].

### Skalowalność

Edycja Community działa na jednym serwerze, więc skaluje się tylko w pionie[^neo-intro]. Pomaga tu duża pamięć podręczna stron[^neo-memory]. W edycji Enterprise klaster rozkłada odczyty na serwery pomocnicze (secondaries)[^neo-cluster]. Bazy złożone (composite databases), także z edycji Enterprise, pozwalają jednym zapytaniem Cypher czytać dane podzielone między wiele baz, np. shardy o wspólnym modelu[^neo-composite].

### Obszary biznesowe

Według producenta Neo4j używają tysiące organizacji, od startupów po firmy z listy Fortune 500[^neo-company]. Producent wymienia wykrywanie oszustw, rekomendacje w czasie rzeczywistym, łańcuchy dostaw, zarządzanie tożsamością i dostępem, sieci i operacje IT oraz grafy wiedzy[^neo-usecases]. W Bagażomacie Neo4j zapisuje sieć przesyłek między automatami jako relacje `SHIPS_TO` i odpowiada na pytanie o osiągalność automatów (scenariusz R8), ale edycja Community bez ról, ograniczeń CHECK i klastra nie nadaje się na główną bazę aplikacji, więc Neo4j występuje tylko w pomiarach.

[^neo-graphdb]: Neo4j, „What is a graph database”, <https://neo4j.com/docs/getting-started/graph-database/>.
[^neo-intro]: Dokumentacja Neo4j 5, Operations Manual, „Introduction”, <https://neo4j.com/docs/operations-manual/5/introduction/>.
[^neo-company]: Neo4j, „About Neo4j”, <https://neo4j.com/company/>.
[^neo-versions]: Neo4j, „Neo4j Supported Versions”, <https://support.neo4j.com/s/article/115013134648-Neo4j-Supported-Versions>.
[^neo-lts]: Neo4j, „Neo4j v5 long-term support and the continued evolution”, <https://neo4j.com/blog/developer/neo4j-v5-lts-evolution/>.
[^neo-native]: Neo4j, „Native vs. Non-Native Graph Database”, <https://neo4j.com/blog/cypher-and-gql/native-vs-non-native-graph-technology/>.
[^neo-cypher]: Dokumentacja Neo4j 5, Cypher Manual, „Cypher overview”, <https://neo4j.com/docs/cypher-manual/5/introduction/cypher-overview/>.
[^neo-gql]: Dokumentacja Neo4j 5, Cypher Manual, „GQL conformance”, <https://neo4j.com/docs/cypher-manual/5/appendix/gql-conformance/>.
[^neo-constraints]: Dokumentacja Neo4j 5, Cypher Manual, „Constraints”, <https://neo4j.com/docs/cypher-manual/5/constraints/>.
[^neo-types]: Dokumentacja Neo4j 5, Cypher Manual, „Property, structural, and constructed values”, <https://neo4j.com/docs/cypher-manual/5/values-and-types/property-structural-constructed/>.
[^neo-shortest]: Dokumentacja Neo4j 5, Cypher Manual, „Shortest paths”, <https://neo4j.com/docs/cypher-manual/5/patterns/shortest-paths/>.
[^neo-spatial]: Dokumentacja Neo4j 5, Cypher Manual, „Spatial values”, <https://neo4j.com/docs/cypher-manual/5/values-and-types/spatial/>.
[^neo-indexes]: Dokumentacja Neo4j 5, Cypher Manual, „Indexes”, <https://neo4j.com/docs/cypher-manual/5/indexes/>.
[^neo-plans]: Dokumentacja Neo4j 5, Cypher Manual, „Execution plans”, <https://neo4j.com/docs/cypher-manual/5/planning-and-tuning/execution-plans/>.
[^neo-import]: Dokumentacja Neo4j 5, Operations Manual, „Import”, <https://neo4j.com/docs/operations-manual/5/tools/neo4j-admin/neo4j-admin-import/>.
[^neo-formats]: Dokumentacja Neo4j 5, Operations Manual, „Store formats”, <https://neo4j.com/docs/operations-manual/5/database-internals/store-formats/>.
[^neo-dump]: Dokumentacja Neo4j 5, Operations Manual, „Back up an offline database”, <https://neo4j.com/docs/operations-manual/5/backup-restore/offline-backup/>.
[^neo-memory]: Dokumentacja Neo4j 5, Operations Manual, „Memory configuration”, <https://neo4j.com/docs/operations-manual/5/performance/memory-configuration/>.
[^neo-txlog]: Dokumentacja Neo4j 5, Operations Manual, „Transaction logging”, <https://neo4j.com/docs/operations-manual/5/database-internals/transaction-logs/>.
[^neo-checkpoint]: Dokumentacja Neo4j 5, Operations Manual, „Checkpointing and log pruning”, <https://neo4j.com/docs/operations-manual/5/database-internals/checkpointing/>.
[^neo-cluster]: Dokumentacja Neo4j 5, Operations Manual, „Clustering: Introduction”, <https://neo4j.com/docs/operations-manual/5/clustering/introduction/>.
[^neo-users]: Dokumentacja Neo4j 5, Operations Manual, „Manage users”, <https://neo4j.com/docs/operations-manual/5/authentication-authorization/manage-users/>.
[^neo-ssl]: Dokumentacja Neo4j 5, Operations Manual, „SSL framework”, <https://neo4j.com/docs/operations-manual/5/security/ssl-framework/>.
[^neo-backup]: Dokumentacja Neo4j 5, Operations Manual, „Backup and restore”, <https://neo4j.com/docs/operations-manual/5/backup-restore/>.
[^neo-upgrade]: Neo4j, „Upgrade and Migration Guide”, <https://neo4j.com/docs/upgrade-migration-guide/current/>.
[^neo-http]: Neo4j, „HTTP API”, <https://neo4j.com/docs/http-api/current/>.
[^neo-kafka]: Neo4j, „Neo4j Connector for Kafka”, <https://neo4j.com/docs/kafka/current/>.
[^neo-spark]: Neo4j, „Neo4j Connector for Apache Spark”, <https://neo4j.com/docs/spark/current/>.
[^neo-composite]: Dokumentacja Neo4j 5, Operations Manual, „Composite databases: concepts”, <https://neo4j.com/docs/operations-manual/5/database-administration/composite-databases/concepts/>.
[^neo-usecases]: Neo4j, „Use Cases”, <https://neo4j.com/use-cases/>.

## Porównanie czterech SZBD

Tabela zestawia najważniejsze różnice. Każda komórka streszcza opis z tego rozdziału, a źródła podano przy opisach.

| Cecha | PostgreSQL 17 | MySQL 8.4 LTS | MongoDB 8.0 | Neo4j 5.26 Community |
|---|---|---|---|---|
| Model danych | obiektowo-relacyjny | relacyjny | dokumentowy (BSON) | graf właściwości |
| Licencja | PostgreSQL, podobna do BSD i MIT | GPL lub komercyjna | SSPL | GPLv3 |
| Język zapytań | SQL | SQL | zapytania o dokumenty, potok agregacji | Cypher, większość obowiązkowych cech GQL |
| Transakcje | ACID, domyślnie READ COMMITTED | ACID w InnoDB, domyślnie REPEATABLE READ | atomowy dokument; ACID na wielu dokumentach, ale nie na samodzielnym serwerze | ACID |
| Integralność | PK, FK, UNIQUE, CHECK, EXCLUDE | PK, FK, UNIQUE, CHECK; wykluczenia przez wyzwalacze | walidacja pól dokumentu, indeksy unikalne | tylko unikalność właściwości |
| Awaryjność | WAL, PITR, replikacja; przełączanie narzędziem zewnętrznym | redo, doublewrite, binlog; InnoDB Cluster przełącza sam | dziennik i punkty kontrolne; zbiór replik przełącza sam | dziennik transakcji; kopia tylko offline |
| Bezpieczeństwo | role, RLS, SCRAM, TLS | role, SHA-256, TLS, szyfrowanie InnoDB | RBAC domyślnie wyłączony, SCRAM, TLS; szyfrowanie plików i audyt w Enterprise | brak ról, każdy użytkownik jest administratorem |
| Migracje | pg_dump, pg_upgrade, transakcyjny DDL | mysqldump, MySQL Shell, clone; DDL nietransakcyjny | mongodump, mongoimport, Relational Migrator | import CSV i zrzut offline, LOAD CSV |
| Integracje | libpq, FDW, dekodowanie logiczne | sterowniki Connector, X DevAPI | 13 sterowników, strumienie zmian, Kafka | Bolt, 5 sterowników, HTTP, Kafka, Spark |
| Skalowalność | zapytania równoległe, partycje, repliki do odczytu | partycje, repliki, Group Replication do 9 serwerów | wbudowany sharding, repliki do odczytu | jeden serwer, tylko w pionie |
| JSON | jsonb z indeksami | JSON z indeksem funkcyjnym i wielowartościowym | natywne dokumenty | brak map we właściwościach |
| Rola w projekcie | pomiary i aplikacja Bagażomat | pomiary | pomiary | pomiary bez scenariuszy JSON |

: Porównanie czterech SZBD. Źródło: opracowanie własne na podstawie źródeł podanych w tym rozdziale.
