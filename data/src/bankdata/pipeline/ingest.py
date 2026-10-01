import shutil
from pathlib import Path

import duckdb

from bankdata.duck import one
from bankdata.pipeline.schemas import TABLES, Table
from bankdata.settings import Settings

HIVE_TYPES = "{'year': INTEGER, 'month': INTEGER, 'day': INTEGER}"


def ingest(con: duckdb.DuckDBPyConnection, s: Settings, tables: list[str] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in tables or list(TABLES):
        table = TABLES[name]
        target = f"{s.curated}/{name}"
        _reset(s, target)
        if table.partitioned:
            _ingest_partitioned(con, s, table, target)
        else:
            _ingest_dimension(con, s, table, target)
        counts[name] = one(
            con, f"SELECT count(*) FROM read_parquet('{target}/**/*.parquet', hive_partitioning=true)"
        )[0]
    return counts


def _ingest_partitioned(con: duckdb.DuckDBPyConnection, s: Settings, table: Table, target: str) -> None:
    source = f"{s.raw}/{table.name}/*/*/*/*.csv"
    con.execute(f"""
        COPY (
            SELECT *
            FROM read_csv('{source}', union_by_name=true, hive_partitioning=true, hive_types={HIVE_TYPES})
        )
        TO '{target}' (FORMAT parquet, PARTITION_BY (year, month), OVERWRITE_OR_IGNORE true)
    """)


def _ingest_dimension(con: duckdb.DuckDBPyConnection, s: Settings, table: Table, target: str) -> None:
    source = f"{s.raw}/{table.name}.csv"
    con.execute(f"""
        COPY (SELECT * FROM read_csv('{source}', union_by_name=true))
        TO '{target}/{table.name}.parquet' (FORMAT parquet)
    """)


def _reset(s: Settings, target: str) -> None:
    if s.remote:
        return
    path = Path(target)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
