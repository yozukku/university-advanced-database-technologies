#!/bin/sh
set -u
cd /Users/agorokh/Projects/Uni/university-advanced-database-technologies
export COMPOSE_PROJECT_NAME=ztb
B="docker compose -f compose.bench.yaml"
R() { dir=$1; shift; echo "=== $(date +%T) $dir $*"; RESULTS_DIR=out/diag-g3/$dir $B run --rm -T --no-deps -e PYTHONPATH=/workspace runner python out/diag-g3/diag.py "$@"; echo "=== exit $?"; }
make compose-config
$B stop pg mysql mongo neo4j
$B create pg mysql mongo neo4j
$B build runner
mkdir -p out/diag-g3/prof
R rev-L order L mysql C3,C4 idx,base
R fwd-L order L mysql C3,C4 base,idx
for c in base idx; do for s in C3 C4; do R prof-L profile L $c $s out/diag-g3/prof/L-$c-$s.json; done; done
for c in base idx; do R prof-M profile M $c C3 out/diag-g3/prof/M-$c-C3.json; done
R rerun-M idx M pg:D2,mysql:D2,mongo:D2,pg:U2,mysql:U2
R rerun-L idx L pg:D2,mysql:D2,mongo:D2,pg:U2,mysql:U2
echo "=== $(date +%T) S load"
RESULTS_DIR=out/diag-g3/S-load make load SIZE=S ENGINE=mysql
RESULTS_DIR=out/diag-g3/S-load make snapshots SIZE=S ENGINE=mysql
$B stop mysql
for c in base idx; do for s in C3 C4; do R prof-S profile S $c $s out/diag-g3/prof/S-$c-$s.json; done; done
R fwd-S order S mysql C3,C4 base,idx
R rev-S order S mysql C3,C4 idx,base
echo "=== $(date +%T) done"
