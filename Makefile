.DEFAULT_GOAL := help

export COMPOSE_PROJECT_NAME ?= ztb
export ZTB_HOST_MACOS = $(shell sw_vers -productVersion 2>/dev/null || echo unknown)
export ZTB_HOST_MODEL = $(shell sysctl -n hw.model 2>/dev/null || echo unknown)
export ZTB_HOST_ORBSTACK = $(shell orb version 2>/dev/null || echo unknown)

SIZE ?= S
RESULTS_DIR ?= results
OUT ?= out

BENCH = docker compose -f compose.bench.yaml
APP = docker compose -p "$(COMPOSE_PROJECT_NAME)-app" -f compose.app.yaml
ENGINES = pg mysql mongo neo4j
SNAPSHOTS = out/snapshots/$(COMPOSE_PROJECT_NAME)
STATE = $(BENCH) run --rm -T --no-deps --build runner python -m bench.runner.state
CAFFEINATE = $(shell command -v caffeinate 2>/dev/null)
RUNNER = $(BENCH) run --rm -T --no-deps --build runner python -m bench.runner
RUNNER_ARGS = --size "$(SIZE)" $(foreach engine,$(ENGINE),--engine $(engine)) \
    $(foreach scenario,$(SCENARIO),--scenario $(scenario)) $(if $(TIMEOUT),--timeout $(TIMEOUT))

.PHONY: help check up ping down require-engine app-up app-down data validate load verify compose-config snapshots restore test-scenarios catalogue report charts bench status forget explain

help:
	@printf '%s\n' 'help  Pokaż dostępne polecenia' 'check Sprawdź komentarze i wpisy o autorstwie' \
	    'up ENGINE=pg|mysql|mongo|neo4j    Uruchom bazę do pomiarów' \
	    'ping ENGINE=pg|mysql|mongo|neo4j  Sprawdź wersję i architekturę bazy' \
	    'down ENGINE=pg|mysql|mongo|neo4j  Zatrzymaj bazę do pomiarów' \
	    'app-up   Uruchom aplikację' 'app-down Zatrzymaj aplikację' \
	    'data SIZE=XS|S|M|L Wygeneruj dane benchmarku' \
	    'validate SIZE=XS|S|M|L Sprawdź dane benchmarku' \
	    'load SIZE=XS|S|M|L [ENGINE=…] Załaduj dane benchmarku do czterech baz po kolei' \
	    'verify SIZE=XS|S|M|L Porównaj dane w czterech bazach z danymi kanonicznymi' \
	    'snapshots SIZE=XS|S|M|L [ENGINE=…] Zapisz migawki BASE i IDX załadowanych baz' \
	    'restore ENGINE=pg|mysql|mongo|neo4j SIZE=XS|S|M|L CONFIG=base|idx Odtwórz bazę z migawki' \
	    'test-scenarios SIZE=XS|S [K=…] Sprawdź scenariusze w czterech bazach na migawkach' \
	    'catalogue [CHECK=1] Zapisz katalog scenariuszy docs/bench/scenarios.md albo go sprawdź' \
	    'report [RESULTS_DIR=results] [OUT=out] Zbuduj sprawozdanie DOCX i PDF oraz prezentację PPTX' \
	    'charts [RESULTS_DIR=results] Narysuj wykresy scenariuszy i par BASE/IDX z wyników pomiarów' \
	    'bench SIZE=XS|S|M|L [ENGINE=…] [SCENARIO=…] [TIMEOUT=…] Zmierz brakujące przebiegi scenariuszy' \
	    'status SIZE=XS|S|M|L Pokaż zmierzone i brakujące komórki pomiarów' \
	    'forget ENGINE=… SIZE=… SCENARIO=… REASON=… Usuń przebiegi komórki, aby zmierzyć ją ponownie' \
	    'explain SIZE=XS|S|L [ENGINE=…] [SCENARIO=…] Zapisz brakujące plany zapytań i explain_summary.csv'

check:
	@tools/check-comments
	@tools/check-attribution

require-engine:
	@case "$(ENGINE)" in pg|mysql|mongo|neo4j) ;; *) echo 'Ustaw ENGINE na pg, mysql, mongo lub neo4j' >&2; exit 2;; esac

up: require-engine
	@running=$$($(BENCH) ps --status running --services) && \
	for service in $$running; do \
	    case " $(ENGINES) " in \
	        *" $$service "*) if [ "$$service" != "$(ENGINE)" ]; then echo "Działa już $$service" >&2; exit 1; fi;; \
	    esac; \
	done
	@$(BENCH) up -d --wait --build "$(ENGINE)"

ping: require-engine
	@$(BENCH) run --rm --no-deps --build runner
	@case "$(ENGINE)" in \
	    pg) $(BENCH) exec -T pg psql -U bench -d bagazomat -Atc 'select version(), postgis_version(), postgis_lib_version()';; \
	    mysql) $(BENCH) exec -T mysql sh -ec 'MYSQL_PWD="$$MYSQL_PASSWORD" mysql -u "$$MYSQL_USER" -NB -e "select version(), @@version_compile_machine"';; \
	    mongo) $(BENCH) exec -T mongo mongosh --quiet --norc --eval 'print(db.version()); if (rs.status().ok !== 1) quit(1)';; \
	    neo4j) $(BENCH) exec -T neo4j sh -ec 'cypher-shell -u neo4j -p "$${NEO4J_AUTH#*/}" "CALL dbms.components() YIELD versions RETURN versions"';; \
	esac
	@arch=$$($(BENCH) exec -T "$(ENGINE)" uname -m) && printf '%s\n' "$$arch" && test "$$arch" = aarch64

down: require-engine
	@$(BENCH) stop "$(ENGINE)"

app-up:
	@$(APP) up -d --wait --build

app-down:
	@$(APP) down

data:
	@$(BENCH) run --rm -T --no-deps --build runner python -m bench.gen --size "$(SIZE)"

validate:
	@$(BENCH) run --rm -T --no-deps --build runner python -m bench.check --size "$(SIZE)"

ifdef ENGINE
load: up
	@$(BENCH) run --rm -T --no-deps --build runner python -m bench.load.$(ENGINE) --size "$(SIZE)"
else
load:
	@$(BENCH) stop $(ENGINES)
	@for engine in $(ENGINES); do \
	    $(MAKE) --no-print-directory load ENGINE=$$engine && \
	    $(BENCH) stop $$engine || exit 1; \
	done
endif

verify:
	@$(BENCH) stop $(ENGINES)
	@for engine in $(ENGINES); do \
	    $(MAKE) --no-print-directory up ENGINE=$$engine && \
	    $(BENCH) run --rm -T --no-deps --build runner python -m bench.check.verify --size "$(SIZE)" --engine $$engine && \
	    $(BENCH) stop $$engine || exit 1; \
	done
	@$(BENCH) run --rm -T --no-deps runner python -m bench.check.verify --size "$(SIZE)"

compose-config:
	@mkdir -p "$(SNAPSHOTS)" && $(BENCH) --profile '*' config --format json > "$(SNAPSHOTS)/compose.json"

snapshots: compose-config
	@$(BENCH) stop $(ENGINES)
	@for engine in $(or $(ENGINE),$(ENGINES)); do \
	    $(MAKE) --no-print-directory up ENGINE=$$engine && \
	    $(STATE) snapshots --size "$(SIZE)" --engine $$engine || exit 1; \
	done

restore: require-engine compose-config
	@case "$(CONFIG)" in base|idx) ;; *) echo 'Ustaw CONFIG na base lub idx' >&2; exit 2;; esac
	@$(BENCH) create "$(ENGINE)"
	@$(STATE) restore --size "$(SIZE)" --engine "$(ENGINE)" --config "$(CONFIG)"

test-scenarios: compose-config
	@$(BENCH) stop $(ENGINES)
	@$(BENCH) create $(ENGINES)
	@$(BENCH) run --rm -T --no-deps --build runner python -m pytest -p no:cacheprovider tests/scenarios --size "$(SIZE)" $(if $(K),-k "$(K)")

catalogue:
	@$(BENCH) run --rm -T --no-deps --build runner python -m bench.scenarios.catalogue $(if $(CHECK),--check)

report:
	@$(BENCH) run --rm -T --no-deps --build report python -m bench.report --results "$(RESULTS_DIR)" --out "$(OUT)"

charts:
	@$(BENCH) run --rm -T --no-deps --build report python -m bench.analysis.charts --results "$(RESULTS_DIR)"

bench: compose-config
	@$(BENCH) stop $(ENGINES)
	@$(BENCH) create $(ENGINES)
	@$(if $(CAFFEINATE),$(CAFFEINATE) -ims) $(RUNNER) run $(RUNNER_ARGS)

status: compose-config
	@$(RUNNER) status $(RUNNER_ARGS)

forget:
	@test -n "$(ENGINE)" -a -n "$(SCENARIO)" -a -n "$(REASON)" || { echo 'Ustaw ENGINE, SCENARIO i REASON' >&2; exit 2; }
	@$(RUNNER) forget $(RUNNER_ARGS) --reason "$(REASON)"

explain: compose-config
	@$(BENCH) stop $(ENGINES)
	@$(BENCH) create $(ENGINES)
	@$(RUNNER) explain $(RUNNER_ARGS)
