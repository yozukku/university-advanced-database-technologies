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

@Fig:h1-L pokazuje ilorazy IDX / BASE tych samych komórek na osi logarytmicznej. Odczyty leżą wyraźnie poniżej 1, a prawie wszystkie zapisy tuż przy 1, po obu jego stronach.

{{ fig("h1-L", "Iloraz IDX / BASE komórek H1 dla rozmiaru L; pusty znacznik: komórka nie potwierdza H1; skala logarytmiczna") }}

## Werdykt

@Tab:h1-verdicts podaje werdykt dla każdego SZBD i werdykt ogólny z `results/h1.json` oraz komórki, które nie potwierdzają hipotezy.

{{ dataset("h1-verdicts", "Werdykty hipotezy H1") }}

Hipoteza H1 jest obalona dla każdego z czterech SZBD, więc także ogólnie. Hipotezy nie potwierdza siedem komórek: jedna komórka odczytu (R5 w PostgreSQL) i sześć komórek zapisu (C3 i C4 w MySQL, C4 w PostgreSQL i MongoDB, C3 i C6 w Neo4j). Pozostałe 21 z 22 komórek odczytu i 21 z 27 komórek zapisu potwierdza hipotezę. Obie części zdania H1 mają więc różną siłę. Część o odczytach potwierdzamy z jednym wyjątkiem. Część o zapisach nie wytrzymuje reguły rozstrzygnięcia, bo koszt indeksu przy wstawianiu jest w większości komórek mniejszy od rozrzutu przebiegów.

## Analiza według SZBD

### PostgreSQL

R5 to jedyna komórka odczytu, która nie potwierdza H1, i to z powodu planu, nie czasu. Przy L planista PostgreSQL wybiera w BASE i w IDX ten sam plan: równoległy `Seq Scan` tabeli `order_` (proces główny i dwa procesy robocze) i złączenia haszowe z `reservation_`, którą oba plany czytają w całości. Oba plany przeglądają {{ examined("R5", "pg", "idx") }} wierszy, a IX2 nie występuje w planie IDX. Iloraz {{ ratio("R5", "pg") }} to różnica przebiegów tego samego planu. Przy S plan IDX tego samego zapytania czyta `order_` przez `Bitmap Index Scan` na IX2, choć warunek wybiera taki sam odsetek zamówień (około 9%) jak przy L. PostgreSQL wybiera plan według szacowanego kosztu. Przy L koszt równoległego przeglądu tabeli wychodzi mniejszy niż koszt odczytu przez indeks i pobrania wybranych wierszy. Indeks istnieje, ale planista uznaje go za nieopłacalny dla zapytania, które wybiera kilka procent tabeli i i tak czyta całą tabelę rezerwacji. Przy M R5 w IDX też działa wolniej, ale dla M planów nie zapisujemy.

C4 (nadanie przesyłki) ma iloraz {{ ratio("C4", "pg") }}. Scenariusz to 1000 osobnych transakcji. Każda wybiera wolne skrytki, wstawia zamówienie, przesyłkę, dwie rezerwacje, kody i opłatę i zatwierdza zmiany z pełną trwałością (rozdz. 5). IDX dodaje w tej transakcji trzy wpisy indeksów: IX1, IX2 i IX3. Ich koszt jest mały wobec wyszukania skrytek, kilku wstawień z kontrolą ograniczeń i zapisu dziennika WAL na dysk przy każdym zatwierdzeniu. Jeden z trzech przebiegów IDX był wyraźnie krótszy od pozostałych, a różnica średnich jest mniejsza od rozrzutu przebiegów IDX (dodatek A). Wynik C4 w PostgreSQL odczytujemy jako brak mierzalnej różnicy, a reguła liczy go jako kierunek przeciwny do H1.

Ten sam mechanizm widać w komórkach, które formalnie potwierdzają H1: C2 ma iloraz {{ ratio("C2", "pg") }}, a C3 {{ ratio("C3", "pg") }}. U1 ma iloraz {{ ratio("U1", "pg") }}, bo zmiana `status_` w PostgreSQL nie jest aktualizacją HOT już w BASE: kolumna występuje w warunku indeksu częściowego schematu, więc każda zmiana i tak aktualizuje wszystkie indeksy tabeli `order_`, a IDX dodaje do nich tylko IX2. Wyraźny koszt pokazują J1 ({{ ratio("J1", "pg") }}) i U5 ({{ ratio("U5", "pg") }}).

### MySQL

Odczyty potwierdzają H1 bez wyjątku. Nie potwierdzają jej C3 ({{ ratio("C3", "mysql") }}) i C4 ({{ ratio("C4", "mysql") }}). To jedyny przypadek, w którym kierunek wygląda na systematyczny: przebiegi obu konfiguracji mają mały rozrzut, a C3 w IDX działa szybciej przy S, M i L. Liczniki odczytów z dysku BASE i IDX w tych zapisach są prawie równe, więc różnica nie wynika z zimnej pamięci podręcznej. Przyczyny nie potrafimy wskazać na podstawie zebranych danych, bo plany zapisujemy tylko dla zapytań wyszukujących cele zapisów C6, U3 i J5, a nie dla C3 i C4. Możliwy powód to statystyki: po utworzeniu IX1–IX4 MySQL przelicza trwałe statystyki tabel `shipment_`, `order_`, `payment_` i `cell_opening_` (rozdz. 5), więc wyszukanie wolnej skrytki i wyzwalacze wykluczeń mogą w IDX dostać inny plan. Tej hipotezy nie sprawdziliśmy. Pozostałe zapisy w MySQL mają najwyraźniejszy koszt indeksów z czterech SZBD: U1 {{ ratio("U1", "mysql") }}, U5 {{ ratio("U5", "mysql") }} i J1 {{ ratio("J1", "mysql") }}.

### MongoDB

Nie potwierdza H1 tylko C4 ({{ ratio("C4", "mongo") }}). Nadanie przesyłki to 1000 transakcji, a każda wstawia jeden dokument zamówienia z osadzoną przesyłką, rezerwacjami i płatnością i kończy się zatwierdzeniem z zapisem dziennika na dysk (`j: true`). IDX dodaje do tego dokumentu wpisy IX1, IX2 i IX3 w kolekcji `orders`. Różnica średnich jest mniejsza od rozrzutu przebiegów IDX. C3 ma iloraz {{ ratio("C3", "mongo") }}, czyli również prawie bez zmian. Odczyty R4, R6 i R7 zyskują w MongoDB najwięcej z czterech SZBD, bo bez dodanego indeksu każde z tych zapytań przegląda całą kolekcję `orders` (`COLLSCAN`, rozdz. 8).

### Neo4j

Nie potwierdzają H1 C3 ({{ ratio("C3", "neo4j") }}) i C6 ({{ ratio("C6", "neo4j") }}). W obu ilorazach różnica jest mniejsza od rozrzutu przebiegów. C6 tworzy węzły opłat i ich relacje dla wszystkich zaległych rezerwacji, a IDX dodaje do tego wpisy IX3. Ilorazy bliskie 1 pokazują, że wpis indeksu zakresowego to niewielka część pracy obok tworzenia węzłów, relacji i zapisu dziennika transakcji. C4 w Neo4j potwierdza H1 ({{ ratio("C4", "neo4j") }}), a U1 i U5 pokazują wyraźny koszt. Neo4j nie wykonuje scenariuszy JSON, więc ma 10 komórek zamiast 13 (rozdz. 9).

## Wielkość zmian

Odczyty zyskują na indeksach od kilkudziesięciu procent do kilku rzędów wielkości. Największy zysk mają zapytania, które bez indeksu przeglądają całą tabelę, aby znaleźć kilka wierszy: R4 (iloraz od {{ ratio("R4", "mongo") }} w MongoDB do {{ ratio("R4", "neo4j") }} w Neo4j) i J2 (iloraz poniżej 0,001 we wszystkich trzech SZBD, rozdz. 9). Odczyty, które wybierają większy zakres i potem łączą tabele, zyskują mniej: R5, R6 i R7 mają ilorazy od {{ ratio("R7", "mongo") }} (R7 w MongoDB) do {{ ratio("R6", "pg") }} (R6 w PostgreSQL), poza R5 w PostgreSQL. Zysk jest zwykle największy w MongoDB, w której BASE nie ma do tych danych innej drogi niż przegląd całej kolekcji `orders`.

Zapisy w IDX działają od kilku procent szybciej do kilkudziesięciu procent wolniej. Wyraźny koszt mają zapisy, w których utrzymanie indeksów to duża część pracy: J1 wstawia dla każdego zdarzenia wpisy JX1 i wiele wpisów JX2, a U1 i U5 zmieniają kolumnę indeksu w wierszach wyszukanych po kluczu głównym, w transakcjach po 1000 wierszy. Rezerwacja C3 i nadanie przesyłki C4 to transakcje z wyszukaniem skrytek, kilkoma wstawieniami i zatwierdzeniem na dysk, średnio kilka milisekund każda. Dodatkowe dwa lub trzy wpisy indeksów nie zmieniają ich czasu w sposób mierzalny przy trzech przebiegach. Werdykt *obalona* wynika więc głównie z tych zapisów: kierunek bez progu liczbowego zalicza iloraz nieco poniżej 1 do komórek przeciwnych H1 tak samo, jak iloraz nieco powyżej 1 do komórek zgodnych z H1. Reguły nie zmieniamy po pomiarach, bo ustaliliśmy ją przed pierwszym pomiarem.

## Wyniki dla rozmiarów S i M

@Tab:h1-S i @tab:h1-M pokazują te same komórki dla rozmiarów S i M. Nie wchodzą one do werdyktu. Dla rozmiaru M nie zapisujemy planów, więc odczyty nie mają kontroli planu ani wyniku reguły.

{{ dataset("h1-S", "Komórki H1 dla rozmiaru S") }}

{{ dataset("h1-M", "Komórki H1 dla rozmiaru M") }}

Przy S i M odczyty również działają w IDX szybciej, z wyjątkiem R5 w PostgreSQL przy M. Przy S plan IDX każdego odczytu używa dodanego indeksu. Zbiór zapisów, w których IDX działa szybciej, zmienia się między rozmiarami, a we wszystkich trzech powtarza się tylko C3 w MySQL. To wspiera odczytanie tych komórek jako rozrzutu pomiaru, a nie trwałego zysku zapisu z indeksu.

[^regulamin-h1]: Politechnika Krakowska, „Zaawansowane technologie baz danych – Regulamin zajęć”, rok akademicki 2026/27, studia niestacjonarne, §3.
