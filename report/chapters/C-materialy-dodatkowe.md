# Materiały dodatkowe

Dodatek zawiera treść wszystkich zapytań każdego SZBD dla 32 scenariuszy (rozdz. 6) oraz indeksy konfiguracji BASE i polecenia DDL indeksów IDX (rozdz. 8 i 9). Treść pochodzi z katalogu `docs/bench/scenarios.md`, który aplikacja testowa zapisuje z rejestru scenariuszy poleceniem `make catalogue`. Przy każdym scenariuszu podajemy flagi, indeks IDX i ustawienia z `bench/scenarios/ops.yaml`.

Oznaczenia w zapytaniach: `%(nazwa)s` i `%s` to parametry SQL, `$nazwa` to parametry Cypher, a `:nazwa` to parametry wywołań MongoDB. `{marks}` i `{rows}` to listy znaczników, które adapter MySQL wstawia dla partii. `<…>` oznacza wartość, którą klient wylicza w mierzonej jednostce z wyniku poprzedniego kroku, albo listę pól.

{{ insert("catalogue") }}
