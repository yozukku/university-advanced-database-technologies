import json
from hashlib import file_digest, sha256
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow.parquet as pq

from .audit import audit_events
from .ledger import ledger_tables
from .orders import order_tables
from .plan import make_plan
from .static import static_tables


def write_dataset(profile, output):
    plan = make_plan(profile)
    tables = dict(static_tables(profile, plan))
    orders = order_tables(profile, plan, tables)
    tables.update(orders.tables)
    tables.update(ledger_tables(profile, plan, orders))
    tables["audit_event_"] = audit_events(orders, tables["payment_"], tables["lockermat_cell_"])
    counts = {name: table.num_rows for name, table in tables.items()}
    if counts != plan.counts:
        raise ValueError(f"Table counts differ from plan: {counts}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix=f".{output.name}-") as temporary:
        staging = Path(temporary)
        for name, table in tables.items():
            pq.write_table(table, staging / f"{name}.parquet", compression="zstd")
        manifest = make_manifest(staging, profile, counts)
        (staging / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        output.mkdir(exist_ok=True)
        for name in tables:
            filename = f"{name}.parquet"
            (staging / filename).replace(output / filename)
        (staging / "manifest.json").replace(output / "manifest.json")
    return plan, tables


def make_manifest(directory, profile, counts):
    hashes = {}
    for name, count in sorted(counts.items()):
        path = directory / f"{name}.parquet"
        actual = pq.read_metadata(path).num_rows
        if actual != count:
            raise ValueError(f"{name}: expected {count} rows, found {actual}")
        with path.open("rb") as file:
            hashes[name] = file_digest(file, "sha256").hexdigest()
    dataset_sha256 = sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {
        "size": profile.size,
        "seed": profile.seed,
        "t0": profile.t0.isoformat(),
        "counts": counts,
        "sha256": hashes,
        "dataset_sha256": dataset_sha256,
    }
