from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class Profile:
    size: str
    records: int
    seed: int
    t0: datetime

    @property
    def destination(self):
        return Path("out/xs/data") if self.size == "XS" else Path("data") / self.size

    def rng(self, stream):
        return np.random.default_rng(np.random.SeedSequence([self.seed, stream]))


def load_profile(size, source=Path("profiles.yaml")):
    settings = yaml.safe_load(source.read_text())
    return Profile(
        size,
        settings["sizes"][size],
        settings["seed"],
        datetime.fromisoformat(settings["t0"]).astimezone(timezone.utc),
    )
