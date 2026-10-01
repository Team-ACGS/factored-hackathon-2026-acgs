from typing import Annotated

import typer

from bankdata import duck, settings
from bankdata.analysis import figures as figures_module
from bankdata.analysis import scratch as scratch_module
from bankdata.pipeline import contracts
from bankdata.pipeline import ingest as ingest_module

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def ingest(
    tables: Annotated[list[str] | None, typer.Argument(help="Tables to build; all when omitted")] = None,
) -> None:
    s = settings.load()
    con = duck.connect(s)
    typer.echo(f"raw {s.raw} -> curated {s.curated}")
    for name, rows in ingest_module.ingest(con, s, tables or None).items():
        typer.echo(f"{name:28s} {rows:>12,}")


@app.command()
def check(
    tables: Annotated[list[str] | None, typer.Argument(help="Tables to check; all when omitted")] = None,
) -> None:
    s = settings.load()
    con = duck.connect(s)
    results = contracts.check(con, tables or None)
    for r in results:
        typer.echo(f"{'ok  ' if r.ok else 'FAIL'} {r.table:28s} {r.check:18s} {r.detail}")
    failed = [r for r in results if not r.ok]
    typer.echo(f"{len(results) - len(failed)} passed, {len(failed)} failed")
    raise typer.Exit(code=1 if failed else 0)


@app.command()
def figures(group: Annotated[str, typer.Argument(help="Figure group, a folder under sql/figures")]) -> None:
    s = settings.load()
    con = duck.connect(s)
    out = figures_module.run(con, s, group)
    typer.echo(f"wrote {out}")


@app.command()
def scratch(
    names: Annotated[
        list[str] | None, typer.Argument(help="Query names in sql/scratch; all when omitted")
    ] = None,
    rows: Annotated[int, typer.Option(help="Rows to print per query")] = 20,
) -> None:
    s = settings.load()
    con = duck.connect(s)
    for target, df in scratch_module.run(con, s, names or None).items():
        typer.echo(f"== {target.name} ({len(df):,} rows)")
        typer.echo(df.head(rows).to_string(index=False))
        typer.echo("")
