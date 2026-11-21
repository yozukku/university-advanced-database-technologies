# Zbiór danych i modele danych

Wszystkie cztery SZBD dostają ten sam zbiór danych Bagażomatu w trzech modelach: relacyjnym (PostgreSQL i MySQL), dokumentowym (MongoDB) i grafowym (Neo4j). Tabele i przykłady w tym rozdziale powstają automatycznie: liczby rekordów i skróty z wyników ładowania, odwzorowanie MySQL ze skryptów DDL i mapy indeksów, a przykładowe dokumenty z transformacji danych do MongoDB.

## Schemat relacyjny

Schemat ma 13 tabel: 12 tabel sieci przechowalni i tabelę `audit_event_` z dziennikiem zdarzeń w JSON. @Fig:erd-przeglad pokazuje wszystkie tabele z kluczami głównymi i obcymi, a @fig:erd-legenda objaśnia oznaczenia. Pełne kolumny tabel pokazują diagramy pięciu stref [@fig:erd-siec; @fig:erd-klient; @fig:erd-zamowienie; @fig:erd-dostep; @fig:erd-dziennik].

Źródłem schematu jest plik `docs/design/schema.sql` w składni PostgreSQL. Reguł biznesowych pilnuje sama baza: klucze główne i obce, ograniczenia CHECK i UNIQUE, częściowe indeksy unikalne i pięć ograniczeń wykluczających EXCLUDE. Wykluczenia nie dopuszczają do nakładania się w czasie rezerwacji jednej skrytki, okresów taryf jednego rozmiaru i faktycznego zajęcia skrytki. Nie dopuszczają też dwóch aktywnych kodów tego samego celu w jednej rezerwacji ani tego samego skrótu kodu w nakładających się oknach ważności. Położenie automatu to punkt PostGIS w układzie WGS 84 (SRID 4326). Kwoty mają typ `numeric`, a znaczniki czasu typ `timestamptz`.

![Diagram ERD: przegląd 13 tabel z kluczami](report/assets/erd/przeglad.png){#fig:erd-przeglad}

![Legenda diagramów ERD](report/assets/erd/legenda.png){#fig:erd-legenda}

![Diagram ERD: sieć automatów](report/assets/erd/siec-automatow.png){#fig:erd-siec}

![Diagram ERD: klient i pieniądze](report/assets/erd/klient-i-pieniadze.png){#fig:erd-klient}

![Diagram ERD: zamówienie i rezerwacja](report/assets/erd/zamowienie-i-rezerwacja.png){#fig:erd-zamowienie}

![Diagram ERD: dostęp i incydenty](report/assets/erd/dostep-i-incydenty.png){#fig:erd-dostep}

![Diagram ERD: dziennik zdarzeń (JSON)](report/assets/erd/dziennik-zdarzen.png){#fig:erd-dziennik}

## Dziennik zdarzeń `audit_event_`

Tabela `audit_event_` zapisuje zmiany zamówień, rezerwacji i płatności (@fig:erd-dziennik). Wiersz ma czas `at_`, encję `entity_` (`ORDER`, `RESERVATION` albo `PAYMENT`), id encji `entity_id_`, czynność `action_` (np. `CREATED`, `PAID`, `DEPOSITED`, `REFUNDED`) oraz dwie kolumny JSON. `actor_` to obiekt z polem `kind` i danymi wykonawcy znanymi w chwili zdarzenia. Rodzajów wykonawcy jest siedem: klient (`CUSTOMER`: id Keycloak i e-mail), odbiorca przesyłki (`RECIPIENT`: imię i nazwisko oraz telefon), kurier (`COURIER`), obsługa (`SUPPORT`), terminal automatu (`TERMINAL`), zadanie systemowe (`SYSTEM`) i operator płatności (`PROVIDER`). `changes_` to tablica zmienionych pól w postaci `{f, old, new}`.

Odwołanie do encji jest polimorficzne, więc tabela nie ma klucza obcego. Ograniczenia CHECK wymagają, aby `actor_` był obiektem z polem `kind`, a `changes_` tablicą. Indeks `(entity_, entity_id_, at_)` służy historii zamówienia. Tabela należy do 13 tabel zbioru i liczy się do jego rozmiaru. Scenariusze JSON opisuje rozdz. 9, a historię zamówienia w aplikacji rozdz. 4.

## Generator danych

Dane tworzy generator w Pythonie (`bench/gen/`, polecenie `make data SIZE=S`). Parametry są w `profiles.yaml`: ziarno 20261101, stała chwila odniesienia T0 = 2026-11-01T00:00Z i łączna liczba rekordów każdego rozmiaru. Generator nie czyta zegara systemowego, więc ten sam profil daje zawsze te same pliki.

Generator działa w trzech krokach:

1. Plan liczy wiersze każdej tabeli z łącznej liczby rekordów. Na każde 4000 rekordów przypada jeden automat, a każdy automat ma 40 skrytek. Taryf jest zawsze 9. Zamówienia dzielą się na 13 grup według typu (przechowanie albo przesyłka) i statusu. Z grup wynikają liczby rezerwacji, kodów dostępu, płatności i zdarzeń audytowych. Tabela `cell_opening_` dostaje resztę, więc suma 13 tabel jest dokładnie równa rozmiarowi z profilu.
2. Wartości powstają z ziarna profilu. Faker z lokalizacją `pl_PL` tworzy pule imion i nazwisk, adresów e-mail i nazw firm, a NumPy losuje z nich wiersze. Automaty leżą w 40 polskich miastach. Dwa pierwsze to Kraków Główny i Warszawa Centralna, bo między nimi każda baza liczy odległość kontrolną. Generator nadaje też wszystkie identyfikatory, więc są one takie same w czterech SZBD. Skrót kodu dostępu to SHA-256 z ziarna i id kodu, a nie HMAC z PIN-u: 6-cyfrowe PIN-y powtarzałyby się przy takiej liczbie kodów.
3. Każda tabela trafia do pliku Parquet. Plik `manifest.json` zawiera liczby wierszy, skrót SHA-256 każdego pliku i skrót całego zbioru.

Generator umieszcza w danych wiersze, których potrzebują scenariusze: klientów bez zamówień, nieużywane automaty, zaległe rezerwacje, nieopłacone zamówienia po terminie, przeterminowane aktywne kody, oczekujące polecenia otwarcia, co najmniej 5000 opłaconych zamówień, klientów z 60–80 zamówieniami i numery odbiorców powtarzające się w wielu przesyłkach.

Przed ładowaniem `make validate` sprawdza pliki Parquet w DuckDB, bez uruchamiania testowanych SZBD. Kontrola porównuje liczby wierszy z planem i sprawdza reguły schematu, np. brak nakładających się rezerwacji, ważność kodu w oknie rezerwacji i sumę zwrotów nie większą od wpłaty. Sprawdza też siedem rodzajów wykonawcy w `audit_event_`, warunki wstępne scenariuszy z `bench/scenarios/ops.yaml` i skróty z manifestu. Ostatecznym dowodem poprawności danych jest ładowanie do PostgreSQL: baza sprawdza każdy wiersz pełnym zestawem ograniczeń schematu.

## Rozmiary zbioru danych

Rekord to wiersz jednej z 13 tabel. @Tab:volume podaje liczbę rekordów w każdej tabeli dla każdego zmierzonego rozmiaru. Suma 13 tabel wynosi dokładnie 500 000 (S), 1 000 000 (M) i 10 000 000 (L) rekordów. Liczby w tabeli to wiersze odtworzone z baz po załadowaniu (`results/load/<rozmiar>.json`). Rozmiar XS (20 000 rekordów) służy tylko testom i nie wchodzi do wyników.

{{ dataset("volume", "Liczba rekordów w tabelach zbioru danych") }}

## Model dokumentowy

MongoDB przechowuje dane w siedmiu kolekcjach: `lockermats`, `tariffs`, `customers`, `orders`, `incidents`, `auditEvents` i `shipLinks`. Dokument zamówienia osadza rezerwacje, ich kody dostępu z otwarciami skrytek, płatności i przesyłkę (@fig:order). Zdarzenie audytowe przechowuje aktora jako obiekt, a listę zmian jako tablicę obiektów (@fig:audit). Kwoty są liczbami groszy, a znaczniki czasu mają dokładność milisekund.

Osadzanie wynika ze sposobu odczytu. Zamówienie ma najwyżej dwie rezerwacje, a rezerwacja kilka kodów i otwarć, więc tablice pozostają małe. Automat osadza swoje skrytki i godziny otwarcia, a jego położenie to GeoJSON Point z indeksem 2dsphere. Otwarcia serwisowe należą do zgłoszenia w kolekcji `incidents`. Tabele z osobnym cyklem życia (`tariffs`, `customers`, `auditEvents`) mają własne kolekcje.

Model dokumentowy ma też dane pochodne. Rezerwacja przechowuje `lockermatId` automatu swojej skrytki, a przesyłka id automatu nadania i odbioru. Kolekcja `shipLinks` ma jeden dokument na przesyłkę z automatem nadania, automatem odbioru i czasem zamówienia. Korzysta z niej odczyt R8 (`$graphLookup`), bo całe dokumenty zamówień przekroczyłyby przy rozmiarze L limit pamięci tego etapu. Zapisy, które tworzą lub usuwają przesyłkę, zmieniają dane pochodne w tej samej transakcji.

Walidatory `$jsonSchema` sprawdzają typy, pola wymagane i wartości wyliczeniowe. Reguł między polami MongoDB nie sprawdza: dane przechodzą je przy ładowaniu do PostgreSQL. Indeks unikalny nie działa wewnątrz tablicy jednego dokumentu, więc częściowe indeksy unikalne wewnątrz zamówienia nie mają odpowiednika. Rezerwacja skrytki działa w transakcji, która najpierw zwiększa licznik `guardSeq` skrytki. Odpowiada to blokadzie skrytki w MySQL i ograniczeniu EXCLUDE w PostgreSQL.

{{ sample("order", "Dokument zamówienia przesyłki w kolekcji orders (dane XS, tablice skrócone do pierwszego elementu)") }}

{{ sample("audit", "Zdarzenie audytowe w kolekcji auditEvents (dane XS)") }}

## Model grafowy

Neo4j ma 12 etykiet węzłów i 15 typów relacji (@fig:graf). Zamówienie przesyłki ma dodatkową etykietę `Shipment`, a relacja `SHIPS_TO` łączy punkt nadania z punktem odbioru. Węzeł `AuditEvent` nie ma relacji. Jego pola `actor` i `changes` są tekstem JSON, bo właściwość węzła w Neo4j nie może zawierać zagnieżdżonej mapy.

Wiersz tabeli to węzeł, a klucz obcy to relacja. Wyjątkiem jest `shipment_`: jego kolumny są właściwościami węzła zamówienia z etykietą `Shipment`. Relacja `SHIPS_TO` to dane pochodne, jak `shipLinks` w MongoDB. Niektóre węzły przechowują też id powiązanego węzła jako właściwość, np. `Order.customerId`, bo właściwość można indeksować. Weryfikacja sprawdza, że taka właściwość wskazuje ten sam węzeł co relacja.

Unikalne `id` każdej etykiety pełni rolę klucza głównego. Neo4j Community nie ma ograniczeń istnienia właściwości, więc poprawność danych zapewnia PostgreSQL przed importem. Rezerwacja skrytki zwiększa właściwość `_guard` węzła `Cell`, co blokuje węzeł do końca transakcji. Pól JSON zapisanych jako tekst nie da się przeszukiwać po kluczu ani indeksować, dlatego Neo4j nie wykonuje scenariuszy JSON (rozdz. 9).

![Model grafowy w Neo4j: etykiety węzłów z tabelami kanonicznymi i typy relacji](report/assets/graph/model.png){#fig:graf}

## Odwzorowanie schematu w MySQL

MySQL ma te same 13 tabel z tymi samymi nazwami kolumn. @Tab:types zestawia typy kolumn, które w MySQL mają inną postać. @Tab:objects zestawia ograniczenia i indeksy PostgreSQL, które MySQL realizuje inaczej: reguły EXCLUDE zastępują wyzwalacze, a indeksy częściowe indeksy funkcyjne z wyrażeniem CASE albo automatyczne indeksy kluczy obcych.

Najważniejsze decyzje odwzorowania:

- Każdą regułę EXCLUDE zastępuje para wyzwalaczy `BEFORE INSERT` i `BEFORE UPDATE`. Wyzwalacz blokuje wiersz porządkujący (`SELECT … FOR UPDATE` na skrytce albo rezerwacji), szuka kolizji przez indeks i przy kolizji zgłasza błąd `SIGNAL SQLSTATE '45000'`. Dwie reguły nie mają wiersza nadrzędnego, więc blokują wiersz pomocniczej tabeli `excl_guard_`. Ta tabela nie należy do zbioru danych i nie liczy się do jego rozmiaru.
- Indeks częściowy staje się indeksem funkcyjnym na wyrażeniu `CASE WHEN <warunek> THEN <klucz> END`. Zapytanie, które ma z niego korzystać, powtarza to samo wyrażenie.
- Położenie to `POINT SRID 4326` z indeksem SPATIAL. Wyszukiwanie w promieniu filtruje najpierw prostokątem (`MBRContains`), a potem odległością `ST_Distance_Sphere`.
- Kolumny wyliczane w złożonych kluczach obcych mają postać `GENERATED ALWAYS AS … STORED`. Kolumna `id_` nie ma `AUTO_INCREMENT`, bo kolumna wyliczana nie może od niej zależeć. Identyfikatory nadaje generator.
- Tabela `audit_event_` ma dodatkową kolumnę pochodną `changes_new_` z wartościami `new` tablicy zmian. Na niej działa indeks wielowartościowy JX2 (rozdz. 9).

Dane ładuje `LOAD DATA` bez kluczy obcych. Klucze obce, indeksy funkcyjne i wyzwalacze powstają po załadowaniu, a `ANALYZE TABLE` liczy statystyki 13 tabel.

{{ dataset("types", "Typy kolumn PostgreSQL i ich odpowiedniki w MySQL") }}

{{ dataset("objects", "Ograniczenia i indeksy PostgreSQL odwzorowane w MySQL inaczej") }}

## Zgodność danych w czterech SZBD

Po załadowaniu `make verify` odtwarza z każdej bazy 13 tabel w postaci kanonicznej. PostgreSQL i MySQL czytają tabele wprost, MongoDB rozwija dokumenty osadzone, a Neo4j czyta węzły i końce relacji. Wartości przechodzą normalizację: czas to milisekundy UTC, kwoty to grosze, skrót kodu to tekst szesnastkowy, punkt to długość i szerokość geograficzna, a JSON jest parsowany, więc kolejność kluczy nie ma znaczenia. Skrót SHA-256 tabeli to suma skrótów jej wierszy modulo 2^256, więc kolejność wierszy też nie ma znaczenia.

@Tab:parity podaje początek skrótu każdej tabeli. Skrót w komórce oznacza, że PostgreSQL, MySQL, MongoDB i Neo4j dały ten sam skrót co dane kanoniczne z plików Parquet. Każda różnica przerywa `make verify` błędem. Weryfikacja sprawdza też dane pochodne: `shipLinks` i id automatów w MongoDB, `SHIPS_TO` w Neo4j oraz `changes_new_` w MySQL. Ostatni wiersz tabeli podaje odległość Kraków Główny – Warszawa Centralna, którą każda baza liczy własną funkcją. Wynik musi mieścić się w przedziale 250–253 km. @Tab:load podaje czas ładowania i rozmiar bazy na dysku.

{{ dataset("parity", "Skróty SHA-256 tabel (pierwsze 12 znaków) równe w czterech SZBD") }}

{{ dataset("load", "Czas ładowania i rozmiar bazy na dysku") }}
