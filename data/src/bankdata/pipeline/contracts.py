from dataclasses import dataclass

import duckdb

from bankdata.pipeline.schemas import TABLES, Table
from bankdata.settings import DATA_CLOCK

DICTIONARY_RATIO = (0.5, 2.0)
CLOCK_TOLERANCE_DAYS = 1


@dataclass(frozen=True)
class Result:
    table: str
    check: str
    ok: bool
    detail: str


def check(con: duckdb.DuckDBPyConnection, tables: list[str] | None = None) -> list[Result]:
    results = []
    for name in tables or list(TABLES):
        results.extend(check_table(con, TABLES[name]))
    return results


def check_table(con: duckdb.DuckDBPyConnection, table: Table) -> list[Result]:
    t = table.name
    try:
        rows = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    except duckdb.Error as e:
        return [Result(t, "exists", False, str(e).splitlines()[0])]
    results = [Result(t, "non_empty", rows > 0, f"{rows:,} rows")]
    if table.dictionary_rows:
        ratio = rows / table.dictionary_rows
        lo, hi = DICTIONARY_RATIO
        results.append(Result(t, "dictionary_ratio", lo <= ratio <= hi, f"{ratio:.2f} of {table.dictionary_rows:,}"))
    present = {c[0]: c[1] for c in con.execute(f"DESCRIBE {t}").fetchall()}
    missing = [c for c in table.columns if c not in present]
    results.append(Result(t, "declared_columns", not missing, f"missing {missing}" if missing else "all present"))
    drifted = [f"{c}:{present[c]}" for c, ty in table.columns.items() if c in present and present[c] != ty]
    results.append(Result(t, "declared_types", not drifted, f"drifted {drifted}" if drifted else "all match"))
    if table.key and table.key in present:
        n, distinct, nulls = con.execute(
            f"SELECT count(*), count(DISTINCT {table.key}), count(*) - count({table.key}) FROM {t}"
        ).fetchone()
        results.append(Result(t, "key_unique", n == distinct, f"{n - distinct:,} duplicate keys"))
        results.append(Result(t, "key_not_null", nulls == 0, f"{nulls:,} null keys"))
    if table.event_date and table.event_date in present:
        latest, limit = con.execute(
            f"SELECT max({table.event_date})::DATE, DATE '{DATA_CLOCK}' + {CLOCK_TOLERANCE_DAYS} FROM {t}"
        ).fetchone()
        ok = latest is not None and latest <= limit
        results.append(Result(t, "within_data_clock", ok, f"latest {latest}, clock {DATA_CLOCK}"))
    return results
