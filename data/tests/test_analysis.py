from dataclasses import replace
from pathlib import Path

import duckdb
import pytest

from bankdata import duck
from bankdata.analysis import figures, scratch
from bankdata.settings import DATA_DIR, Settings

SQL = DATA_DIR / "sql"
FIGURES = sorted((SQL / "figures").rglob("*.sql"))


@pytest.mark.parametrize("path", FIGURES, ids=[str(p.relative_to(SQL)) for p in FIGURES])
def test_every_figure_query_runs(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    df = con.execute(path.read_text()).df()
    assert len(df.columns) > 0


def test_scratch_writes_csv_next_to_each_query(
    con: duckdb.DuckDBPyConnection, s: Settings, tmp_path: Path
) -> None:
    folder = tmp_path / "scratch"
    folder.mkdir(parents=True)
    (folder / "one.sql").write_text("SELECT 1 AS a")
    (folder / "two.sql").write_text("SELECT status, count(*) AS n FROM complaints GROUP BY 1")
    local = replace(s, sql_dir=tmp_path)
    assert set(scratch.run(con, local)) == {folder / "one.csv", folder / "two.csv"}
    assert (folder / "one.csv").read_text() == "a\n1\n"
    assert set(scratch.run(con, local, ["one"])) == {folder / "one.csv"}


def test_data_clock_variable_is_set(con: duckdb.DuckDBPyConnection) -> None:
    assert str(duck.one(con, "SELECT getvariable('data_clock')")[0]) == "2026-06-18"


def test_figures_run_overwrites_group_with_one_csv_per_query(
    con: duckdb.DuckDBPyConnection, s: Settings
) -> None:
    stale = s.figures_dir / "eda" / "removed_query.csv"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("old\n")
    out = figures.run(con, s, "eda")
    expected = {p.with_suffix(".csv").name for p in (SQL / "figures" / "eda").glob("*.sql")}
    assert {p.name for p in out.glob("*.csv")} == expected
    assert (out / "case_status.csv").read_text().count("\n") >= 2
