import json
import os
from pathlib import Path

CELL = ("engine", "size", "config", "scenario", "qhash", "state_id")
FAILED = ("timeout", "error")


class Store:
    def __init__(self, directory):
        self.path = Path(directory) / "runs.jsonl"
        self.lines = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()] if self.path.exists() else []

    def cell(self, key):
        return {line["run"]: line for line in self.lines if all(line[field] == key[field] for field in CELL)}

    def pending(self, key, runs):
        done = self.cell(key)
        return [run for run in runs if run not in done], any(line["status"] in FAILED for line in done.values())

    def forget(self, engine, size, scenario):
        text = [raw for raw in self.path.read_text().splitlines(keepends=True) if raw.strip()] if self.path.exists() else []
        kept = [raw for raw in text if not matches(json.loads(raw), engine, size, scenario)]
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text("".join(kept))
        os.replace(temporary, self.path)
        self.lines = [json.loads(raw) for raw in kept]
        return len(text) - len(kept)

    def append(self, line):
        if line["run"] in self.cell(line):
            raise RuntimeError(f"Run {line['run']} of {line['scenario']} {line['engine']} {line['config']} is already stored")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as target:
            target.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
            target.flush()
            os.fsync(target.fileno())
        self.lines.append(line)


def matches(line, engine, size, scenario):
    return (line["engine"], line["size"], line["scenario"]) == (engine, size, scenario)
