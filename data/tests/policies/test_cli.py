import shutil
from pathlib import Path

import boto3
import pymupdf
import pytest
from typer.testing import CliRunner

from bankdata.policies.cli import build_app
from policies_harness import SOURCES

RUNNER = CliRunner()
DEADLINES = "dispute-deadlines/es.md"


@pytest.fixture(autouse=True)
def no_aws(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("validate and render never touch AWS")

    for name in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "none"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "none"))
    monkeypatch.setattr(boto3, "Session", refuse)
    monkeypatch.setattr(boto3, "client", refuse)


@pytest.fixture
def sources(tmp_path: Path) -> Path:
    return Path(shutil.copytree(SOURCES, tmp_path / "sources"))


def change(sources: Path, key: str, old: str, new: str) -> int:
    path = sources / key
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(old, new), encoding="utf-8")
    return next(number for number, line in enumerate(text.splitlines(), 1) if old in line)


def test_validate_passes_the_sample(sources: Path) -> None:
    result = RUNNER.invoke(build_app, ["validate", "--sources", str(sources)])

    assert result.exit_code == 0, result.output
    assert result.stdout == "12 editions valid, 0 files with problems\n"


def test_validate_prints_every_problem_with_file_and_line_and_fails(sources: Path) -> None:
    at = change(sources, DEADLINES, "que no hizo la compra", "que no hubo fraude")

    result = RUNNER.invoke(build_app, ["validate", "--sources", str(sources)])

    assert result.exit_code == 1
    assert result.stderr.startswith(f"{DEADLINES}:{at}: forbidden_word: ")
    assert result.stdout == "8 editions valid, 1 files with problems\n"


def test_render_writes_each_edition_as_a_pdf_and_prints_its_pages(sources: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"

    result = RUNNER.invoke(
        build_app, ["render", "--sources", str(sources), "--out", str(out), "--country", "US"]
    )

    assert result.exit_code == 0, result.output
    written = sorted(path.relative_to(out).as_posix() for path in out.rglob("*.pdf"))
    assert written == ["US/us-dispute-deadlines-v1-f2.pdf", "US/us-unrecognized-charges-faq-v1-f2.pdf"]
    for line, key in zip(result.stdout.splitlines(), written, strict=True):
        with pymupdf.open(out / key) as pdf:
            pages = pdf.page_count - 1
        assert line.split() == [key, str(pages), "pages"]
        assert 2 <= pages <= 3


def test_render_renders_a_draft_that_fails_only_word_rules_or_parity(sources: Path, tmp_path: Path) -> None:
    at = change(sources, DEADLINES, "Usted puede reportar", "Tú puedes reportar")
    (sources / "dispute-deadlines" / "en-US.md").unlink()
    out = tmp_path / "out"

    result = RUNNER.invoke(
        build_app, ["render", "--sources", str(sources), "--out", str(out), "--country", "MX"]
    )

    assert result.exit_code == 1
    assert f"{DEADLINES}:{at}: register: " in result.stderr
    assert f"{DEADLINES}:1: parity: document dispute-deadlines has no en-US file" in result.stderr
    assert (out / "MX" / "mx-dispute-deadlines-v1-f2.pdf").is_file()


def test_render_skips_a_draft_with_a_raw_figure(sources: Path, tmp_path: Path) -> None:
    at = change(sources, DEADLINES, "nunca supera el máximo legal", "nunca supera los 45 días")
    out = tmp_path / "out"

    result = RUNNER.invoke(
        build_app, ["render", "--sources", str(sources), "--out", str(out), "--country", "MX"]
    )

    assert result.exit_code == 1
    assert result.stderr == f"{DEADLINES}:{at}: raw_figure: '45' must be a placeholder\n"
    assert sorted(path.name for path in out.rglob("*.pdf")) == ["mx-unrecognized-charges-faq-v1-f2.pdf"]
