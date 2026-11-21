import re

COUNTERS = {"pg": "blks_read", "mysql": "Innodb_buffer_pool_reads", "mongo": "bytes read into cache", "neo4j": "rchar"}
NEO4J_IO = "cat /proc/$(pgrep -o java)/io"
RCHAR = re.compile(r"^rchar: (\d+)$", re.MULTILINE)


def reads(session, container):
    if session.engine == "pg":
        session.fetch("select pg_stat_force_next_flush()")
        return session.fetch("select blks_read from pg_stat_database where datname = current_database()")[0][0]
    if session.engine == "mysql":
        return int(session.fetch("show global status like 'Innodb_buffer_pool_reads'")[0][1])
    if session.engine == "mongo":
        return session.client.admin.command("serverStatus")["wiredTiger"]["cache"]["bytes read into cache"]
    code, output = container.exec_run(["sh", "-c", NEO4J_IO], user="neo4j")
    if code:
        raise RuntimeError(output.decode())
    return int(RCHAR.search(output.decode())[1])


def delta(engine, before, after):
    return {"counter": COUNTERS[engine], "delta": after - before}
