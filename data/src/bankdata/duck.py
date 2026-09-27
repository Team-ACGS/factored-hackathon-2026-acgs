import sys

import duckdb

from bankdata import settings
from bankdata.pipeline.schemas import TABLES

CURATED_HIVE_TYPES = "{'year': INTEGER, 'month': INTEGER}"
NO_FILES = "No files found"


def connect(s: settings.Settings | None = None) -> duckdb.DuckDBPyConnection:
    s = s or settings.load()
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{s.memory_limit}'")
    con.execute(f"SET threads={s.threads}")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET partitioned_write_flush_threshold=100000")
    con.execute(f"SET VARIABLE data_clock = DATE '{settings.DATA_CLOCK}'")
    if s.remote:
        con.execute("INSTALL httpfs; LOAD httpfs")
        con.execute("CREATE SECRET IF NOT EXISTS (TYPE s3, PROVIDER credential_chain)")
    for name, reason in register_tables(con, s).items():
        if NO_FILES not in reason:
            print(f"table {name} skipped: {reason}", file=sys.stderr)
    return con


def register_tables(con: duckdb.DuckDBPyConnection, s: settings.Settings) -> dict[str, str]:
    skipped = {}
    for name, table in TABLES.items():
        types = f", hive_types={CURATED_HIVE_TYPES}" if table.partitioned else ""
        glob = f"{s.curated}/{name}/**/*.parquet"
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{glob}', hive_partitioning=true{types})"
            )
        except duckdb.Error as e:
            skipped[name] = str(e).splitlines()[0]
    return skipped
