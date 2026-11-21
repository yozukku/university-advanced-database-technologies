# Scenariusze testowe

Katalog obejmuje 32 scenariusze. 26 scenariuszy podstawowych (6 C, 8 R, 6 U, 6 D) wykonują wszystkie cztery SZBD. 6 scenariuszy JSON na tabeli `audit_event_` wykonują PostgreSQL, MySQL i MongoDB. Neo4j przechowuje `actor_` i `changes_` jako tekst JSON bez indeksów ścieżek, więc nie wykonuje serii J (rozdz. 9). Regulamin wymaga co najmniej 24 scenariuszy, w tym co najmniej 6 na każdą operację CRUD.

Tabele tego rozdziału powstają automatycznie z katalogu `docs/bench/scenarios.md`, który aplikacja testowa zapisuje z rejestru scenariuszy (`make catalogue`). Ten sam katalog zawiera pełne teksty zapytań każdego SZBD i polecenia DDL indeksów (dodatek C).

## Zasady wspólne

Każdy scenariusz ma w każdym SZBD własną implementację w idiomatycznej postaci: SQL w PostgreSQL i MySQL, wywołania sterownika pymongo w MongoDB i Cypher w Neo4j. Implementacje dostają te same parametry i muszą dać ten sam wynik (rozdz. 5).

- Parametry wybiera selektor scenariusza z plików Parquet danego rozmiaru. Generator losowy ma ziarno złożone z ziarna profilu danych i identyfikatora scenariusza, więc parametry są powtarzalne.
- Liczba operacji i rozmiar partii są takie same dla rozmiarów S, M i L. Pochodzą z `bench/scenarios/ops.yaml`.
- Nowe wiersze dostają identyfikatory powyżej zakresu identyfikatorów danych, a identyfikator dziecka jest stałą funkcją identyfikatora rodzica. Dzięki temu wynik zapisu można porównać między SZBD.
- Zapisy punktowe wykonują jedną transakcję na partię, a zapisy zbiorowe partie do 5000 kluczy celu z jednym zatwierdzeniem na partię (rozdz. 5).

Flagi w tabelach:

- CX — złożony odczyt: złączenie, agregacja, przejście grafu albo zapytanie przestrzenne;
- BA — pomiar w konfiguracjach BASE i IDX; pozostałe scenariusze mierzymy tylko w IDX;
- H1-S, H1-I, H1-U — zbiory SELECT, INSERT i UPDATE hipotezy H1 (rozdz. 11).

Kolumna „Indeks IDX” podaje dla odczytu indeks dodany w IDX, który go obsługuje, a dla zapisu dodane indeksy, które zapis utrzymuje (rozdz. 8).

## Scenariusze podstawowe

@Tab:scenarios-core zawiera 26 scenariuszy podstawowych. Odczyty R1–R8 odpowiadają zapytaniom aplikacji Bagażomat i raportom sieci przechowalni. Zapisy obejmują rejestrację, rezerwację, nadanie przesyłki, zmiany statusów i usuwanie danych z zależnościami.

{{ dataset("scenarios-core", "Scenariusze podstawowe we wszystkich czterech SZBD") }}

## Scenariusze JSON

@Tab:scenarios-json zawiera 6 scenariuszy na dzienniku zdarzeń `audit_event_` z migawką aktora `actor_` i listą zmian `changes_` w JSON. Wynikają one z obowiązków RODO (dostęp do danych osoby, pseudonimizacja) i retencji dziennika.

{{ dataset("scenarios-json", "Scenariusze JSON w PostgreSQL, MySQL i MongoDB") }}

## Konfiguracje pomiaru

W konfiguracji IDX mierzymy wszystkie scenariusze, a w BASE tylko scenariusze z flagą BA: 11 podstawowych i 4 JSON. Na jeden rozmiar daje to 122 komórki IDX (26 × 4 SZBD i 6 × 3 SZBD) i 56 komórek BASE (11 × 4 i 4 × 3). Komórka ma trzy przebiegi mierzone. Scenariusze z flagą BA tworzą zbiory hipotezy H1 oraz dwa scenariusze poza rozstrzygnięciem, U3 i J5 (rozdz. 11).
