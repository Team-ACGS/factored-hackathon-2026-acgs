import shutil
from pathlib import Path

import duckdb

from bankdata import duck
from bankdata.pipeline import contracts, ingest
from bankdata.pipeline.schemas import TABLES
from bankdata.settings import Settings


def test_partitioned_tables_are_written_by_year_and_month(
    s: Settings, con: duckdb.DuckDBPyConnection
) -> None:
    files = list(Path(s.curated, "transactions").glob("year=*/month=*/*.parquet"))
    assert files
    assert Path(s.curated, "customers", "customers.parquet").exists()


def test_curated_has_every_declared_column(con: duckdb.DuckDBPyConnection) -> None:
    for table in TABLES.values():
        present = {row[0] for row in con.execute(f"DESCRIBE {table.name}").fetchall()}
        assert set(table.columns) <= present, table.name
        if table.partitioned:
            assert {"year", "month", "day"} <= present


def test_contracts_pass_on_clean_fixtures(con: duckdb.DuckDBPyConnection) -> None:
    failed = [r for r in contracts.check(con) if not r.ok and r.check != "dictionary_ratio"]
    assert failed == []


def test_contracts_catch_duplicate_key_and_future_row(s: Settings, tmp_path: Path) -> None:
    root = tmp_path / "dirty"
    shutil.copytree(Path(s.root, "raw"), root / "raw")
    csv = next((root / "raw" / "complaints").rglob("*.csv"))
    lines = csv.read_text().splitlines()
    row = lines[1].split(",")
    row[1] = "2031-01-01 00:00:00"
    csv.write_text("\n".join([*lines, lines[1], ",".join(row)]) + "\n")
    dirty = Settings(root=str(root), memory_limit="512MB", threads=2)
    con = duck.connect(dirty)
    ingest.ingest(con, dirty, ["complaints"])
    duck.register_tables(con, dirty)
    results = {r.check: r for r in contracts.check_table(con, TABLES["complaints"])}
    assert not results["key_unique"].ok
    assert not results["within_data_clock"].ok
