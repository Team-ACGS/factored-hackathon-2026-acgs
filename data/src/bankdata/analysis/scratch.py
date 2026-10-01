from pathlib import Path

import duckdb
import pandas as pd

from bankdata.settings import Settings


def run(
    con: duckdb.DuckDBPyConnection, s: Settings, names: list[str] | None = None
) -> dict[Path, pd.DataFrame]:
    folder = s.sql_dir / "scratch"
    paths = (
        [folder / f"{name.removesuffix('.sql')}.sql" for name in names]
        if names
        else sorted(folder.glob("*.sql"))
    )
    results: dict[Path, pd.DataFrame] = {}
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"no query at {path}")
        try:
            df = con.execute(path.read_text()).df()
        except duckdb.Error as e:
            raise SystemExit(f"{path.name}: {str(e).splitlines()[0]}") from e
        target = path.with_suffix(".csv")
        df.to_csv(target, index=False)
        results[target] = df
    return results
