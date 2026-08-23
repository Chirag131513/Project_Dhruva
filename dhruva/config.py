"""Configuration loading, freezing and hashing.

Every experiment artefact records the hash of the config that produced it. If the hash differs
between two runs, their numbers are not comparable and the loader says so rather than letting
you quietly plot them on the same axes.

The `frozen` block of config.yaml corresponds to PROTOCOL sections 02, 05, 07, 10 and 12. It is
amendment-only after Block 0. `freeze()` writes a lock file; `check_lock()` refuses to proceed if
a frozen value has been edited in place, because choosing gamma or a cost constant after seeing
results is how an experiment is made to guarantee its own conclusion.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = REPO_ROOT / "results" / "protocol.lock"


@dataclass(frozen=True)
class Config:
    frozen: dict[str, Any]
    tuning: dict[str, Any]
    paths: dict[str, Any]
    amendments: list[dict[str, Any]]
    source: Path

    # -- convenience accessors, so call sites read as prose ---------------------------------
    @property
    def alpha(self) -> float:
        return float(self.frozen["alpha"])

    @property
    def gamma(self) -> float:
        return float(self.frozen["gamma"])

    @property
    def min_cell_n(self) -> int:
        return int(self.frozen["min_cell_n"])

    @property
    def base_seed(self) -> int:
        return int(self.frozen["base_seed"])

    @property
    def delay_days(self) -> int:
        return int(self.frozen["delay_days"])

    def data_dir(self) -> Path:
        """Where the IEEE-CIS CSVs live.

        Resolution order: the DHRUVA_DATA environment variable, then paths.data_dir in
        config.yaml. Absolute paths are honoured as-is so the ~700MB of raw data can sit OUTSIDE
        a synced folder -- inside OneDrive it triggers a full cloud sync of files that are
        gitignored and freely re-downloadable.

        The shipped default is the relative `data/`. It is gitignored, and it is where
        scripts/fetch_data.py puts things, so a fresh clone runs with no edit at all. This used
        to hold a machine-specific absolute path, which made the repository unrunnable for anyone
        else and published the author's home directory into a public repo. Set the environment
        variable instead of editing this file back:

            PowerShell   $env:DHRUVA_DATA = "C:\\path\\to\\dhruva-data"
            bash         export DHRUVA_DATA=/path/to/dhruva-data
        """
        raw = os.environ.get("DHRUVA_DATA") or self.paths["data_dir"]
        d = Path(str(raw)).expanduser()
        return d if d.is_absolute() else REPO_ROOT / d

    def results_dir(self) -> Path:
        d = REPO_ROOT / self.paths["results_dir"]
        d.mkdir(parents=True, exist_ok=True)
        return d

    # -- integrity --------------------------------------------------------------------------
    def hash(self) -> str:
        """SHA-256 over the frozen block only.

        Tuning parameters are excluded on purpose: they are engineering choices that cannot bias
        a hypothesis test, so changing a LightGBM leaf count should not invalidate comparability.
        Changing alpha, gamma or a cost constant should, and does.
        """
        payload = json.dumps(self.frozen, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def freeze(self) -> str:
        """Write the lock file. Called once, by Block 0."""
        h = self.hash()
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCK_PATH.write_text(
            json.dumps({"hash": h, "frozen": self.frozen}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return h

    def check_lock(self) -> None:
        """Raise if a frozen value changed after Block 0 without a recorded amendment."""
        if not LOCK_PATH.exists():
            raise RuntimeError(
                "Protocol not frozen. Run `python scripts/block0_audit.py` first -- it commits "
                "the pre-registered constants before any result can be produced."
            )
        locked = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if locked["hash"] == self.hash():
            return

        diffs = [
            f"    {k}: locked={locked['frozen'].get(k)!r} -> current={v!r}"
            for k, v in self.frozen.items()
            if locked["frozen"].get(k) != v
        ]
        raise RuntimeError(
            "FROZEN CONFIG CHANGED after Block 0.\n"
            + "\n".join(diffs)
            + "\n\n  PROTOCOL sections 02/05/07/10/12 are amendment-only. If this change is "
            "\n  intended, append it to `amendments` in config.yaml with a timestamp and reason, "
            "\n  then re-run block0 to re-freeze. Editing a constant in place after seeing "
            "\n  results is the failure mode the lock exists to prevent."
        )


def load(path: str | Path | None = None) -> Config:
    path = Path(path) if path else REPO_ROOT / "config.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Config(
        frozen=raw["frozen"],
        tuning=raw.get("tuning", {}),
        paths=raw.get("paths", {"data_dir": "data", "results_dir": "results"}),
        amendments=raw.get("amendments") or [],
        source=path,
    )
