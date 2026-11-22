# Wnioski, rekomendacja i zagrożenia trafności

Rozdział zbiera wnioski z rozdz. 7–11, rekomenduje SZBD dla Bagażomatu i wymienia ograniczenia, które wpływają na trafność wyników. Tabele tego rozdziału, podobnie jak tabele rozdz. 7–11, powstają z katalogu `results/` przy budowaniu sprawozdania.

## Porównanie SZBD

@Tab:summary-L podsumowuje konfigurację IDX przy rozmiarze L. Dla każdego scenariusza wskazujemy najszybszy SZBD. Dla scenariuszy podstawowych liczymy też średnią geometryczną krotności czasu SZBD względem najszybszego SZBD w tym samym scenariuszu, czyli wartości z @fig:heatmap-L uśrednione po 26 scenariuszach. Najszybszy SZBD ma krotność 1.

{{ dataset("summary-L", "Najszybszy SZBD i średnia krotność czasu względem najszybszego przy rozmiarze L, konfiguracja IDX") }}

- PostgreSQL jest najszybszy w większości scenariuszy i ma najmniejszą średnią krotność. Wygrywa odczyty ze złączeniami i agregacją (R1, R2, R4–R7), zapytanie przestrzenne R3, zapisy partiami C1, C2, C5 i C6 oraz większość usunięć. Najwolniejszy z czterech SZBD jest w aktualizacjach zbiorowych U4 i U6 (@tab:U).
- MySQL wygrywa aktualizacje według klucza U1 i U5 oraz zbiorowe unieważnienie kodów U6. Przy L ma też najkrótsze czasy rezerwacji C3 i nadania przesyłki C4, ale w C3 i C4 kolejność MySQL i PostgreSQL odwraca się przy rozmiarze S, a różnice leżą w granicach zmienności między sesjami pomiarowymi (rozdz. 7).
- MongoDB wygrywa aktualizacje zbiorowe U3 i U4 oraz usunięcie D5. W tych scenariuszach jedna operacja na dokumencie zmienia albo usuwa razem z nim dane osadzone: etapy i kody zamówienia albo skrytki automatu. Wygrywa też R8, bo przechodzi po kolekcji połączeń `shipLinks` wyliczonej przy ładowaniu (rozdz. 3), oraz zapis J1 i scenariusze JSON J4 i J5.
- Neo4j nie jest najszybszy w żadnym scenariuszu podstawowym, także w przejściu po połączeniach przesyłek R8. Każdy przebieg zapisu w Neo4j obejmuje kompilację zapytań na świeżo uruchomionej JVM (rozdz. 5). Neo4j nie wykonuje scenariuszy JSON, bo nie przechowuje zagnieżdżonych map we właściwościach (rozdz. 9).

Model danych wyjaśnia część różnic (@tab:models). Zamówienie osadzone w jednym dokumencie MongoDB przyspiesza operacje na całym zamówieniu, a model relacyjny z indeksami na kluczach obcych wygrywa odczyty, które łączą wiele tabel i agregują dane.

## Indeksy i hipoteza H1

Werdykt ogólny H1 brzmi *obalona*, podobnie jak werdykt każdego z czterech SZBD (@tab:h1-verdicts). Według reguły z rozdz. 11 wystarcza jedna komórka, która nie potwierdza hipotezy. Obraz poszczególnych części hipotezy jest jednak różny (@tab:h1-L):

- SELECT: 21 z 22 komórek odczytu potwierdza hipotezę. Plan IDX używa dodanego indeksu, a czas spada. W R4 i J2 odczyt jest w IDX ponad dziesięciokrotnie szybszy we wszystkich SZBD. Indeks zastępuje tam skan całej tabeli lub kolekcji odczytem kilku wierszy (@tab:access-core-L, @tab:access-json-L).
- UPDATE: wszystkie 8 komórek potwierdza hipotezę. Zmiana kolumny z kluczem indeksu wymaga usunięcia starego i wstawienia nowego wpisu indeksu, więc U1 i U5 działają w IDX wolniej.
- INSERT: 13 z 19 komórek potwierdza hipotezę. Wyraźny koszt widać w J1, gdzie każde zdarzenie audytu dodaje kilka wpisów indeksów JSON. Sześć komórek, które nie potwierdzają hipotezy, to zapisy C3, C4 i C6.

@Tab:failing-L zestawia zakres min–max trzech przebiegów BASE i IDX dla każdej komórki, która nie potwierdza hipotezy. Kolumna „Ścieżka dostępu IDX” podaje plan odczytu, a dla C6 plan wyszukania wierszy do zapisu.

{{ dataset("failing-L", "Komórki H1, które nie potwierdzają hipotezy przy rozmiarze L: zakres przebiegów i plan IDX") }}

### PostgreSQL: R5 i C4

R5 to jedyny odczyt, który nie potwierdza hipotezy. Plan IDX w PostgreSQL nie używa IX2 i jest taki sam jak plan BASE: równoległy skan sekwencyjny tabel `order_` i `reservation_` ze złączeniem haszującym, z tą samą liczbą przejrzanych wierszy (@tab:access-core-L). Warunek na statusie i dacie utworzenia wybiera około 9% zamówień, a zapytanie i tak łączy je z etapami z tabeli `reservation_`. Optymalizator ocenia, że przy takiej selektywności skan sekwencyjny jest tańszy od odczytu przez indeks. Średnia IDX jest wyższa o kilka procent, a różnicę daje głównie jeden dłuższy przebieg IDX (dodatek A). Ten sam plan bez indeksu daje w R5 najkrótszy czas z czterech SZBD (@tab:R). W pozostałych trzech SZBD plan IDX używa IX2 i odczyt działa szybciej.

C4 wstawia w jednej transakcji dziewięć wierszy w pięciu tabelach, a dodane indeksy IX1, IX2 i IX3 dostają po jednym wpisie. Czas transakcji wyznaczają wyszukanie dwóch wolnych skrytek, kontrola nakładania rezerwacji przez ograniczenie wykluczające i zatwierdzenie z zapisem dziennika na dysk. Przebiegi IDX mają duży rozrzut, a zakresy BASE i IDX się nakładają. Koszt utrzymania trzech wpisów indeksu jest więc mniejszy od rozrzutu przebiegów i pomiar nie rozstrzyga kierunku.

### MySQL: C3 i C4

W MySQL rezerwacja C3 i nadanie przesyłki C4 działają przy L w IDX szybciej o kilka procent, a zakresy przebiegów BASE i IDX się nie nakładają. C3 jest w IDX szybszy także przy rozmiarach S i M, a C4 przy M, ale nie przy S (@tab:h1-S, @tab:h1-M). Poza indeksami znamy dwie różnice między konfiguracjami: nową próbkę statystyk tabel `shipment_`, `order_`, `payment_` i `cell_opening_` (rozdz. 5) oraz kolejność przebiegów, w której IDX następuje zaraz po BASE. Statystyki nie zmieniają planów w tych transakcjach, bo C3 i C4 czytają z tych tabel tylko `order_`, po kluczu głównym (rozdz. 11). W sesji diagnostycznej plany wyszukania wolnej skrytki i zapytania wyzwalacza były w BASE i IDX takie same, a IDX było wolniejsze od BASE w sześciu z ośmiu par C3 i C4, w obu kolejnościach przebiegów (rozdz. 8). Przewaga IDX w MySQL nie powtórzyła się więc poza sesją pomiarową i nie wynika z indeksów.

### MongoDB: C4

W MongoDB indeksy IX1, IX2 i IX3 leżą w kolekcji `orders`, bo przesyłka i płatności są osadzone w dokumencie zamówienia (rozdz. 8). C4 wstawia jeden dokument zamówienia na transakcję, więc IDX dodaje do każdej transakcji trzy klucze indeksów. Iloraz jest bliski 1, a zakres przebiegów IDX obejmuje zakres BASE. Koszt utrzymania indeksów ginie w rozrzucie przebiegów.

### Neo4j: C3 i C6

C3 w Neo4j ma iloraz bliski 1, a zakresy przebiegów BASE i IDX się nakładają, tak jak w C4 w PostgreSQL i MongoDB. C6 dopisuje opłaty za przetrzymanie bagażu w kilku dużych transakcjach. Wyszukanie wierszy do zapisu ma w BASE i IDX ten sam plan na indeksie `reservation_overdue__idx` (@tab:access-core-L). Przebiegi C6 w Neo4j mają w obu konfiguracjach największy rozrzut z czterech SZBD, a średnie różnią się o mniej niż rozrzut. Każdy przebieg zapisu w Neo4j zaczyna się na świeżej JVM (rozdz. 5), co zwiększa rozrzut czasów.

### Ocena wyniku

Wynik nie oznacza, że indeksy nie kosztują zapisów. Koszt utrzymania widać tam, gdzie indeks dostaje wiele wpisów w stosunku do pozostałej pracy zapisu: w J1 we wszystkich trzech SZBD oraz w sześciu z ośmiu komórek U1 i U5 iloraz wynosi co najmniej 1,1. W transakcjach C3 i C4 dodane indeksy dostają dwa lub trzy wpisy na transakcję, a czas wyznacza reszta pracy transakcji. Wtedy kierunek zmiany średniej rozstrzyga rozrzut przebiegów. Ta sama przyczyna sprawia, że kilka komórek potwierdza hipotezę tylko formalnie, z ilorazem między 1,00 a 1,02: C2 w PostgreSQL i Neo4j, C3 w PostgreSQL i MongoDB oraz U1 w PostgreSQL.

Jakościowa reguła bez progu (rozdz. 11) jest więc wrażliwa na rozrzut przebiegów przy ilorazach bliskich 1. Wniosek merytoryczny brzmi: indeksy znacząco przyspieszają odczyty, które bez nich skanują całą tabelę, i spowalniają zapisy, które zmieniają wiele kluczy indeksu. W krótkich transakcjach biznesowych koszt indeksów jest mniejszy od dokładności naszego pomiaru.

## Dane JSON

Indeksy JSON dają największe przyspieszenie odczytu w całym projekcie. J2, czyli wyszukanie zdarzeń osoby według e-maila lub telefonu na potrzeby RODO, w BASE przegląda cały dziennik zdarzeń, a w IDX odczytuje tylko zdarzenia tej osoby (@tab:access-json-L). Te same indeksy najbardziej spowalniają zapis: J1 w MySQL ma najwyższy iloraz IDX / BASE wśród wszystkich zapisów mierzonych w BASE i IDX (@tab:ba-json-L). PostgreSQL jest najszybszy w J2, J3 i J6, a MongoDB, który przechowuje dokumenty natywnie, w J1, J4 i J5. W Neo4j przechowujemy JSON jako tekst, bez indeksów ścieżek, co wyklucza ten SZBD z analizy danych półstrukturalnych.

## Rekomendacja dla Bagażomatu

Dla Bagażomatu rekomendujemy PostgreSQL. Przemawiają za tym trzy powody:

- Wydajność: przy rozmiarze L PostgreSQL jest najszybszy w większości scenariuszy i ma najmniejszą średnią krotność względem najszybszego SZBD (@tab:summary-L). Wygrywa odczyty, których używa aplikacja: szczegóły zamówienia R1, „Moje rezerwacje” R2, wyszukiwanie automatów z wolną skrytką R3 i przesyłki do odbioru R4.
- Integralność w bazie: ograniczenie wykluczające wyklucza nakładanie się rezerwacji jednej skrytki bez kodu aplikacji. MySQL potrzebuje do tego wyzwalaczy z blokadą, a MongoDB i Neo4j nie mają takich ograniczeń (rozdz. 2 i 3).
- Komplet funkcji w jednym SZBD: PostGIS obsługuje wyszukiwanie najbliższych automatów, a `jsonb` z indeksami GIN i indeksami wyrażeń obsługuje dziennik zdarzeń i żądania RODO.

Aplikację Bagażomat zbudowaliśmy na PostgreSQL przed pomiarami (rozdz. 4). Wyniki potwierdzają ten wybór. Rekomendacja ma też koszty. MySQL jest szybszy w aktualizacjach według klucza U1 i U5, a przy M i L ma też krótsze czasy rezerwacji C3, choć ta różnica leży w granicach zmienności między sesjami (rozdz. 7). PostgreSQL jest najwolniejszy w aktualizacjach zbiorowych U4 i U6. Te zapisy wykonują jednak zadania okresowe i administracyjne, a nie klient czekający na odpowiedź. PostgreSQL nie ma wbudowanego shardingu (rozdz. 2), ale przy rozmiarze L wszystkie scenariusze działają na jednym serwerze w czasie poniżej limitu.

Z analizy indeksów wynika wniosek dla schematu Bagażomatu: w PostgreSQL żaden plan IDX zapisany przy rozmiarze L nie używa IX2 (@tab:access-core-L). IX2 można więc pominąć w PostgreSQL. Pozostałe indeksy IDX skracają w PostgreSQL odczyty, które obsługują (R4, R6, R7, J2 i J4), i warto je zachować.

## Zagrożenia trafności

- Jedno stanowisko. Wszystkie pomiary pochodzą z jednego komputera Apple Silicon i maszyny wirtualnej OrbStack (rozdz. 5). Czasy bezwzględne zależą od dysku, systemu plików i wirtualizacji, więc przenosimy na inne środowiska tylko proporcje między SZBD, a nie wartości.
- Trzy przebiegi. Średnia z trzech przebiegów nie pozwala na test statystyczny. Kilka komórek ma współczynnik zmienności powyżej 15% (dodatek A). Przy ilorazach bliskich 1 rozstrzygnięcie H1 zależy od rozrzutu, co pokazuje @tab:failing-L.
- Jeden klient. Nie mierzymy pracy wielu równoczesnych klientów. Blokady, konflikty transakcji i rywalizacja o zasoby mogą zmienić kolejność SZBD, zwłaszcza w zapisach C3 i C4 i w MySQL, który zastępuje ograniczenia wykluczające wyzwalaczami z blokadą.
- Dane syntetyczne. Generator tworzy dane według rozkładów, które przyjęliśmy (rozdz. 3). Inne udziały statusów albo dat zmienią selektywność warunków, a od selektywności zależy plan, na przykład wybór skanu sekwencyjnego w R5 w PostgreSQL.
- Plany. Plan zapisujemy dla pierwszego zestawu parametrów scenariusza i tylko dla rozmiarów S i L. Inne parametry mogą dać inny plan. Plany zapytań wewnątrz transakcji C3 mamy tylko dla MySQL, z sesji diagnostycznej (rozdz. 8).
- Kolejność przebiegów. W każdej parze BASE i IDX runner mierzy najpierw BASE, a zaraz potem IDX (rozdz. 5). Kolejność nie jest równoważona, więc przy ilorazach bliskich 1 kierunek może od niej zależeć. W pilotażu przy S, gdy IDX szło przed BASE, MySQL miał w C2, C3 i C4 ilorazy 1,21, 1,19 i 1,10, a po zmianie kolejności 0,99, 0,97 i 1,04 (rozdz. 8).
- Sesje pomiarowe. Każdy rozmiar mierzyliśmy w osobnej sesji. W scenariuszach z 1000 krótkich transakcji (C3, C4, U2, D2) czas tego samego SZBD różni się między rozmiarami nawet dwukrotnie, choć praca jest stała, a w sesji diagnostycznej te różnice się nie powtórzyły (rozdz. 7). W C3 w MySQL około dwóch trzecich czasu zajmuje zatwierdzenie z zapisem na dysk, którego opóźnienie zmienia się między sesjami. Kolejność SZBD w tych scenariuszach nie jest więc pewna. Pary BASE i IDX mierzymy bezpośrednio po sobie, więc dotyczy ich to w mniejszym stopniu, ale skok czasu zdarza się też w trakcie jednej sesji (C3 w MongoDB przy M, rozdz. 8).
- Konfiguracja SZBD. Ustawienia opierają się na wspólnych zasadach, a nie na osobnym strojeniu każdego SZBD (rozdz. 5). W MySQL konfiguracja IDX ma nową próbkę statystyk tabel z indeksami IX1–IX4, więc BASE i IDX różnią się w MySQL nie tylko indeksami.
- Modele danych. Wyniki dotyczą naszych modeli: osadzenia w MongoDB, kolekcji `shipLinks`, węzłów i relacji w Neo4j oraz wyzwalaczy w MySQL (rozdz. 3). Inny model w tym samym SZBD może dać inne czasy.
- Pomiar po stronie klienta. Czas obejmuje sterownik języka Python i sieć Dockera. Sterowniki czterech SZBD mają różny narzut, który wchodzi do wyniku.
