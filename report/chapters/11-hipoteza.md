# Hipoteza badawcza H1

## Sformułowanie

Na ocenę 5.0 regulamin wymaga sformułowania i weryfikacji hipotezy badawczej[^regulamin-h1]. Przyjmujemy hipotezę H1 w brzmieniu z regulaminu:

> Zastosowanie indeksów znacząco poprawia wydajność operacji SELECT kosztem spadku wydajności operacji INSERT i UPDATE.

Hipoteza jest jakościowa. Słowu „znacząco” nie przypisujemy progu liczbowego. Rozstrzygamy kierunek zmiany czasu, a dla odczytów także to, czy plan zapytania korzysta z dodanego indeksu. Wielkość zmian, czyli ilorazy czasów, omawiamy osobno.

## Konfiguracje BASE i IDX

H1 sprawdzamy porównaniem dwóch konfiguracji indeksów na tych samych danych (rozdz. 8):

- BASE to schemat w zaprojektowanej postaci: klucze główne i obce, ograniczenia unikalności i wykluczające, indeksy, które je obsługują, oraz własne indeksy schematu. MongoDB i Neo4j mają ich logiczne odpowiedniki.
- IDX to BASE i sześć dodanych indeksów logicznych: cztery indeksy pomocnicze IX1–IX4, po jednym dla każdego złożonego odczytu z pomiarem przed i po, oraz dwa indeksy JSON, JX1 (osobno dla e-maila i telefonu) i JX2.

| Indeks | Klucz | Obsługuje odczyt | Utrzymują zapisy |
|---|---|---|---|
| IX1 | telefon odbiorcy przesyłki (`shipment_.recipient_phone_`) | R4 | C4, U5 |
| IX2 | status i czas utworzenia zamówienia (`order_.status_`, `created_at_`) | R5 | C3, C4, U1, U3 |
| IX3 | czas utworzenia płatności (`payment_.created_at_`) | R6 | C3, C4, C6 |
| IX4 | czas żądania otwarcia skrytki (`cell_opening_.requested_at_`) | R7 | C2 |
| JX1 | e-mail i telefon w migawce aktora (`audit_event_.actor_`) | J2 | J1, J5 |
| JX2 | nazwy pól i nowe wartości w liście zmian (`audit_event_.changes_`) | J4 | J1 |

Ten sam logiczny zestaw indeksów istnieje we wszystkich czterech SZBD. Wyjątkiem są JX1 i JX2 w Neo4j: Neo4j przechowuje `actor_` i `changes_` jako tekst JSON i nie indeksuje ich ścieżek (rozdz. 9). Polecenia DDL każdego SZBD zawiera dodatek C.

## Zbiory scenariuszy

H1 obejmuje trzy zbiory scenariuszy z katalogu (rozdz. 6). Każdy scenariusz z tych zbiorów mierzymy w konfiguracjach BASE i IDX.

| Zbiór | Operacja | Scenariusze | Związek z dodanymi indeksami |
|---|---|---|---|
| H1-S | SELECT | R4, R5, R6, R7, J2, J4 | każdy odczyt ma dodany indeks, który może go obsłużyć |
| H1-I | INSERT | C2, C3, C4, C6, J1 | każdy zapis wstawia wpisy co najmniej jednego dodanego indeksu |
| H1-U | UPDATE | U1, U5 | zapis znajduje wiersze po kluczu głównym i zmienia kolumnę dodanego indeksu: U1 status zamówienia (IX2), U5 telefon odbiorcy (IX1) |

W PostgreSQL, MySQL i MongoDB zbiory liczą 13 scenariuszy. Neo4j nie wykonuje scenariuszy JSON, więc ma 10 scenariuszy bez J1, J2 i J4.

Scenariusze U3 i J5 mierzymy w BASE i IDX, ale nie wchodzą do rozstrzygnięcia. Oba są operacjami UPDATE, które najpierw szukają swoich wierszy. U3 szuka nieopłaconych zamówień po terminie płatności (`status_ = 'AWAITING_PAYMENT'`), a IX2 zaczyna się od kolumny `status_`. J5 szuka zdarzeń osoby po e-mailu lub telefonie, czyli przez JX1. W IDX oba mogą więc działać szybciej. Opisujemy je jako nazwany wyjątek „indeks przyspiesza wyszukanie wierszy do UPDATE”: U3 w rozdz. 8, J5 w rozdz. 9.

Zbiory ustaliliśmy przed pierwszym pomiarem i nie zmieniamy ich na podstawie zmierzonych czasów. Kontrola katalogu (`make catalogue CHECK=1`) sprawdza, że flagi pomiaru BASE i IDX w rejestrze scenariuszy to dokładnie te trzy zbiory oraz U3 i J5. Zapis, którego koszt utrzymania indeksu jest mały wobec kosztu zatwierdzenia transakcji, zostaje w swoim zbiorze. Jego wynik, na przykład iloraz bliski 1 albo odwrotny kierunek, omawiamy w analizie. Zbiór może się zmienić tylko z powodu poprawności, czyli po zmianie zapytania lub znaczenia scenariusza, przed pomiarami pełnymi. Taką zmianę zapisujemy w `results/notes.md`.

## Metoda weryfikacji

Każdy scenariusz z trzech zbiorów mierzymy w każdym SZBD, które go wykonuje, dla rozmiarów S, M i L, w konfiguracjach BASE i IDX. Pomiary startują z tej samej odtworzonej migawki danych. Odczyt ma jeden przebieg rozgrzewający i trzy mierzone. Zapis ma trzy mierzone przebiegi i przed każdym odtwarzamy migawkę (rozdz. 5). Dla każdego scenariusza, SZBD i rozmiaru wyznaczamy:

- średnią z trzech przebiegów BASE i średnią z trzech przebiegów IDX;
- iloraz średnich IDX / BASE i kierunek zmiany: poniżej 1 IDX działa szybciej, powyżej 1 wolniej;
- dla odczytu wynik kontroli planu: czy plan wykonania IDX (EXPLAIN) używa dodanego indeksu. Plany zapisujemy dla rozmiarów S i L, a rozmiar M daje tylko czasy (rozdz. 8).

Nie stosujemy progu liczbowego, testu statystycznego ani porównania zakresów min–max. Regulamin wymaga sformułowania i weryfikacji hipotezy, a jakościowa reguła odpowiada jakościowej hipotezie.

Przebieg, który przekroczy limit 600 s, zapisujemy jako „> 600 s” (rozdz. 5). Jeśli tak skończy się przebieg BASE, komórka nie ma średniej ani ilorazu i liczy się jako „BASE > 600 s”. Jej kierunek to „IDX szybciej”, bo każdy przebieg IDX musi skończyć się przed limitem: przekroczenie limitu w IDX przerywa pomiary, a liczbę operacji lub próg daty scenariusza zmniejszamy we wszystkich SZBD i rozmiarach. Taką komórkę wymieniamy z nazwy razem ze zmierzonymi czasami.

## Reguła rozstrzygnięcia

Komórka, czyli para scenariusza H1 i SZBD dla rozmiaru L, potwierdza hipotezę, gdy:

- dla H1-S plan IDX używa dodanego indeksu, a średnia IDX jest niższa od średniej BASE albo komórka ma „BASE > 600 s”;
- dla H1-I i H1-U średnia IDX jest wyższa od średniej BASE.

Komórka nie potwierdza hipotezy, gdy średnie są równe, gdy plan IDX odczytu nie używa dodanego indeksu albo gdy zapis ma „BASE > 600 s”, bo wtedy IDX działa szybciej.

Werdykt dla jednego SZBD obejmuje jego komórki H1 dla rozmiaru L:

- *potwierdzona*, gdy wszystkie komórki potwierdzają hipotezę;
- *obalona*, gdy co najmniej jedna jej nie potwierdza. Wymieniamy wtedy te komórki.

Werdykt ogólny brzmi *potwierdzona* tylko wtedy, gdy werdykty wszystkich czterech SZBD brzmią *potwierdzona*. W przeciwnym razie brzmi *obalona*, a rozdział wymienia SZBD, dla których hipoteza się nie potwierdza.

Werdykt wymaga kompletnych danych. Każda komórka H1 dla rozmiaru L musi mieć pomiary BASE i IDX, a każda komórka H1-S także plany BASE i IDX. Bez tego werdykt brzmi „weryfikacja po pomiarach L”. Wyniki S i M pokazujemy w tabeli dowodów z ilorazem i kierunkiem, a rozstrzygnięcie opiera się na rozmiarze L. Średnie, ilorazy, kierunki, kontrolę planów i werdykty aplikacja testowa zapisuje w `results/h1.json`, a ten rozdział cytuje je bez zmian.

Koszt indeksów uzupełniają czas budowy i rozmiar każdego dodanego indeksu w każdym SZBD (rozdz. 8 i 9). Wyjątki od oczekiwanego kierunku, na przykład zapis, w którym koszt utrzymania indeksu ginie w koszcie zatwierdzenia transakcji, omawiamy jako część analizy.

## Wyniki dla rozmiaru L

@Tab:h1-L zawiera wszystkie komórki H1 dla rozmiaru L w postaci z `results/h1.json`: średnie BASE i IDX, iloraz IDX / BASE, kierunek zmiany, kontrolę planu odczytu i wynik reguły rozstrzygnięcia. Kontrola planu dotyczy tylko odczytów, więc zapisy mają w tej kolumnie „—”. Wykresy par BASE i IDX zawierają rozdz. 8 i 9.

{{ dataset("h1-L", "Komórki H1 dla rozmiaru L") }}

## Werdykt

@Tab:h1-verdicts podaje werdykt dla każdego SZBD i werdykt ogólny z `results/h1.json` oraz komórki, które nie potwierdzają hipotezy.

{{ dataset("h1-verdicts", "Werdykty hipotezy H1") }}

## Wyniki dla rozmiarów S i M

@Tab:h1-S i @tab:h1-M pokazują te same komórki dla rozmiarów S i M. Nie wchodzą one do werdyktu. Dla rozmiaru M nie zapisujemy planów, więc odczyty nie mają kontroli planu ani wyniku reguły.

{{ dataset("h1-S", "Komórki H1 dla rozmiaru S") }}

{{ dataset("h1-M", "Komórki H1 dla rozmiaru M") }}

[^regulamin-h1]: Politechnika Krakowska, „Zaawansowane technologie baz danych – Regulamin zajęć”, rok akademicki 2026/27, studia niestacjonarne, §3.
