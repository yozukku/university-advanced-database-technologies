# Indeksy i plany zapytań

## Konfiguracje BASE i IDX

Każdy scenariusz z flagą BA mierzymy w dwóch konfiguracjach indeksów na tych samych danych. BASE to schemat w zaprojektowanej postaci: klucze główne i obce, ograniczenia unikalności i wykluczające, indeksy, które je obsługują, oraz własne indeksy schematu. IDX to BASE i cztery indeksy pomocnicze IX1–IX4 oraz dwa indeksy JSON, JX1 i JX2. Każdy indeks pomocniczy obsługuje jeden złożony odczyt: IX1 odczyt R4, IX2 odczyt R5, IX3 odczyt R6, a IX4 odczyt R7. Pełną listę indeksów razem z zapisami, które je utrzymują, zawiera rozdz. 11, a polecenia DDL dodatek C.

W BASE mierzymy 15 scenariuszy z flagą BA, a w IDX wszystkie 32. Każda para BASE i IDX startuje z migawki tych samych danych (rozdz. 5). Ten rozdział pokazuje scenariusze podstawowe. Scenariusze JSON J1, J2, J4 i J5 pokazuje rozdz. 9.

## Czasy BASE i IDX

@Tab:ba-core-L zestawia średnie czasy z trzech przebiegów w obu konfiguracjach dla rozmiaru L. Iloraz IDX / BASE poniżej 1 oznacza, że w IDX scenariusz działa szybciej, a powyżej 1, że wolniej. Wykresy od @fig:R4-ba do @fig:U5-ba pokazują te same pary dla rozmiarów S, M i L, z ilorazem nad każdą parą.

{{ dataset("ba-core-L", "Średnie czasy scenariuszy podstawowych w konfiguracjach BASE i IDX dla rozmiaru L") }}

Odczyty R4–R7 należą do zbioru H1-S, zapisy C2, C3, C4 i C6 do zbioru H1-I, a U1 i U5 do zbioru H1-U (rozdz. 11). U3 nie wchodzi do weryfikacji H1. Wyszukuje nieopłacone zamówienia po terminie płatności przez warunek na kolumnie `status_`, od której zaczyna się IX2, więc indeks może przyspieszyć wyszukanie wierszy do aktualizacji.

{{ fig("R4-ba", "R4 (przesyłki do odbioru według telefonu odbiorcy) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R5-ba", "R5 (ranking punktów według liczby zamówień z 30 dni) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R6-ba", "R6 (przychód netto punktów w miesiącu) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("R7-ba", "R7 (aktywność drzwi punktów w oknie 24 h) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

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

## Koszt budowy indeksów

Indeksy IDX powstają na załadowanych danych, po zapisaniu migawki BASE, po jednym poleceniu na indeks. @Tab:build-core podaje czas budowy i rozmiar każdego indeksu IX1–IX4 dla każdego rozmiaru danych. Rozmiar to `pg_relation_size` w PostgreSQL, liczba stron z `mysql.innodb_index_stats` razy rozmiar strony w MySQL, `indexSizes` z `$collStats` w MongoDB i rozmiar katalogu indeksu (`du`) w Neo4j. W MongoDB wszystkie cztery indeksy leżą w kolekcji `orders`, bo przesyłka, płatności i otwarcia skrytek są osadzone w dokumencie zamówienia.

{{ dataset("build-core", "Czas budowy i rozmiar indeksów IX1–IX4") }}
