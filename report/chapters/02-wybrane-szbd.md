# Wybrane systemy zarządzania bazami danych

Projekt porównuje dwa relacyjne i dwa nierelacyjne SZBD. Każdy z nich opisujemy według tej samej siatki jedenastu punktów. Ta część obejmuje systemy relacyjne PostgreSQL 17 i MySQL 8.4 LTS. Opisy opierają się na dokumentacji i stronach producentów, sprawdzonych 20 listopada 2026 r.

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
