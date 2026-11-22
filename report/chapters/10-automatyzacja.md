# Automatyzacja testów i generowania wyników

## Jedno polecenie

Druga opcja na ocenę 5.0 to automatyzacja całego procesu, od utworzenia baz do gotowych wyników i wykresów. Polecenie `make full` wykonuje cały łańcuch od pustych baz do wykresów, tabeli H1 i dokumentów. Domyślnie obejmuje rozmiary S, M i L, a `SIZES` wybiera inne, np. `make full SIZES=XS`. Generator, runner, analiza i budowanie dokumentów działają w kontenerach z `compose.bench.yaml` (rozdz. 4). Instrukcję uruchomienia podaje dodatek B.

@Fig:pipeline pokazuje kolejność kroków. Dla każdego rozmiaru łańcuch:

1. generuje dane do plików Parquet (`data`) i sprawdza je w DuckDB (`validate`);
2. ładuje dane do czterech SZBD (`load`) i sprawdza, że każdy SZBD odtwarza z nich te same 13 tabel (`verify`);
3. zapisuje migawki BASE i IDX każdego SZBD (`snapshots`);
4. mierzy scenariusze (`bench`) i zapisuje plany zapytań (`explain`, bez rozmiaru M);
5. sprawdza kompletność i zgodność wyników (`qa`).

Po wszystkich rozmiarach `h1` wyznacza komórki i werdykty hipotezy, `charts` rysuje wykresy, a `report` buduje sprawozdanie DOCX i PDF oraz prezentację PPTX. Kroki `load`, `verify`, `snapshots`, `bench` i `explain` działają osobno dla każdego SZBD i uruchamiają tylko ten SZBD, którego dotyczą, więc w czasie pomiaru działa jeden kontener bazy (rozdz. 5).

![Łańcuch kroków `make full`: kroki wykonywane dla każdego rozmiaru i kroki końcowe](report/assets/pipeline/pipeline.png){#fig:pipeline}

## Pomijanie kroków i wznawianie

Każdy krok ma klucz wejść. Dla danych to skrót plików generatora, profilu rozmiaru i wersji bibliotek, dla ładowania i weryfikacji `state_id` konfiguracji BASE, a dla migawek manifesty z bieżącym `state_id` (rozdz. 5). Krok wykonany wcześniej z tym samym kluczem `make full` pomija. Pomiar sprawdza każdy przebieg osobno po `qhash` i `state_id`, więc wykonuje tylko przebiegi, których brakuje. Po zmianie zapytania, indeksu albo ustawienia SZBD ponowne `make full` wykonuje tylko te kroki i przebiegi, których dotyczy zmiana. Kroki `qa`, `h1`, `charts` i `report` działają przy każdym wywołaniu, bo są krótkie i zależą od wszystkich wyników.

Przerwanie (Ctrl-C) nie traci wyników. Trwający krok dostaje sygnał przerwania, zapisane przebiegi zostają, jego czas trafia do dziennika, a kolejne `make full` zaczyna od przebiegów, których brakuje. Po błędzie kroku łańcuch przerywa dany rozmiar, wykonuje `qa` i przechodzi do następnego rozmiaru, a na końcu buduje wykresy i dokumenty z tego, co już jest. Polecenie kończy się kodem 0 tylko wtedy, gdy każdy wykonany krok się udał. W przeciwnym razie podaje pierwszy nieudany rozmiar i krok.

## Czas kroków

Każde wykonane wywołanie kroku dopisuje swój czas do `results/full-run.jsonl`. @Tab:steps sumuje te czasy dla każdego kroku i rozmiaru, łącznie dla czterech SZBD. Gdy krok wykonano kilka razy z tym samym kluczem wejść (`state_id`), na przykład po przerwaniu i wznowieniu, czasy wywołań są sumowane. Kroki `qa`, `h1`, `charts` i `report` działają przy każdym wywołaniu, więc tabela podaje ich ostatnie wykonanie. Plany zapytań (`explain`) nie powstają dla rozmiaru M (rozdz. 5).

{{ dataset("steps", "Czas kroków make full według rozmiaru, suma czterech SZBD") }}

Najwięcej czasu zajmuje pomiar (`bench`). Przy L kolejne są weryfikacja i ładowanie, bo obie przetwarzają 10 milionów rekordów w każdym SZBD. Migawki powstają szybko, bo kopia wolumenu przez reflink współdzieli bloki z oryginałem (rozdz. 5). Kroki końcowe trwają sekundy, więc przebudowanie wykresów i dokumentów po zmianie tekstu nie wymaga ponownych pomiarów.

## Uruchomienie z czystego klonu

Automatyzację sprawdzamy na świeżym klonie repozytorium: `git clone` zatwierdzonej wersji do pustego katalogu i `make full SIZES=XS` z osobną nazwą projektu Docker Compose, bez wcześniejszych wolumenów, migawek i wyników. @Tab:clean-clone podaje sprawdzoną wersję, datę, kod wyjścia i czas każdego kroku tego uruchomienia z `results/clean-clone.json`.

{{ dataset("clean-clone", "Uruchomienie make full SIZES=XS na czystym klonie repozytorium") }}
