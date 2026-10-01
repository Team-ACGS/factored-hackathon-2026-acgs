import shutil
from pathlib import Path

import duckdb
import pandas as pd

from bankdata.settings import Settings


def run(con: duckdb.DuckDBPyConnection, s: Settings, group: str) -> Path:
    sql_root = s.sql_dir / "figures" / group
    if not sql_root.is_dir():
        raise SystemExit(f"no figure group at {sql_root}")
    results: dict[Path, pd.DataFrame] = {}
    for path in sorted(sql_root.rglob("*.sql")):
        try:
            results[path.relative_to(sql_root).with_suffix(".csv")] = con.execute(path.read_text()).df()
        except duckdb.Error as e:
            raise SystemExit(f"{path.relative_to(s.sql_dir)}: {str(e).splitlines()[0]}") from e
    out = s.figures_dir / group
    shutil.rmtree(out, ignore_errors=True)
    for relative, df in results.items():
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(target, index=False)
    return out
