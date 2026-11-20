import duckdb


def connect(directory, tables):
    db = duckdb.connect(config={"threads": 4})
    try:
        for name in tables:
            db.read_parquet(str(directory / f"{name}.parquet")).create_view(name)
    except Exception:
        db.close()
        raise
    return db


def require_empty(db, checks):
    errors = []
    for name, query in checks.items():
        failures = db.execute(query).fetchone()[0]
        if failures:
            errors.append(f"{name}: {failures}")
    if errors:
        raise ValueError("; ".join(errors))
