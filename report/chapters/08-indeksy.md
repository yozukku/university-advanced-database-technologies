# Indeksy i plany zapytań

## Konfiguracje BASE i IDX

Każdy scenariusz z flagą BA mierzymy w dwóch konfiguracjach indeksów na tych samych danych. BASE to schemat w zaprojektowanej postaci: klucze główne i obce, ograniczenia unikalności i wykluczające, indeksy, które je obsługują, oraz własne indeksy schematu. IDX to BASE i cztery indeksy pomocnicze IX1–IX4 oraz dwa indeksy JSON, JX1 i JX2. Każdy indeks pomocniczy obsługuje jeden złożony odczyt: IX1 odczyt R4, IX2 odczyt R5, IX3 odczyt R6, a IX4 odczyt R7. Pełną listę indeksów razem z zapisami, które je utrzymują, zawiera rozdz. 11, a polecenia DDL dodatek C.

W BASE mierzymy 15 scenariuszy z flagą BA, a w IDX wszystkie 32. Każda para BASE i IDX startuje z migawki tych samych danych (rozdz. 5). Ten rozdział pokazuje scenariusze podstawowe. Scenariusze JSON J1, J2, J4 i J5 pokazuje rozdz. 9.

## Czasy BASE i IDX

@Tab:ba-core-L zestawia średnie czasy z trzech przebiegów w obu konfiguracjach dla rozmiaru L. Iloraz IDX / BASE poniżej 1 oznacza, że w IDX scenariusz działa szybciej, a powyżej 1, że wolniej. Wykresy od @fig:R4-ba do @fig:U5-ba pokazują te same pary dla rozmiarów S, M i L, z ilorazem nad każdą parą.

{{ dataset("ba-core-L", "Średnie czasy scenariuszy podstawowych w konfiguracjach BASE i IDX dla rozmiaru L") }}

Odczyty R4–R7 należą do zbioru H1-S, zapisy C2, C3, C4 i C6 do zbioru H1-I, a U1 i U5 do zbioru H1-U (rozdz. 11). U3 nie wchodzi do weryfikacji H1. Wyszukuje nieopłacone zamówienia po terminie płatności przez warunek na kolumnie `status_`, od której zaczyna się IX2, więc indeks może przyspieszyć wyszukanie wierszy do aktualizacji. Przy rozmiarze L U3 działa jednak w IDX wolniej we wszystkich SZBD, np. w PostgreSQL z ilorazem {{ ratio("U3", "pg") }}. PostgreSQL, MySQL i Neo4j nadal wyszukują jego wiersze przez indeks częściowy z BASE (podrozdz. „Ścieżki dostępu”), a każda zmiana statusu zamówienia aktualizuje wpis w IX2.

### Odczyty

Przy rozmiarze L odczyty R4–R7 działają w IDX szybciej we wszystkich SZBD z jednym wyjątkiem: R5 w PostgreSQL. Największy zysk ma R4, który wybiera przesyłki jednego odbiorcy po numerze telefonu. W MongoDB czas R4 spada z {{ mean("R4", "mongo", "base") }} ms do {{ mean("R4", "mongo", "idx") }} ms (iloraz {{ ratio("R4", "mongo") }}), a w PostgreSQL z {{ mean("R4", "pg", "base") }} ms do {{ mean("R4", "pg", "idx") }} ms (iloraz {{ ratio("R4", "pg") }}). Bez IX1 każdy SZBD przegląda wszystkie przesyłki, a z IX1 czyta kilka wpisów indeksu (podrozdz. „Plany BASE i IDX”).

W PostgreSQL zysk rośnie z rozmiarem danych, bo czas BASE rośnie razem z liczbą przeglądanych wierszy, a czas IDX nie. W PostgreSQL R4 w BASE trwa {{ mean("R4", "pg", "base", "S") }} ms przy rozmiarze S i {{ mean("R4", "pg", "base") }} ms przy L, a w IDX {{ mean("R4", "pg", "idx", "S") }} ms i {{ mean("R4", "pg", "idx") }} ms (@fig:R4-ba).

R5, R6 i R7 wybierają wiersze z okna czasu: zamówienia z 30 dni, płatności z miesiąca i otwarcia z doby. W takim oknie mieszczą się tysiące albo dziesiątki tysięcy wierszy. PostgreSQL, MySQL i Neo4j muszą każdy z nich jeszcze połączyć z rezerwacją i skrytką. Indeks skraca tylko wybór wierszy z okna, więc ilorazy są wyższe niż w R4. Na przykład R5 w MySQL ma iloraz {{ ratio("R5", "mysql") }}, a R7 w MongoDB {{ ratio("R7", "mongo") }}. W R5, R6 i R7 najmniej zyskuje PostgreSQL, którego plany BASE czytają duże tabele równolegle (`Parallel Seq Scan`). R5 w PostgreSQL w BASE ({{ mean("R5", "pg", "base") }} ms) jest szybszy niż R5 w IDX w każdym z pozostałych SZBD.

{{ fig("R4-ba", "R4 (przesyłki do odbioru według telefonu odbiorcy) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R5-ba", "R5 (ranking punktów według liczby zamówień z 30 dni) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R6-ba", "R6 (przychód netto punktów w miesiącu) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R7-ba", "R7 (aktywność drzwi punktów w oknie 24 h) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

### Zapisy

Każdy zapis z H1-I i H1-U dopisuje lub zmienia wpisy co najmniej jednego dodanego indeksu. Koszt tej pracy zależy od jej udziału w całej transakcji:

- U1 i U5 zmieniają kolumnę dodanego indeksu w 5000 wierszy, w transakcjach po 1000. Przy rozmiarze L działają w IDX wolniej we wszystkich SZBD, najwyraźniej w MySQL: U1 ma iloraz {{ ratio("U1", "mysql") }}, a U5 {{ ratio("U5", "mysql") }}.
- C2 dopisuje 100 000 wpisów dziennika drzwi w transakcjach po 1000, każdy z wpisem w IX4. Przy rozmiarze L działa w IDX wolniej we wszystkich SZBD, ale ilorazy są bliskie 1: w PostgreSQL {{ ratio("C2", "pg") }}, czyli średnie są prawie równe, a w MongoDB {{ ratio("C2", "mongo") }}.
- C6 dopisuje płatności partiami po 5000, każdą z wpisem w IX3. W PostgreSQL, MySQL i MongoDB działa w IDX wolniej, w Neo4j minimalnie szybciej.
- C3 i C4 to 1000 osobnych transakcji. Każda wstawia kilka wierszy, a w dodanych indeksach dwa wpisy (C3: IX2 i IX3) albo trzy (C4: IX1, IX2 i IX3). Kierunek zmiany różni się tu między SZBD i między rozmiarami danych.

Iloraz C3 w MongoDB przy M ({{ ratio("C3", "mongo", "M") }}, @fig:C3-ba) nie pokazuje kosztu indeksów. Przebiegi BASE trwają {{ span("C3", "mongo", "base", "M") }} ms, a IDX {{ span("C3", "mongo", "idx", "M") }} ms. Trzeci przebieg BASE i wszystkie przebiegi IDX są o około 2 s dłuższe od dwóch pierwszych przebiegów BASE. Czas wzrósł więc skokowo w trakcie sesji, jeszcze w BASE, i ten skok wchodzi do ilorazu.

W PostgreSQL ilorazy U5 są wyższe niż ilorazy U1 we wszystkich rozmiarach, np. przy S {{ ratio("U5", "pg", "S") }} wobec {{ ratio("U1", "pg", "S") }}. Zmiana kolumny objętej indeksem wyklucza aktualizację HOT, czyli nową wersję wiersza bez nowych wpisów w indeksach. Kolumna `status_`, którą zmienia U1, już w BASE występuje w predykacie indeksu częściowego `order_awaiting_payment__idx`, więc U1 nie korzysta z HOT w żadnej konfiguracji. Telefon odbiorcy, który zmienia U5, w BASE nie występuje w żadnym indeksie `shipment_`, a w IDX jest kluczem IX1. Wyniki są z tym zgodne, ale planów zapisów nie zapisujemy (rozdz. 5), więc HOT nie jest potwierdzony planem.

{{ fig("C2-ba", "C2 (dopisanie wpisów dziennika drzwi) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("C3-ba", "C3 (rezerwacja skrytki) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("C4-ba", "C4 (nadanie przesyłki) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("C6-ba", "C6 (naliczenie opłat za przetrzymanie bagażu) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("U1-ba", "U1 (zamknięcie opłaconych zamówień) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("U3-ba", "U3 (wygaszenie nieopłaconych zamówień po terminie) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("U5-ba", "U5 (korekta telefonu odbiorcy przesyłki) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

## Ścieżki dostępu

Plany wykonania zapisujemy dla rozmiarów S i L, dla pierwszego zestawu parametrów scenariusza (rozdz. 5). @Tab:access-core-L pokazuje plany BASE i IDX dla rozmiaru L. Dla odczytów R4–R7 to plan całego zapytania. Dla zapisów C6 i U3 to plan zapytania, które wyszukuje wiersze do zmiany.

Kolumna „Ścieżka dostępu” podaje sposoby czytania danych z planu: węzły skanu w PostgreSQL, typ dostępu w MySQL, etap `COLLSCAN` albo `IXSCAN` w MongoDB i operator skanu albo wyszukania w Neo4j. Kolumna „Indeksy” wymienia indeksy użyte w planie. Wiersze przejrzane i zwrócone liczymy według reguł z rozdz. 5. Pełne plany obu rozmiarów są w katalogu `results/explain/`.

{{ dataset("access-core-L", "Ścieżki dostępu i przejrzane wiersze w planach BASE i IDX dla rozmiaru L") }}

W BASE odczyty R4–R7 przeglądają całą tabelę, kolekcję albo etykietę: `Seq Scan` w PostgreSQL, `ALL` w MySQL, `COLLSCAN` w MongoDB i `NodeByLabelScan` w Neo4j. W IDX każdy z nich używa dodanego indeksu, z wyjątkiem R5 w PostgreSQL. MongoDB w BASE przegląda całą kolekcję `orders` także w R6 i R7, bo płatności i otwarcia skrytek są osadzone w dokumencie zamówienia. To jeden z powodów, dla których MongoDB ma w R4, R6 i R7 najmniejsze ilorazy spośród czterech SZBD.

Wyszukanie wierszy do zapisu C6 ma w obu konfiguracjach ten sam plan, z tym samym indeksem i tą samą liczbą przejrzanych wierszy. Różnica czasu C6 między BASE i IDX wynika więc z samego wstawiania płatności i z rozrzutu przebiegów. U3 w PostgreSQL, MySQL i Neo4j wyszukuje wiersze w obu konfiguracjach przez indeks częściowy `order_awaiting_payment__idx` z BASE. Tylko MongoDB wybiera w IDX dodany indeks IX2.

W MySQL utworzenie indeksu IX1–IX4 przelicza statystyki całej tabeli (rozdz. 5), więc tabele z nowymi indeksami mają w IDX inną próbkę statystyk niż w BASE. W planach R4–R7 nie zmieniło to kolejności złączeń: poza dostępem do tabeli z nowym indeksem plany BASE i IDX mają w MySQL te same kroki.

## Plany BASE i IDX

Rysunki od @fig:plan-R4-pg do @fig:plan-R5-neo4j zestawiają wyciągi z planów BASE i IDX dla rozmiaru L. Wyciąg zawiera tylko kroki dostępu do danych, w kolejności z planu, najwyżej sześć na konfigurację:

- PostgreSQL: węzły skanu z rzeczywistą liczbą wierszy na wykonanie (`rows`) i liczbą wykonań (`loops`) oraz wiersze odrzucone przez filtr;
- MySQL: kroki `scan`, `lookup` i `search` z drzewa `EXPLAIN ANALYZE`, z liczbą wierszy i wykonań;
- MongoDB: etapy `COLLSCAN`, `IXSCAN` i `FETCH` z liczbą przejrzanych kluczy albo dokumentów (`keysExamined`, `docsExamined`) i zwróconych (`nReturned`);
- Neo4j: operatory skanu i wyszukania z liczbą wierszy.

R4 pokazuje odczyt selektywny. W BASE każdy SZBD przegląda wszystkie przesyłki: PostgreSQL i MySQL tabelę `shipment_`, Neo4j węzły z etykietą `Shipment`, a MongoDB całą kolekcję `orders`, bo przesyłka jest częścią dokumentu zamówienia. W IDX każdy SZBD czyta przez IX1 tylko kilka wpisów. Pozostałe kroki planów PostgreSQL i MySQL, czyli wyszukania rezerwacji, skrytki i punktu, są w obu konfiguracjach takie same.

{{ plan("R4", "pg", "L", "Plan R4 w PostgreSQL dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R4", "mysql", "L", "Plan R4 w MySQL dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R4", "mongo", "L", "Plan R4 w MongoDB dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R4", "neo4j", "L", "Plan R4 w Neo4j dla rozmiaru L: wyciąg z planów BASE i IDX") }}

R5 pokazuje odczyt mało selektywny. W MySQL, MongoDB i Neo4j plan IDX zaczyna od IX2 i czyta tylko zamówienia z okna czasu. MySQL robi to przez skan zakresu indeksu pokrywającego, ale potem wyszukuje rezerwację i skrytkę osobno dla każdego zamówienia z okna. Ta część planu jest taka sama jak w BASE, dlatego iloraz R5 w MySQL jest wyższy niż w MongoDB i Neo4j. Neo4j w BASE zaczyna od przejrzenia wszystkich węzłów `Reservation`, a w IDX od wyszukania zamówień w IX2.

PostgreSQL ma w BASE i IDX ten sam plan: równoległy `Seq Scan` tabel `order_` i `reservation_` z dwoma procesami pomocniczymi i złączenia haszujące. Plan IDX nie używa IX2. Warunek R5 spełnia mniej niż jedna dziesiąta wierszy `order_`, ale planista szacuje ich więcej, niż jest w rzeczywistości: w pliku planu szacunek to 80 072 wiersze na proces, a rzeczywista liczba 26 982 wiersze na proces. Wszystkie strony obu tabel są w pamięci podręcznej (`shared hit`), a koszt równoległego odczytu całej tabeli planista ocenia niżej niż odczyt przez indeks. Przy rozmiarze S ten sam odczyt używa IX2 (`Bitmap Index Scan`) i w IDX działa szybciej, z ilorazem {{ ratio("R5", "pg", "S") }}.

{{ plan("R5", "pg", "L", "Plan R5 w PostgreSQL dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R5", "mysql", "L", "Plan R5 w MySQL dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R5", "mongo", "L", "Plan R5 w MongoDB dla rozmiaru L: wyciąg z planów BASE i IDX") }}

{{ plan("R5", "neo4j", "L", "Plan R5 w Neo4j dla rozmiaru L: wyciąg z planów BASE i IDX") }}

## Komórki, które nie potwierdzają H1

Werdykt H1, regułę rozstrzygnięcia i analizę według SZBD podaje rozdz. 11. Przy rozmiarze L hipotezy nie potwierdza siedem komórek scenariuszy podstawowych: jeden odczyt (R5 w PostgreSQL) i sześć zapisów INSERT (C3, C4 i C6). Wszystkie komórki JSON potwierdzają hipotezę (rozdz. 9). Ten podrozdział zestawia dla tych komórek dowody z planów i z przebiegów. Komórka zapisu potwierdza H1, gdy średnia IDX jest wyższa od średniej BASE. Reguła nie ma progu, więc przy ilorazie bliskim 1 o wyniku decyduje także rozrzut przebiegów. Dlatego podajemy zakres min–max trzech przebiegów BASE i IDX.

- PostgreSQL, R5: plan IDX nie używa IX2 i jest taki sam jak plan BASE (@fig:plan-R5-pg), więc oba czasy są prawie równe (iloraz {{ ratio("R5", "pg") }}).
- PostgreSQL, C4: przebiegi BASE trwają {{ span("C4", "pg", "base") }} ms, a IDX {{ span("C4", "pg", "idx") }} ms. Zakresy się nakładają, a jeden przebieg IDX jest wyraźnie krótszy od pozostałych. Przy M C4 w IDX działa wolniej (iloraz {{ ratio("C4", "pg", "M") }}), a przy S szybciej ({{ ratio("C4", "pg", "S") }}).
- MySQL, C3: przebiegi BASE trwają {{ span("C3", "mysql", "base") }} ms, a IDX {{ span("C3", "mysql", "idx") }} ms. Zakresy się nie nakładają, a IDX jest szybsze także przy S i M (ilorazy {{ ratio("C3", "mysql", "S") }} i {{ ratio("C3", "mysql", "M") }}).
- MySQL, C4: przebiegi BASE trwają {{ span("C4", "mysql", "base") }} ms, a IDX {{ span("C4", "mysql", "idx") }} ms. Zakresy się nie nakładają.
- MongoDB, C4: przebiegi BASE trwają {{ span("C4", "mongo", "base") }} ms, a IDX {{ span("C4", "mongo", "idx") }} ms. Zakresy się nakładają, a przy S i M C4 w IDX działa wolniej (ilorazy {{ ratio("C4", "mongo", "S") }} i {{ ratio("C4", "mongo", "M") }}).
- Neo4j, C3: przebiegi BASE trwają {{ span("C3", "neo4j", "base") }} ms, a IDX {{ span("C3", "neo4j", "idx") }} ms. Zakresy się nakładają.
- Neo4j, C6: przebiegi BASE trwają {{ span("C6", "neo4j", "base") }} ms, a IDX {{ span("C6", "neo4j", "idx") }} ms. Zakresy się nakładają, a wyszukanie zaległych rezerwacji ma w obu konfiguracjach ten sam plan (@tab:access-core-L).

W PostgreSQL C4, MongoDB C4 i obu komórkach Neo4j różnica średnich jest mniejsza od rozrzutu przebiegów. Dwa albo trzy dodatkowe wpisy indeksów na transakcję (C3, C4) i wpisy IX3 dla nowych płatności (C6) są tu małą częścią pracy obok wyszukania wierszy, wstawień z kontrolą ograniczeń i trwałego zatwierdzenia. W Neo4j stałą część czasu zwiększa dodatkowo świeża JVM i kompilacja zapytań w każdym przebiegu zapisu (rozdz. 5).

MySQL jest wyjątkiem: w C3 i C4 przy L IDX jest szybsze, a zakresy przebiegów się nie nakładają. Liczniki odczytów z dysku są w obu konfiguracjach prawie równe. IDX wykonuje więcej pracy niż BASE, więc szybszy przebieg IDX wymaga innej przyczyny niż indeksy. Sprawdziliśmy ją po pomiarach w sesji diagnostycznej (rozdz. 7, dane w `results/diag-g3/`):

- Plany. `EXPLAIN ANALYZE` wyszukania wolnej skrytki i zapytania wyzwalacza o nakładające się rezerwacje ma w BASE i IDX te same kroki, te same indeksy i te same szacunki. Nowa próbka statystyk tabel z IX1–IX4 nie zmienia więc tych planów.
- Kolejność przebiegów. W pilotażu przy S przebiegi IDX szły przed przebiegami BASE i MySQL miał w IDX czasy dłuższe: ilorazy C2, C3 i C4 wynosiły 1,21, 1,19 i 1,10. Po zmianie kolejności na BASE, a zaraz potem IDX (rozdz. 5) te same scenariusze przy S dały 0,99, 0,97 i 1,04.
- Powtórzenie. W sesji diagnostycznej zmierzyliśmy C3 i C4 w MySQL przy S i L w obu kolejnościach. IDX było wolniejsze od BASE w sześciu z ośmiu par, z ilorazami od 1,02 do 1,27. Szybsze było tylko C4 przy S, z ilorazami 0,98 i 0,99, w obu kolejnościach.

Przewaga IDX w C3 i C4 przy L nie powtórzyła się więc w innej sesji. Odczytujemy ją jako zmienność kolejnych przebiegów, a nie skutek indeksów. W sesji diagnostycznej zatwierdzenie z zapisem na dysk zajmowało w C3 i C4 ponad połowę czasu przebiegu (rozdz. 7), a dwa albo trzy wpisy indeksów to mała część pracy.

## Koszt budowy indeksów

Indeksy IDX powstają na załadowanych danych, po zapisaniu migawki BASE, po jednym poleceniu na indeks. @Tab:build-core podaje czas budowy i rozmiar każdego indeksu IX1–IX4 dla każdego rozmiaru danych. Rozmiar to `pg_relation_size` w PostgreSQL, liczba stron z `mysql.innodb_index_stats` razy rozmiar strony w MySQL, `indexSizes` z `$collStats` w MongoDB i rozmiar katalogu indeksu (`du`) w Neo4j. W MongoDB wszystkie cztery indeksy leżą w kolekcji `orders`, bo przesyłka, płatności i otwarcia skrytek są osadzone w dokumencie zamówienia.

{{ dataset("build-core", "Czas budowy i rozmiar indeksów IX1–IX4") }}

Budowa to koszt jednorazowy. Przy rozmiarze L żaden indeks IX1–IX4 nie powstaje dłużej niż kilka sekund, a najkrócej budują się w PostgreSQL. Przy metodach pomiaru rozmiaru opisanych wyżej najmniejsze indeksy ma MongoDB, a Neo4j ma największe IX2, IX3 i IX4.
