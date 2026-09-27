import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DATA_DIR = Path(__file__).resolve().parents[2]
DATA_CLOCK = "2026-06-18"


@dataclass(frozen=True)
class Settings:
    root: str
    memory_limit: str
    threads: int
    sql_dir: Path = DATA_DIR / "sql"
    figures_dir: Path = DATA_DIR / "figures"

    @property
    def raw(self) -> str:
        return f"{self.root}/raw"

    @property
    def curated(self) -> str:
        return f"{self.root}/curated"

    @property
    def remote(self) -> bool:
        return self.root.startswith("s3://")



def load() -> Settings:
    load_dotenv(DATA_DIR / ".env")
    root = os.environ.get("BANKDATA_ROOT", ".cache")
    if not root.startswith("s3://"):
        root = str((DATA_DIR / root).resolve())
    return Settings(
        root=root.rstrip("/"),
        memory_limit=os.environ.get("BANKDATA_MEMORY_LIMIT", "2GB"),
        threads=int(os.environ.get("BANKDATA_THREADS", "4")),
    )
