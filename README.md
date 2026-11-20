# Bagażomat

Projekt z przedmiotu Zaawansowane Technologie Bazodanowe na Politechnice Krakowskiej. Porównujemy operacje CRUD w PostgreSQL, MySQL, MongoDB i Neo4j na wspólnym zbiorze danych sieci przechowalni bagażu.

`make help` wyświetla dostępne polecenia. `make check` uruchamia kontrole repozytorium i wymaga Pythona 3.

Po sklonowaniu uruchom `git config core.hooksPath tools/hooks`, aby włączyć kontrolę komunikatów commitów.

[Model relacyjny](docs/design/schema.sql) · [Reguły obsługi](docs/design/NOTES.md) · [Harmonogram](report/chapters/13-harmonogram.md)

## Środowisko pomiarowe

Na hoście ARM64 z Docker Compose uruchom `make up ENGINE=pg`, a następnie `make ping ENGINE=pg`. Dostępne silniki to `pg`, `mysql`, `mongo` i `neo4j`. Przed zmianą silnika zatrzymaj bieżący przez `make down ENGINE=pg`. Bazy są dostępne wewnątrz sieci Compose.

`docker/copy-volume SOURCE_VOLUME TARGET_VOLUME auto` kopiuje zawartość jednego zatrzymanego woluminu do drugiego i zastępuje zawartość docelową. Tryb `always` wymaga kopii reflink, a `never` wymusza pełną kopię.
