# Dane półstrukturalne (JSON)

## Scenariusze JSON

Scenariusze J1–J6 działają na dzienniku zdarzeń `audit_event_` (rozdz. 3) w PostgreSQL, MySQL i MongoDB. Neo4j przechowuje pola `actor_` i `changes_` jako tekst JSON i nie indeksuje ich ścieżek, więc nie wykonuje serii J. Katalog scenariuszy zawiera rozdz. 6. Wykresy od @fig:J1 do @fig:J6 pokazują średnie czasy w konfiguracji IDX dla rozmiarów S, M i L.

{{ fig("J1", "Czas zapisu J1 (dopisanie zdarzeń audytu) w trzech SZBD") }}

{{ fig("J2", "Czas odczytu J2 (RODO art. 15: zdarzenia osoby według e-maila lub telefonu) w trzech SZBD") }}

{{ fig("J3", "Czas odczytu J3 (istnienie kluczy JSON) w trzech SZBD; skala logarytmiczna") }}

{{ fig("J4", "Czas odczytu J4 (element tablicy zmian) w trzech SZBD") }}

{{ fig("J5", "Czas aktualizacji J5 (RODO art. 17: pseudonimizacja) w trzech SZBD") }}

{{ fig("J6", "Czas usuwania J6 (retencja zdarzeń audytu) w trzech SZBD; skala logarytmiczna") }}

## Indeksy JSON: BASE i IDX

IDX dodaje dwa indeksy JSON. JX1 indeksuje e-mail i telefon w migawce aktora i obsługuje odczyt J2. JX2 indeksuje nazwy pól i nowe wartości w liście zmian i obsługuje odczyt J4. PostgreSQL używa indeksów wyrażeń B-drzewa dla JX1 i indeksu GIN `jsonb_path_ops` dla JX2. MySQL używa indeksów funkcyjnych dla JX1 i indeksu wielowartościowego dla JX2. MongoDB używa indeksów pól osadzonych dla JX1 i indeksu wielokluczowego tablicy dla JX2.

@Tab:ba-json-L zestawia średnie czasy scenariuszy JSON z flagą BA w obu konfiguracjach dla rozmiaru L. J2 i J4 należą do zbioru H1-S, a J1 do zbioru H1-I (rozdz. 11). J5 nie wchodzi do weryfikacji H1: wyszukuje zdarzenia osoby po e-mailu lub telefonie, czyli przez JX1, więc indeks może przyspieszyć wyszukanie wierszy do aktualizacji. Wykresy od @fig:J1-ba do @fig:J5-ba pokazują pary dla rozmiarów S, M i L.

{{ dataset("ba-json-L", "Średnie czasy scenariuszy JSON w konfiguracjach BASE i IDX dla rozmiaru L") }}

{{ fig("J1-ba", "J1 (dopisanie zdarzeń audytu) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J2-ba", "J2 (RODO art. 15) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J4-ba", "J4 (element tablicy zmian) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

{{ fig("J5-ba", "J5 (RODO art. 17: pseudonimizacja) w konfiguracjach BASE i IDX; skala logarytmiczna") }}

## Ścieżki dostępu

@Tab:access-json-L pokazuje plany BASE i IDX dla rozmiaru L. Dla J2 i J4 to plan całego zapytania, a dla J5 plan zapytania, które wyszukuje zdarzenia do zmiany. Kolumny mają to samo znaczenie co w rozdz. 8.

{{ dataset("access-json-L", "Ścieżki dostępu i przejrzane wiersze w planach scenariuszy JSON dla rozmiaru L") }}

## Rozmiar i czas budowy indeksów JSON

@Tab:build-json podaje czas budowy i rozmiar indeksów JX1 i JX2 dla każdego rozmiaru danych. JX1 to w każdym SZBD dwa indeksy, osobno dla e-maila i telefonu. Rozmiar mierzymy tak samo jak w rozdz. 8.

{{ dataset("build-json", "Czas budowy i rozmiar indeksów JSON JX1 i JX2") }}
