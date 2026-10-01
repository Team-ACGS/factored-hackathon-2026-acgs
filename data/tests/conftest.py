import shutil
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from bankdata import duck
from bankdata.pipeline import ingest
from bankdata.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def s(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    root = tmp_path_factory.mktemp("root")
    shutil.copytree(FIXTURES / "raw", root / "raw")
    return Settings(root=str(root), memory_limit="512MB", threads=2, figures_dir=root / "figures")


@pytest.fixture(scope="session")
def con(s: Settings) -> Iterator[duckdb.DuckDBPyConnection]:
    con = duck.connect(s)
    ingest.ingest(con, s)
    duck.register_tables(con, s)
    yield con
    con.close()
