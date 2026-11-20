# Cel i zakres pracy

## Cel pracy

Według regulaminu przedmiotu temat projektu dotyczy porównania dwóch relacyjnych i dwóch nierelacyjnych SZBD na dużych zbiorach danych, testów wydajności i analizy wyników[^regulamin]. Porównujemy więc operacje CRUD w czterech systemach: relacyjnych PostgreSQL 17 i MySQL 8.4 LTS, dokumentowym MongoDB 8.0 i grafowym Neo4j 5.26 Community. Wszystkie dostają te same dane z jednego przypadku biznesowego, sieci przechowalni bagażu Bagażomat. Sprawdzamy, jak czas operacji zależy od rozmiaru danych, modelu danych i indeksów. Na końcu rekomendujemy SZBD dla Bagażomatu (rozdz. 12).

## Zakres pracy

- Opis czterech SZBD według wspólnej siatki: zalety, wady, udogodnienia, ograniczenia, awaryjność, bezpieczeństwo, migracje, integracje, skalowalność i obszary biznesowe (rozdz. 2).
- Jeden deterministyczny zbiór danych w 13 tabelach relacyjnych, w trzech rozmiarach: 500 000, 1 000 000 i 10 000 000 rekordów łącznie. Te same dane trafiają do modelu relacyjnego, dokumentowego i grafowego, a zgodność kopii potwierdzają sumy kontrolne tabel (rozdz. 3).
- Aplikacja testowa, która generuje i ładuje dane, wykonuje scenariusze i rysuje wykresy, oraz aplikacja Bagażomat działająca na PostgreSQL (rozdz. 4).
- 26 scenariuszy CRUD (6 C, 8 R, 6 U, 6 D) we wszystkich czterech SZBD i 6 scenariuszy JSON w PostgreSQL, MySQL i MongoDB. Każdy scenariusz mierzymy trzy razy i podajemy średnią (rozdz. 5–7).
- Indeksy przed i po: konfiguracja BASE, czyli schemat w zaprojektowanej postaci z kluczami, ograniczeniami i ich indeksami, oraz IDX, czyli BASE z czterema indeksami pomocniczymi i dwoma indeksami JSON. Porównanie obejmuje plany zapytań (EXPLAIN) (rozdz. 8).
- Dwie opcje na ocenę 5.0: dane półstrukturalne JSON w tabeli `audit_event_` (rozdz. 9) oraz automatyzacja testów i generowania wyników jednym poleceniem `make full` (rozdz. 10).
- Hipoteza H1 z regulaminu: „Zastosowanie indeksów znacząco poprawia wydajność operacji SELECT kosztem spadku wydajności operacji INSERT i UPDATE”[^regulamin]. Weryfikujemy ją porównaniem średnich czasów BASE i IDX oraz planów zapytań (rozdz. 11).

Poza zakresem pomiarów są testy wielu równoczesnych użytkowników, wpływ ról i szyfrowania na operacje CRUD, replikacja i sharding. Te tematy opisujemy tylko teoretycznie (rozdz. 2).

## Przypadek biznesowy: Bagażomat

Bagażomat to wymyślona sieć automatów do przechowywania bagażu na dworcach, lotniskach i w centrach miast. Każdy automat ma skrytki w trzech rozmiarach: S, M i L. Klient znajduje automat na mapie, rezerwuje skrytkę wybranego rozmiaru na określony czas i płaci. Dostaje kod dostępu (PIN). Skrytkę otwiera zdalnie z aplikacji: najpierw zostawia bagaż, potem go odbiera. Dopóki bagaż nie trafi do skrytki, klient może anulować rezerwację z pełnym zwrotem.

Bagażomat przewozi też bagaż między automatami. Kurier odbiera przesyłkę z automatu nadania i zostawia ją w automacie docelowym. Odbiorcę wskazuje numer telefonu, a przesyłkę odbiera on w aplikacji. Każde otwarcie drzwiczek trafia do dziennika otwarć. Każda zmiana zamówienia, rezerwacji i płatności trafia do historii zdarzeń w formacie JSON. Z tej historii aplikacja pokazuje przebieg zamówienia, a operator odpowiada na żądanie dostępu do danych osobowych[^rodo].

Przypadek stawia bazie typowe wymagania systemu rezerwacji (rozdz. 3):

- rezerwacje jednej skrytki nie mogą nakładać się w czasie;
- suma zwrotów nie może przekroczyć wpłaty;
- wyszukiwanie najbliższych automatów z wolną skrytką wymaga danych przestrzennych;
- historia zdarzeń ma zmienną strukturę, więc pasuje do JSON;
- przesyłki między automatami tworzą sieć, czyli graf.

Każdy z czterech SZBD spełnia te wymagania inaczej. PostgreSQL ma ograniczenia wykluczające i PostGIS, a MySQL zastępuje wykluczenia wyzwalaczami. MongoDB trzyma zamówienie w jednym dokumencie, a Neo4j zapisuje sieć przesyłek jako relacje (rozdz. 2 i 3).

[^regulamin]: Politechnika Krakowska, „Zaawansowane technologie baz danych – Regulamin zajęć”, rok akademicki 2026/27, studia niestacjonarne, §3.
[^rodo]: Rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679 z dnia 27 kwietnia 2016 r. (RODO), art. 15, Dz.Urz. UE L 119 z 4.5.2016, s. 1.
