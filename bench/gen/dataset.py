import pyarrow.parquet as pq

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
    output.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        pq.write_table(table, output / f"{name}.parquet", compression="zstd")
    return plan, tables
