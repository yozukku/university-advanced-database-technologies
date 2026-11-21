# Zbiór danych i modele danych

Wszystkie cztery SZBD dostają ten sam zbiór danych Bagażomatu w trzech modelach: relacyjnym (PostgreSQL i MySQL), dokumentowym (MongoDB) i grafowym (Neo4j). Tabele i przykłady w tym rozdziale powstają automatycznie: liczby rekordów i skróty z wyników ładowania, odwzorowanie MySQL ze skryptów DDL i mapy indeksów, a przykładowe dokumenty z transformacji danych do MongoDB.

## Schemat relacyjny

Schemat ma 13 tabel: 12 tabel sieci przechowalni i tabelę `audit_event_` z dziennikiem zdarzeń w JSON. @Fig:erd-przeglad pokazuje wszystkie tabele z kluczami głównymi i obcymi, a @fig:erd-legenda objaśnia oznaczenia. Pełne kolumny tabel pokazują diagramy pięciu stref [@fig:erd-siec; @fig:erd-klient; @fig:erd-zamowienie; @fig:erd-dostep; @fig:erd-dziennik].

![Diagram ERD: przegląd 13 tabel z kluczami](report/assets/erd/przeglad.png){#fig:erd-przeglad}

![Legenda diagramów ERD](report/assets/erd/legenda.png){#fig:erd-legenda}

![Diagram ERD: sieć automatów](report/assets/erd/siec-automatow.png){#fig:erd-siec}

![Diagram ERD: klient i pieniądze](report/assets/erd/klient-i-pieniadze.png){#fig:erd-klient}

![Diagram ERD: zamówienie i rezerwacja](report/assets/erd/zamowienie-i-rezerwacja.png){#fig:erd-zamowienie}

![Diagram ERD: dostęp i incydenty](report/assets/erd/dostep-i-incydenty.png){#fig:erd-dostep}

![Diagram ERD: dziennik zdarzeń (JSON)](report/assets/erd/dziennik-zdarzen.png){#fig:erd-dziennik}

## Rozmiary zbioru danych

Rekord to wiersz jednej z 13 tabel. @Tab:volume podaje liczbę rekordów w każdej tabeli dla każdego zmierzonego rozmiaru. Suma 13 tabel wynosi dokładnie 500 000 (S), 1 000 000 (M) i 10 000 000 (L) rekordów.

{{ dataset("volume", "Liczba rekordów w tabelach zbioru danych") }}

## Model dokumentowy

MongoDB przechowuje dane w siedmiu kolekcjach: `lockermats`, `tariffs`, `customers`, `orders`, `incidents`, `auditEvents` i `shipLinks`. Dokument zamówienia osadza rezerwacje, ich kody dostępu z otwarciami skrytek, płatności i przesyłkę (@fig:order). Zdarzenie audytowe przechowuje aktora jako obiekt, a listę zmian jako tablicę obiektów (@fig:audit). Kwoty są liczbami groszy, a znaczniki czasu mają dokładność milisekund.

{{ sample("order", "Dokument zamówienia przesyłki w kolekcji orders (dane XS, tablice skrócone do pierwszego elementu)") }}

{{ sample("audit", "Zdarzenie audytowe w kolekcji auditEvents (dane XS)") }}

## Model grafowy

Neo4j ma 12 etykiet węzłów i 15 typów relacji (@fig:graf). Zamówienie przesyłki ma dodatkową etykietę `Shipment`, a relacja `SHIPS_TO` łączy punkt nadania z punktem odbioru. Węzeł `AuditEvent` nie ma relacji. Jego pola `actor` i `changes` są tekstem JSON, bo właściwość węzła w Neo4j nie może zawierać zagnieżdżonej mapy.

![Model grafowy w Neo4j: etykiety węzłów z tabelami kanonicznymi i typy relacji](report/assets/graph/model.png){#fig:graf}

## Odwzorowanie schematu w MySQL

MySQL ma te same 13 tabel z tymi samymi nazwami kolumn. @Tab:types zestawia typy kolumn, które w MySQL mają inną postać. @Tab:objects zestawia ograniczenia i indeksy PostgreSQL, które MySQL realizuje inaczej: reguły EXCLUDE zastępują wyzwalacze, a indeksy częściowe indeksy funkcyjne z wyrażeniem CASE albo automatyczne indeksy kluczy obcych.

{{ dataset("types", "Typy kolumn PostgreSQL i ich odpowiedniki w MySQL") }}

{{ dataset("objects", "Ograniczenia i indeksy PostgreSQL odwzorowane w MySQL inaczej") }}

## Zgodność danych w czterech SZBD

Po załadowaniu każda baza odtwarza 13 tabel w postaci kanonicznej, a każda tabela dostaje skrót SHA-256 niezależny od kolejności wierszy. @Tab:parity podaje początek skrótu każdej tabeli. Skrót w komórce oznacza, że PostgreSQL, MySQL, MongoDB i Neo4j dały ten sam skrót co dane kanoniczne. Ostatni wiersz podaje odległość Kraków Główny – Warszawa Centralna, którą każda baza liczy własną funkcją. @Tab:load podaje czas ładowania i rozmiar bazy na dysku.

{{ dataset("parity", "Skróty SHA-256 tabel (pierwsze 12 znaków) równe w czterech SZBD") }}

{{ dataset("load", "Czas ładowania i rozmiar bazy na dysku") }}
