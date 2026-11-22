# Instrukcja uruchomienia

Dodatek opisuje, jak odtworzyć pomiary i dokumenty jednym poleceniem `make full` (rozdz. 10).

## Wymagania wstępne

- Komputer z procesorem ARM64, na którym działa Docker z Docker Compose v2. Pomiary w tym sprawozdaniu wykonaliśmy na komputerze Apple Silicon z OrbStack (rozdz. 5). `make ping` sprawdza, że baza działa w architekturze `aarch64`.
- Maszyna wirtualna Dockera z co najmniej 16 GB pamięci RAM. Kontener SZBD ma limit 8 GB pamięci, a obok niego działają kontenery `runner` i `report`.
- Wolne miejsce na dysku maszyny wirtualnej Dockera, według zajętości zmierzonej przy ładowaniu: około 15 GB dla rozmiaru S lub M i około 30 GB dla rozmiaru L, do tego około 6,5 GB na obrazy. Najwięcej zajmuje MySQL: każda kopia jego woluminu, czyli wolumin roboczy i migawki BASE i IDX, zawiera własny dziennik redo o rozmiarze 4 GB. `make clean SIZE=…` usuwa dane i migawki rozmiaru, a wyniki w `results/` zostawia.
- System plików maszyny wirtualnej z obsługą kopii reflink. Migawki kopiujemy poleceniem `cp -a --reflink=auto` (rozdz. 5). Przy rozmiarach S, M i L kopie były wykonane jako reflink (@tab:env). Bez reflinku kopia jest pełna: zajmuje więcej miejsca, a odtworzenie migawki przed każdym przebiegiem zapisu trwa dłużej. Odtworzenie migawki odbywa się poza mierzonym czasem scenariusza, więc reflink zmienia czasy kroków w @tab:steps, a nie czasy scenariuszy.
- Git, GNU Make i Python 3. Python na hoście uruchamia tylko kontrole `make check`. Generator, ładowanie, pomiary, wykresy i dokumenty działają w kontenerach.

## Uruchomienie

```sh
git clone https://github.com/yozukku/university-advanced-database-technologies.git
cd university-advanced-database-technologies
make full SIZES=XS
make full
```

`make full SIZES=XS` wykonuje cały łańcuch na najmniejszym zbiorze danych. Wyniki zapisuje w `out/xs/results/`, a dokumenty w `out/xs/`. Służy do sprawdzenia stanowiska przed pełnym pomiarem.

`make full` bez parametrów wykonuje łańcuch dla rozmiarów S, M i L po kolei: `data` → `validate` → `load` → `verify` → `snapshots` → `bench` → `explain` → `qa` dla każdego rozmiaru, a na końcu `charts` → `h1` → `report` (rozdz. 10). Kroku `explain` nie ma dla rozmiaru M. Czas kroków przy naszym pomiarze podaje @tab:steps. Na macOS Makefile uruchamia łańcuch pod `caffeinate -ims`, więc komputer nie przechodzi w stan uśpienia.

Wyniki trafiają do katalogu `results/`, a dokumenty do `out/`: `out/sprawozdanie.docx`, `out/sprawozdanie.pdf` i `out/prezentacja.pptx`.

## Wznowienie i pojedyncze kroki

- Ponowne `make full` pomija kroki wykonane wcześniej z tymi samymi danymi wejściowymi i mierzy tylko brakujące przebiegi. Przerwany łańcuch wystarczy więc uruchomić jeszcze raz.
- `make full SIZES=L UNTIL=snapshots` kończy łańcuch po wskazanym kroku.
- `make status SIZE=L` pokazuje zmierzone i brakujące komórki pomiarów.
- `make report` buduje sprawozdanie i prezentację z istniejących wyników, bez pomiarów.
- `make help` wypisuje wszystkie polecenia z opisem.

## Aplikacja Bagażomat

`make app-up` uruchamia aplikację Bagażomat z bazą PostgreSQL, serwerem Keycloak, backendem i frontendem (rozdz. 4). Konta demonstracyjne to `anna` i `jan`. `make app-down` zatrzymuje aplikację.
