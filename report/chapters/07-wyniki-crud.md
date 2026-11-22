# Wyniki CRUD

Rozdział pokazuje wyniki 26 scenariuszy podstawowych w konfiguracji IDX, w której mierzymy wszystkie scenariusze (rozdz. 6). Każda wartość to średnia z trzech mierzonych przebiegów (rozdz. 5). Tabele i wykresy powstają z katalogu `results/` przy budowaniu sprawozdania, a czasy podane w tekście pochodzą z tych samych plików. Minimum, maksimum i współczynnik zmienności każdej komórki podaje dodatek A.

## Średnie czasy według operacji i rozmiaru

@Tab:C, @tab:R, @tab:U i @tab:D podają średni czas każdego scenariusza dla rozmiarów S, M i L w czterech SZBD. Czas obejmuje cały przebieg: wszystkie zestawy parametrów odczytu albo wszystkie partie zapisu. Liczba operacji jest taka sama dla wszystkich rozmiarów (rozdz. 6).

### Tworzenie (C)

{{ table("C", "Średnie czasy scenariuszy tworzenia (C) w konfiguracji IDX") }}

Scenariusze C1–C5 wykonują stałą liczbę operacji, więc ich czasy prawie nie zależą od rozmiaru danych (@tab:C). C6 nalicza opłaty dla wszystkich zaległych rezerwacji, a ich liczba rośnie razem ze zbiorem danych. Neo4j jest najwolniejszy we wszystkich scenariuszach tworzenia. W C1 przy rozmiarze L potrzebuje {{ mean("C1", "neo4j", "idx") }} ms, a PostgreSQL {{ mean("C1", "pg", "idx") }} ms. Czas każdego zapisu w Neo4j obejmuje pierwszą kompilację zapytań Cypher na świeżo uruchomionej JVM (rozdz. 5).

W C2 MongoDB potrzebuje {{ mean("C2", "mongo", "idx") }} ms, a PostgreSQL {{ mean("C2", "pg", "idx") }} ms. W modelu dokumentowym wpis dziennika drzwi jest osadzony w dokumencie zamówienia, w tablicy otwarć kodu dostępu (rozdz. 3). C2 nie wstawia więc w MongoDB małych wierszy, tylko zmienia dokumenty zamówień operacją `$push` z filtrami tablic.

### Odczyt (R)

Na @fig:R1 pokazano średni czas odczytu R1 w czterech SZBD z zakresem min–max.

{{ fig("R1", "Czas odczytu R1 (szczegóły zamówienia) w czterech SZBD") }}

{{ table("R", "Średnie czasy scenariuszy odczytu (R) w konfiguracji IDX") }}

PostgreSQL jest najszybszy w siedmiu z ośmiu odczytów (@tab:R). Wyjątkiem jest R8, w którym najszybszy jest MongoDB (podrozdz. „Wybrane przypadki”). Największą rozpiętość między SZBD ma odczyt przestrzenny R3. Odczyty R5, R6 i R7 obejmują okno czasu o stałej długości, a liczba zamówień, płatności i otwarć w tym oknie rośnie z rozmiarem danych, więc rośnie też ich czas.

### Aktualizacja (U)

{{ table("U", "Średnie czasy scenariuszy aktualizacji (U) w konfiguracji IDX") }}

W aktualizacjach żaden SZBD nie wygrywa we wszystkich scenariuszach (@tab:U). Przy rozmiarze L MySQL jest najszybszy w U1, U5 i U6, MongoDB w U3 i U4, a PostgreSQL w U2. U2 to 1000 krótkich transakcji, jedna na użycie kodu, więc jego czas prawie nie zależy od rozmiaru danych. U3 i U6 zmieniają wszystkie wiersze spełniające warunek daty, a ich liczba rośnie z rozmiarem danych. Przypadek U6 w PostgreSQL omawiamy niżej.

### Usuwanie (D)

{{ table("D", "Średnie czasy scenariuszy usuwania (D) w konfiguracji IDX") }}

Przy rozmiarze L PostgreSQL jest najszybszy w D1, D2, D3, D4 i D6, a MongoDB w D5 (@tab:D). W D4 MongoDB potrzebuje {{ mean("D4", "mongo", "idx") }} ms, a PostgreSQL {{ mean("D4", "pg", "idx") }} ms. D4 szuka klientów bez zamówień. W MongoDB robi to etap `$lookup` z kolekcji `customers` do `orders`, czyli osobne wyszukanie zamówień dla każdego klienta. PostgreSQL i MySQL wykonują jedno zapytanie z antyzłączeniem `not exists`.

## Porównanie SZBD

@Fig:heatmap-L zestawia scenariusze podstawowe przy rozmiarze L. Komórka to średni czas SZBD podzielony przez średni czas najszybszego SZBD w tym samym scenariuszu, więc najszybszy SZBD ma wartość ×1. Im ciemniejsza komórka, tym większa krotność.

{{ fig("heatmap-L", "Czas scenariuszy CRUD przy rozmiarze L względem najszybszego SZBD w scenariuszu, konfiguracja IDX; skala logarytmiczna") }}

PostgreSQL ma wartość ×1 w większości scenariuszy podstawowych, w tym we wszystkich odczytach poza R8. MySQL jest najszybszy w C3, C4, U1, U5 i U6, przy czym w C4 jego czas prawie równa się czasowi PostgreSQL. MongoDB jest najszybszy w R8, U3, U4 i D5. Neo4j nie jest najszybszy w żadnym scenariuszu podstawowym. Najmniejsze krotności we wszystkich SZBD mają zapisy w wielu krótkich transakcjach: U2, C3, C4 i D2. Najciemniejsze komórki to R3 w Neo4j i MySQL oraz D4 w MongoDB.

## Wybrane przypadki

### R3: najbliższe punkty z wolną skrytką

R3 szuka dziesięciu najbliższych aktywnych punktów w promieniu 5 km, które mają wolną skrytkę danego rozmiaru w wybranym oknie czasu. Przy rozmiarze L PostgreSQL potrzebuje {{ mean("R3", "pg", "idx") }} ms, MongoDB {{ mean("R3", "mongo", "idx") }} ms, MySQL {{ mean("R3", "mysql", "idx") }} ms, a Neo4j {{ mean("R3", "neo4j", "idx") }} ms (@fig:R3).

{{ fig("R3", "Czas odczytu R3 (najbliższe punkty z wolną skrytką) w czterech SZBD; skala logarytmiczna") }}

Plany IDX przy rozmiarze L pokazują, że wszystkie cztery SZBD znajdują punkty w promieniu przez indeks przestrzenny: GiST w PostgreSQL, SPATIAL w MySQL, 2dsphere w MongoDB i indeks punktowy w Neo4j. Różnią się sprawdzeniem, czy skrytka jest wolna w oknie czasu. PostgreSQL używa indeksu GiST ograniczenia wykluczającego `reservation_no_double_booking__ex` na parze (skrytka, zakres czasu), więc dla każdej skrytki czyta tylko rezerwacje nakładające się na okno. MySQL nie ma typu zakresu ani ograniczenia wykluczającego. Czyta przez B-drzewo `reservation_cell_from__idx` wszystkie rezerwacje skrytki i dopiero potem sprawdza czas. W planie Neo4j filtr rozmiaru skrytki działa dopiero po sprawdzeniu rezerwacji, więc Neo4j przechodzi relacje `IN_CELL` wszystkich skrytek punktu, a nie tylko skrytek żądanego rozmiaru.

### R8: zasięg sieci przesyłek

R8 wyznacza punkty osiągalne z punktu startowego po połączeniach przesyłek z ostatnich 90 dni, w co najwyżej trzech przeskokach. Przy rozmiarze L najszybszy jest MongoDB: {{ mean("R8", "mongo", "idx") }} ms. PostgreSQL potrzebuje {{ mean("R8", "pg", "idx") }} ms, Neo4j {{ mean("R8", "neo4j", "idx") }} ms, a MySQL {{ mean("R8", "mysql", "idx") }} ms (@fig:R8).

{{ fig("R8", "Czas odczytu R8 (punkty osiągalne po połączeniach przesyłek) w czterech SZBD") }}

MongoDB i Neo4j czytają gotowe połączenia między punktami: kolekcję `shipLinks` z indeksem `(from, at)` i relacje `SHIPS_TO` z datą przesyłki (rozdz. 3). PostgreSQL i MySQL wyznaczają połączenia w kolejnych krokach rekurencyjnego CTE ze złączenia sześciu tabel: przesyłki, zamówienia, dwóch nóg rezerwacji i dwóch skrytek. Model grafowy nie daje tu Neo4j przewagi nad MongoDB. Plan Neo4j składa się z wyszukania punktu startowego w indeksie unikalnym i jednego operatora najkrótszej ścieżki `SHORTEST 1`. Z planów nie wynika, dlaczego ten operator działa wolniej niż `$graphLookup` w MongoDB.

### Zapisy w wielu krótkich transakcjach (C3, C4, U2, D2)

C3, C4, U2 i D2 wykonują po 1000 transakcji, każda z trwałym zatwierdzeniem (rozdz. 5). W tych scenariuszach różnice między SZBD są najmniejsze w całym zestawie (@fig:heatmap-L), a czasy prawie nie zależą od rozmiaru danych (@tab:scaling). Każda transakcja dotyka kilku wierszy znalezionych przez indeksy, więc jej koszt nie rośnie z liczbą rekordów. SZBD różnią się liczbą wywołań w transakcji (rozdz. 6). W PostgreSQL rezerwacja C3 to jedno polecenie z wyrażeniami `with`, w MySQL pięć poleceń, w MongoDB sześć wywołań, a w Neo4j jedno zapytanie Cypher. Mimo to MySQL jest w C3 szybszy od PostgreSQL: {{ mean("C3", "mysql", "idx") }} ms wobec {{ mean("C3", "pg", "idx") }} ms (@fig:C3). Sama liczba wywołań nie wyjaśnia więc kolejności SZBD.

{{ fig("C3", "Czas zapisu C3 (rezerwacja skrytki, 1000 transakcji) w czterech SZBD") }}

### U6 w PostgreSQL

U6 zmienia status wszystkich przeterminowanych aktywnych kodów dostępu na REVOKED. Przy rozmiarze L PostgreSQL potrzebuje {{ mean("U6", "pg", "idx") }} ms, a MySQL {{ mean("U6", "mysql", "idx") }} ms (@fig:U6). Liczba zmienianych wierszy i liczba partii są we wszystkich SZBD równe, co sprawdza porównanie zapisów (rozdz. 5).

{{ fig("U6", "Czas aktualizacji U6 (unieważnienie przeterminowanych kodów) w czterech SZBD; skala logarytmiczna") }}

PostgreSQL przy każdej aktualizacji zapisuje nową wersję wiersza. Jeśli zmieniona kolumna występuje w jakimkolwiek indeksie tabeli, także w predykacie indeksu częściowego, aktualizacja nie może być typu HOT i dopisuje nowe wpisy do wszystkich indeksów tabeli. Kolumna `status_` występuje w predykacie ograniczenia wykluczającego `access_code_active_purpose__ex`. Tabela `access_code_` ma cztery indeksy: klucz główny, indeks kolumny `reservation_id_` i dwa indeksy GiST ograniczeń wykluczających. W MySQL ograniczenia wykluczające zastępują wyzwalacze, a żaden indeks pomocniczy `access_code_` nie zawiera kolumny `status_`. InnoDB zmienia więc tylko wiersz w indeksie klastrowym. Planów aktualizacji U6 nie zapisujemy (rozdz. 5), więc to wyjaśnienie wynika ze schematu, a nie z planu.

### Usuwanie zbiorowe D3 i D5

D3 usuwa wpisy dziennika otwarć starsze niż 540 dni, a D5 stare anulowane i wygasłe zamówienia ze wszystkimi zależnymi wierszami. W D3 PostgreSQL potrzebuje {{ mean("D3", "pg", "idx") }} ms, MySQL {{ mean("D3", "mysql", "idx") }} ms, MongoDB {{ mean("D3", "mongo", "idx") }} ms, a Neo4j {{ mean("D3", "neo4j", "idx") }} ms (@fig:D3). W MongoDB wpisy dziennika są osadzone w zamówieniach, więc D3 nie usuwa dokumentów, tylko zmienia dokumenty zamówień operacją `$pull`. W Neo4j każdy wpis to węzeł, który znika razem ze swoimi relacjami.

{{ fig("D3", "Czas usuwania D3 (stare wpisy dziennika otwarć) w czterech SZBD; skala logarytmiczna") }}

W D5 kolejność jest inna: najszybszy jest MongoDB ({{ mean("D5", "mongo", "idx") }} ms), tuż za nim PostgreSQL ({{ mean("D5", "pg", "idx") }} ms), a najwolniejszy Neo4j ({{ mean("D5", "neo4j", "idx") }} ms) (@fig:D5). Tu osadzenie działa na korzyść MongoDB: usunięcie dokumentu zamówienia usuwa od razu jego rezerwacje, kody, otwarcia i płatności. PostgreSQL i MySQL usuwają wiersze z siedmiu tabel, a Neo4j każdy węzeł zamówienia i jego zależności razem z relacjami.

{{ fig("D5", "Czas usuwania D5 (stare anulowane i wygasłe zamówienia z zależnymi) w czterech SZBD; skala logarytmiczna") }}

## Skalowanie z rozmiarem danych

@Tab:scaling podaje wykładnik *b* zależności *t* ≈ *a* · *n*^*b*^, gdzie *t* to średni czas scenariusza, a *n* to liczba rekordów zbioru (500 000, 1 000 000 i 10 000 000). Wykładnik to nachylenie prostej dopasowanej metodą najmniejszych kwadratów do punktów (log *n*, log *t*) dla rozmiarów S, M i L. Wartość bliska 0 oznacza czas niezależny od rozmiaru danych, a wartość bliska 1 czas proporcjonalny do liczby rekordów. Liczba operacji jest stała, ale w zapisach zbiorowych (rozdz. 5) liczba zmienianych wierszy zależy od rozmiaru danych.

{{ dataset("scaling", "Wykładnik skalowania b czasu względem liczby rekordów (S, M, L), konfiguracja IDX") }}

Większość scenariuszy należy do jednej z dwóch grup. Wykładnik bliski 0, co do modułu najwyżej 0,25, mają we wszystkich SZBD scenariusze, które wykonują stałą liczbę operacji i znajdują wiersze po kluczu lub przez indeks: C1–C5, R1, R2, R4, U1, U2, U4, U5, D1 i D2. Wykładnik od 0,7 do 1,2 mają scenariusze, w których liczba przetwarzanych wierszy rośnie z rozmiarem danych: odczyty okien czasu R5, R6 i R7 oraz zapisy zbiorowe C6, U3, U6, D3 i D5. Wyjątkiem w tej grupie są zapisy w Neo4j, z wykładnikiem od 0,45 do 0,74. Już przy rozmiarze S czasy tych zapisów w Neo4j są wielokrotnie wyższe niż w pozostałych SZBD (@tab:C, @tab:U, @tab:D), więc stała część kosztu przeważa. Scenariusze R3, R8, D4 i D6 leżą między grupami.

## Wpływ modelu danych

Trzy scenariusze pokazują różnicę między modelem relacyjnym, dokumentowym i grafowym (@tab:models):

- R1 (szczegóły zamówienia): w PostgreSQL i MySQL złączenie pięciu tabel, w MongoDB odczyt jednego dokumentu `orders` i dokumentów automatów jego etapów, w Neo4j wzorce od węzła zamówienia przez etapy i skrytki do automatów;
- D2 (usunięcie zamówień z zależnymi): w PostgreSQL i MySQL osiem poleceń `delete` w kolejności od dzieci do rodzica w siedmiu tabelach, w MongoDB `deleteOne` dokumentu zamówienia i dwa `deleteMany` w jednej transakcji, w Neo4j `DETACH DELETE` podgrafu zamówienia;
- R8 (automaty osiągalne po połączeniach przesyłek): w PostgreSQL i MySQL rekurencyjne CTE, w MongoDB `$graphLookup` po kolekcji `shipLinks`, w Neo4j `SHORTEST 1` po relacjach `SHIPS_TO`.

{{ dataset("models", "Model danych a wynik: średnie czasy R1, D2 i R8 przy rozmiarze L, konfiguracja IDX") }}

W R1 model dokumentowy nie daje MongoDB przewagi. Zamówienie z rezerwacjami, kodami i płatnościami to jeden dokument, ale nazwa i adres punktu leżą w kolekcji `lockermats`. MongoDB wykonuje więc dwa wywołania na zamówienie, a PostgreSQL i MySQL jedno zapytanie. PostgreSQL ({{ mean("R1", "pg", "idx") }} ms) jest szybszy od MongoDB ({{ mean("R1", "mongo", "idx") }} ms) i MySQL ({{ mean("R1", "mysql", "idx") }} ms). Neo4j ({{ mean("R1", "neo4j", "idx") }} ms) jest najwolniejszy, choć cały wynik zbiera jedno zapytanie po relacjach węzła zamówienia.

W D2 MongoDB ({{ mean("D2", "mongo", "idx") }} ms) jest szybszy od MySQL ({{ mean("D2", "mysql", "idx") }} ms) i Neo4j ({{ mean("D2", "neo4j", "idx") }} ms), ale wolniejszy od PostgreSQL ({{ mean("D2", "pg", "idx") }} ms). Osadzenie zastępuje usuwanie wierszy z sześciu tabel usunięciem jednego dokumentu. Zgłoszenia `incidents` i pochodne połączenia `shipLinks` są jednak osobnymi kolekcjami, więc wymagają dodatkowych wywołań w tej samej transakcji.

W R8 model danych decyduje o wyniku najwyraźniej: MongoDB i Neo4j czytają gotowe połączenia między punktami, a model relacyjny wyznacza je złączeniami w każdym kroku rekurencji (podrozdz. „Wybrane przypadki”). W C2, D3 i D5 o wyniku decyduje osadzenie w MongoDB. Przyspiesza usuwanie całych zamówień (D5), ale spowalnia dopisywanie i usuwanie pojedynczych wpisów dziennika drzwi (C2, D3), bo każda taka zmiana jest aktualizacją dokumentu zamówienia, a nie wstawieniem lub usunięciem małego wiersza.
