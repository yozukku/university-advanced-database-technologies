# Dane półstrukturalne (JSON)

## Model `audit_event_` w trzech SZBD

Dziennik zdarzeń `audit_event_` (rozdz. 3) ma dwie kolumny półstrukturalne. `actor_` to migawka wykonawcy: obiekt z polem `kind` i tymi danymi, które były znane w chwili zdarzenia, np. e-mail klienta albo telefon odbiorcy przesyłki. `changes_` to tablica zmienionych pól w postaci `{f, old, new}`. Zestaw pól obu kolumn zależy od rodzaju zdarzenia i wykonawcy, więc nie pasuje do stałego zestawu kolumn.

Każdy SZBD przechowuje je inaczej:

- PostgreSQL używa typu `jsonb`, czyli postaci binarnej z rozłożonymi kluczami. Operatory `->>`, `?` i `@>` czytają klucze i zawartość tablic.
- MySQL używa binarnego typu `JSON`. Pola czytają operatory i funkcje ścieżek, np. `->>` i `JSON_CONTAINS`. Indeks wielowartościowy JX2 korzysta z dodatkowej kolumny `changes_new_` z wartościami `new` tablicy zmian (rozdz. 3).
- MongoDB zapisuje zdarzenie jako dokument BSON w kolekcji `auditEvents`. Aktor to dokument osadzony, a zmiany to tablica dokumentów, więc zapytania i indeksy odwołują się do ścieżek, np. `actor.email` czy `changes.f`.
- Neo4j przechowuje `actor` i `changes` jako tekst JSON we właściwościach węzła `AuditEvent` (podrozdział „Ograniczenie Neo4j”).

## Scenariusze JSON

Scenariusze J1–J6 działają na dzienniku zdarzeń `audit_event_` (rozdz. 3) w PostgreSQL, MySQL i MongoDB. Neo4j przechowuje pola `actor_` i `changes_` jako tekst JSON i nie indeksuje ich ścieżek, więc nie wykonuje serii J. Katalog scenariuszy zawiera rozdz. 6. Wykresy od @fig:J1 do @fig:J6 pokazują średnie czasy w konfiguracji IDX dla rozmiarów S, M i L.

{{ fig("J1", "Czas zapisu J1 (dopisanie zdarzeń audytu) w trzech SZBD") }}

{{ fig("J2", "Czas odczytu J2 (RODO art. 15: zdarzenia osoby według e-maila lub telefonu) w trzech SZBD") }}

{{ fig("J3", "Czas odczytu J3 (istnienie kluczy JSON) w trzech SZBD; skala logarytmiczna") }}

{{ fig("J4", "Czas odczytu J4 (element tablicy zmian) w trzech SZBD") }}

{{ fig("J5", "Czas aktualizacji J5 (RODO art. 17: pseudonimizacja) w trzech SZBD") }}

{{ fig("J6", "Czas usuwania J6 (retencja zdarzeń audytu) w trzech SZBD; skala logarytmiczna") }}

J3 nie ma indeksu, który mógłby go obsłużyć, i czyta całą tabelę. Przy L trwa {{ mean("J3", "pg", "idx") }} ms w PostgreSQL, {{ mean("J3", "mysql", "idx") }} ms w MySQL i {{ mean("J3", "mongo", "idx") }} ms w MongoDB. Plan PostgreSQL dzieli przegląd tabeli między proces główny i dwa procesy robocze (`Parallel Seq Scan`), a MySQL i MongoDB przeglądają ją w jednym wątku zapytania. J6 wyszukuje stare zdarzenia po dacie i usuwa je partiami po kluczu głównym. Mierzymy go tylko w IDX, więc usunięcie zdarzenia usuwa też jego wpisy z indeksów JX1 i JX2. W obu scenariuszach PostgreSQL jest najszybszy.

## Indeksy JSON: BASE i IDX

IDX dodaje dwa indeksy JSON. JX1 indeksuje e-mail i telefon w migawce aktora i obsługuje odczyt J2. JX2 indeksuje nazwy pól i nowe wartości w liście zmian i obsługuje odczyt J4. PostgreSQL używa indeksów wyrażeń B-drzewa dla JX1 i indeksu GIN `jsonb_path_ops` dla JX2. MySQL używa indeksów funkcyjnych dla JX1 i indeksu wielowartościowego dla JX2. MongoDB używa indeksów pól osadzonych dla JX1 i indeksu wielokluczowego tablicy dla JX2.

Budowa tych indeksów się różni:

- W PostgreSQL JX1 to zwykłe B-drzewo na wyniku wyrażenia `actor_ ->> 'email'` (i osobno `'phone'`). Obsługuje równość z tym samym wyrażeniem i ma jeden wpis na wiersz. JX2 to indeks GIN, który dla każdego elementu tablicy `changes_` zapisuje skróty ścieżek razem z wartościami i obsługuje zawieranie `@>`. Ma więc wiele wpisów na wiersz.
- W MySQL indeks funkcyjny działa tylko wtedy, gdy zapytanie powtarza jego wyrażenie dokładnie, z tym samym `CAST` i `COLLATE`. Dlatego J2 i J5 porównują `cast(actor_ ->> '$.email' as char(320) character set utf8mb4) collate utf8mb4_0900_bin`, a nie samo `actor_ ->> '$.email'`. Indeks wielowartościowy JX2 ma wpis dla każdej wartości tablicy `changes_new_` i obsługuje `MEMBER OF`. Parę `{f, new}` sprawdza potem `JSON_CONTAINS`.
- W MongoDB JX1 to dwa indeksy częściowe, tylko dla zdarzeń, które mają e-mail albo telefon. JX2 to indeks złożony `{changes.f, changes.new}`, w którym każdy element tablicy daje osobny wpis.

@Tab:ba-json-L zestawia średnie czasy scenariuszy JSON z flagą BA w obu konfiguracjach dla rozmiaru L. J2 i J4 należą do zbioru H1-S, a J1 do zbioru H1-I (rozdz. 11). J5 nie wchodzi do weryfikacji H1: wyszukuje zdarzenia osoby po e-mailu lub telefonie, czyli przez JX1, więc indeks może przyspieszyć wyszukanie wierszy do aktualizacji. Wykresy od @fig:J1-ba do @fig:J5-ba pokazują pary dla rozmiarów S, M i L.

{{ dataset("ba-json-L", "Średnie czasy scenariuszy JSON w konfiguracjach BASE i IDX dla rozmiaru L") }}

{{ fig("J1-ba", "J1 (dopisanie zdarzeń audytu) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J2-ba", "J2 (RODO art. 15) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J4-ba", "J4 (element tablicy zmian) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J5-ba", "J5 (RODO art. 17: pseudonimizacja) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

J2 daje największą różnicę w projekcie. W BASE każdy SZBD przegląda wszystkie zdarzenia, aby znaleźć nieliczne zdarzenia jednej osoby. Przy L to {{ mean("J2", "pg", "base") }} ms w PostgreSQL, {{ mean("J2", "mysql", "base") }} ms w MySQL i {{ mean("J2", "mongo", "base") }} ms w MongoDB. PostgreSQL i tu przegląda tabelę równolegle w trzech procesach. Z JX1 każdy SZBD czyta tylko wpisy szukanego e-maila i telefonu. Iloraz IDX / BASE wynosi {{ ratio("J2", "pg") }} w PostgreSQL, {{ ratio("J2", "mysql") }} w MySQL i {{ ratio("J2", "mongo") }} w MongoDB.

J4 zyskuje mniej: iloraz wynosi {{ ratio("J4", "pg") }} w PostgreSQL, {{ ratio("J4", "mysql") }} w MySQL i {{ ratio("J4", "mongo") }} w MongoDB. JX2 nie zawiera daty zdarzenia. Indeks zwraca więc zdarzenia ze zmianą statusu na `CANCELLED` ze wszystkich miesięcy, a warunek na miesiąc SZBD sprawdza dopiero na odczytanych wierszach. PostgreSQL w BASE czyta tabelę najszybciej z trzech SZBD, więc jego względny zysk jest najmniejszy.

J1 pokazuje koszt JX1 i JX2 przy zapisie. Iloraz wynosi {{ ratio("J1", "pg") }} w PostgreSQL, {{ ratio("J1", "mysql") }} w MySQL i {{ ratio("J1", "mongo") }} w MongoDB. Każde nowe zdarzenie dodaje wpisy do indeksów JX1 i do JX2, a JX2 ma wpis dla każdego elementu listy zmian. GIN w PostgreSQL ma wyłączone `fastupdate`, więc jego aktualizacja mieści się w mierzonym zapisie, a nie odkłada się na później. Największy koszt ma MySQL, którego indeksy JSON są też największe (@tab:build-json).

J5 to nazwany wyjątek „indeks przyspiesza wyszukanie wierszy do UPDATE”. Pseudonimizacja najpierw szuka zdarzeń 100 osób po e-mailu lub telefonie. W BASE to pełny przegląd tabeli, a w IDX odczyt JX1 (@tab:access-json-L). Iloraz wynosi {{ ratio("J5", "pg") }} w PostgreSQL, {{ ratio("J5", "mysql") }} w MySQL i {{ ratio("J5", "mongo") }} w MongoDB, choć zamiana e-maila na pseudonim i usunięcie telefonu zmienia też wpisy JX1.

## Ścieżki dostępu

@Tab:access-json-L pokazuje plany BASE i IDX dla rozmiaru L. Dla J2 i J4 to plan całego zapytania, a dla J5 plan zapytania, które wyszukuje zdarzenia do zmiany. Kolumny mają to samo znaczenie co w rozdz. 8.

{{ dataset("access-json-L", "Ścieżki dostępu i przejrzane wiersze w planach scenariuszy JSON dla rozmiaru L") }}

Plany IDX używają indeksów JSON we wszystkich trzech SZBD. W BASE J2 to `Seq Scan` w PostgreSQL, `ALL` w MySQL i `COLLSCAN` w MongoDB, czyli {{ examined("J2", "pg", "base") }} przejrzanych wierszy w PostgreSQL. W IDX warunek `OR` na e-mailu i telefonie łączy dwa indeksy JX1: `Bitmap Index Scan` w PostgreSQL, `index_merge` w MySQL i dwa etapy `IXSCAN` w MongoDB. Każdy SZBD przegląda wtedy tylko te wiersze, które zwraca. W J4 wszystkie trzy SZBD czytają w IDX tę samą liczbę wpisów JX2, {{ examined("J4", "pg", "idx") }}: to zdarzenia ze zmianą na `CANCELLED` ze wszystkich miesięcy.

## Rozmiar i czas budowy indeksów JSON

@Tab:build-json podaje czas budowy i rozmiar indeksów JX1 i JX2 dla każdego rozmiaru danych. JX1 to w każdym SZBD dwa indeksy, osobno dla e-maila i telefonu. Rozmiar mierzymy tak samo jak w rozdz. 8.

{{ dataset("build-json", "Czas budowy i rozmiar indeksów JSON JX1 i JX2") }}

GIN `jsonb_path_ops` w PostgreSQL to najmniejszy indeks JX2, bo przechowuje skróty ścieżek z wartościami, a nie same wartości. W MySQL największe są indeksy funkcyjne JX1: klucz e-maila to `CHAR(320)` w `utf8mb4`, a indeks ma wpis także dla zdarzeń bez e-maila. Indeksy częściowe JX1 w MongoDB pomijają zdarzenia bez danego pola, dlatego indeks telefonu jest wielokrotnie mniejszy od indeksu e-maila.

## Ograniczenie Neo4j

Właściwość węzła w Neo4j może być wartością prostą albo listą wartości prostych, ale nie mapą. Migawka aktora i lista zmian są zagnieżdżone, więc model grafowy zapisuje je jako tekst JSON (rozdz. 3). Cypher bez rozszerzeń nie czyta klucza z takiego tekstu, a indeks Neo4j obejmuje całą wartość właściwości, nie ścieżkę w jej treści. Scenariusze J2–J5 wymagałyby więc parsowania tekstu każdego zdarzenia, np. procedurami biblioteki APOC, której nie instalujemy, albo innego modelu: pól aktora jako osobnych właściwości i zmian jako osobnych węzłów. Drugi wariant nie jest już modelem danych półstrukturalnych. Dlatego Neo4j nie wykonuje serii J, a w zbiorach H1 ma 10 scenariuszy zamiast 13 (rozdz. 11).

## Zastosowanie w aplikacji Bagażomat

Aplikacja Bagażomat (rozdz. 4) zapisuje zdarzenie `audit_event_` przy każdej zmianie biznesowej, w tej samej transakcji co zmiana: utworzeniu, opłaceniu, anulowaniu i wygaszeniu zamówienia, zwrocie, pozostawieniu i odbiorze bagażu oraz przy zmianach przesyłki z symulatora. Komponent `AuditWriter` buduje `actor_` z danych zalogowanego użytkownika (klient: id Keycloak i e-mail, odbiorca: także telefon) albo z nazwy zadania systemowego. Hibernate zapisuje obie kolumny jako `jsonb`. „Historia zamówienia” czyta zdarzenia zamówienia, jego rezerwacji i płatności przez indeks schematu `(entity_, entity_id_, at_)`, a z JSON wyciąga tylko rodzaj wykonawcy (`actor_ ->> 'kind'`). Aplikacja nie ma funkcji RODO. Scenariusze J2 i J5 pokazują, jak eksport danych osoby i jej pseudonimizacja działają na tych samych danych i że bez JX1 oba przeglądają cały dziennik.
