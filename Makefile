.DEFAULT_GOAL := help

export COMPOSE_PROJECT_NAME ?= ztb
export ZTB_HOST_MACOS = $(shell sw_vers -productVersion 2>/dev/null || echo unknown)
export ZTB_HOST_MODEL = $(shell sysctl -n hw.model 2>/dev/null || echo unknown)
export ZTB_HOST_ORBSTACK = $(shell orb version 2>/dev/null || echo unknown)

SIZE ?= S

BENCH = docker compose -f compose.bench.yaml
APP = docker compose -p "$(COMPOSE_PROJECT_NAME)-app" -f compose.app.yaml
ENGINES = pg mysql mongo neo4j

.PHONY: help check up ping down require-engine app-up app-down data validate load verify

help:
	@printf '%s\n' 'help  Pokaż dostępne polecenia' 'check Sprawdź komentarze i wpisy o autorstwie' \
	    'up ENGINE=pg|mysql|mongo|neo4j    Uruchom bazę do pomiarów' \
	    'ping ENGINE=pg|mysql|mongo|neo4j  Sprawdź wersję i architekturę bazy' \
	    'down ENGINE=pg|mysql|mongo|neo4j  Zatrzymaj bazę do pomiarów' \
	    'app-up   Uruchom aplikację' 'app-down Zatrzymaj aplikację' \
	    'data SIZE=XS|S|M|L Wygeneruj dane benchmarku' \
	    'validate SIZE=XS|S|M|L Sprawdź dane benchmarku' \
	    'load ENGINE=pg|mysql|mongo|neo4j SIZE=XS|S|M|L Załaduj dane benchmarku do bazy' \
	    'verify SIZE=XS|S|M|L Porównaj dane w czterech bazach z danymi kanonicznymi'

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

load: up
	@$(BENCH) run --rm -T --no-deps --build runner python -m bench.load.$(ENGINE) --size "$(SIZE)"

verify:
	@$(BENCH) stop $(ENGINES)
	@for engine in $(ENGINES); do \
	    $(MAKE) --no-print-directory up ENGINE=$$engine && \
	    $(BENCH) run --rm -T --no-deps --build runner python -m bench.check.verify --size "$(SIZE)" --engine $$engine && \
	    $(BENCH) stop $$engine || exit 1; \
	done
	@$(BENCH) run --rm -T --no-deps runner python -m bench.check.verify --size "$(SIZE)"
