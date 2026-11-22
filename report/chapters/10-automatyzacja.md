# Automatyzacja testów i generowania wyników

Polecenie `make full` wykonuje cały łańcuch od pustych baz do wykresów, tabeli H1 i dokumentów. Każde wykonane wywołanie kroku dopisuje swój czas do `results/full-run.jsonl`. @Tab:steps sumuje te czasy dla każdego kroku i rozmiaru, łącznie dla czterech SZBD. Gdy krok wykonano kilka razy z tym samym kluczem wejść (`state_id`), na przykład po przerwaniu i wznowieniu, czasy wywołań są sumowane. Kroki `qa`, `charts`, `h1` i `report` działają przy każdym wywołaniu, więc tabela podaje ich ostatnie wykonanie. Plany zapytań (`explain`) nie powstają dla rozmiaru M (rozdz. 5).

{{ dataset("steps", "Czas kroków make full według rozmiaru, suma czterech SZBD") }}
