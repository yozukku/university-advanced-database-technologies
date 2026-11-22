# Wyniki CRUD

Rozdział pokazuje wyniki 26 scenariuszy podstawowych w konfiguracji IDX, w której mierzymy wszystkie scenariusze (rozdz. 6). Każda wartość to średnia z trzech mierzonych przebiegów (rozdz. 5). Tabele i wykresy powstają z katalogu `results/` przy budowaniu sprawozdania.

## Średnie czasy według operacji i rozmiaru

@Tab:C, @tab:R, @tab:U i @tab:D podają średni czas każdego scenariusza dla rozmiarów S, M i L w czterech SZBD. Czas obejmuje cały przebieg: wszystkie zestawy parametrów odczytu albo wszystkie partie zapisu. Liczba operacji jest taka sama dla wszystkich rozmiarów (rozdz. 6).

### Tworzenie (C)

{{ table("C", "Średnie czasy scenariuszy tworzenia (C) w konfiguracji IDX") }}

### Odczyt (R)

Na @fig:R1 pokazano średni czas odczytu R1 w czterech SZBD z zakresem min–max.

{{ fig("R1", "Czas odczytu R1 (szczegóły zamówienia) w czterech SZBD") }}

{{ table("R", "Średnie czasy scenariuszy odczytu (R) w konfiguracji IDX") }}

### Aktualizacja (U)

{{ table("U", "Średnie czasy scenariuszy aktualizacji (U) w konfiguracji IDX") }}

### Usuwanie (D)

{{ table("D", "Średnie czasy scenariuszy usuwania (D) w konfiguracji IDX") }}

## Porównanie SZBD

@Fig:heatmap-L zestawia scenariusze podstawowe przy rozmiarze L. Komórka to średni czas SZBD podzielony przez średni czas najszybszego SZBD w tym samym scenariuszu, więc najszybszy SZBD ma wartość ×1. Im ciemniejsza komórka, tym większa krotność.

{{ fig("heatmap-L", "Czas scenariuszy CRUD przy rozmiarze L względem najszybszego SZBD w scenariuszu, konfiguracja IDX; skala logarytmiczna") }}

## Skalowanie z rozmiarem danych

@Tab:scaling podaje wykładnik *b* zależności *t* ≈ *a* · *n*^*b*^, gdzie *t* to średni czas scenariusza, a *n* to liczba rekordów zbioru (500 000, 1 000 000 i 10 000 000). Wykładnik to nachylenie prostej dopasowanej metodą najmniejszych kwadratów do punktów (log *n*, log *t*) dla rozmiarów S, M i L. Wartość bliska 0 oznacza czas niezależny od rozmiaru danych, a wartość bliska 1 czas proporcjonalny do liczby rekordów. Liczba operacji jest stała, ale w zapisach zbiorowych (rozdz. 5) liczba zmienianych wierszy zależy od rozmiaru danych.

{{ dataset("scaling", "Wykładnik skalowania b czasu względem liczby rekordów (S, M, L), konfiguracja IDX") }}

## Wpływ modelu danych

Trzy scenariusze pokazują różnicę między modelem relacyjnym, dokumentowym i grafowym (@tab:models):

- R1 (szczegóły zamówienia): w PostgreSQL i MySQL złączenie pięciu tabel, w MongoDB odczyt jednego dokumentu `orders` i dokumentów automatów jego etapów, w Neo4j wzorce od węzła zamówienia przez etapy i skrytki do automatów;
- D2 (usunięcie zamówień z zależnymi): w PostgreSQL i MySQL osiem poleceń `delete` w kolejności od dzieci do rodzica w siedmiu tabelach, w MongoDB `deleteOne` dokumentu zamówienia i dwa `deleteMany` w jednej transakcji, w Neo4j `DETACH DELETE` podgrafu zamówienia;
- R8 (automaty osiągalne po połączeniach przesyłek): w PostgreSQL i MySQL rekurencyjne CTE, w MongoDB `$graphLookup` po kolekcji `shipLinks`, w Neo4j `SHORTEST 1` po relacjach `SHIPS_TO`.

{{ dataset("models", "Model danych a wynik: średnie czasy R1, D2 i R8 przy rozmiarze L, konfiguracja IDX") }}
