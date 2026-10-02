import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import boto3
import typer
from core.policies import COUNTRIES, pdf_key, policy_facts
from core.retrieval import VectorRetriever
from core.vectors import BUILD_CONFIG, Embedder, VectorIndex, bedrock_runtime, s3vectors
from dotenv import load_dotenv

from bankdata.policies.build import Target, build, read_manifest
from bankdata.policies.chunk import Chunking, chunk_document
from bankdata.policies.pdf import render_pdf
from bankdata.policies.sources import load
from bankdata.policies.spec import RENDERABLE, Limits
from bankdata.policies.store import LocalStore, S3Store
from bankdata.policies.tune import load_queries, tune
from bankdata.settings import DATA_DIR

build_app = typer.Typer(add_completion=False)
tune_app = typer.Typer(add_completion=False)

BUILD_SESSION_SECONDS = 4 * 3600

Profile = Annotated[str, typer.Option(help="AWS profile that assumes the policies-builder role")]
Folder = Annotated[
    Path, typer.Option(exists=True, file_okay=False, help="A local folder of sources, <doc_id>/<language>.md")
]


@dataclass(frozen=True)
class Config:
    region: str
    policies_bucket: str
    documents_bucket: str
    index_arn: str
    model_id: str
    docs_domain: str
    builder_role_arn: str | None

    @classmethod
    def load(cls) -> "Config":
        load_dotenv(DATA_DIR / ".env")
        return cls(
            region=os.environ.get("AWS_REGION", "us-east-1"),
            policies_bucket=os.environ["POLICIES_BUCKET"],
            documents_bucket=os.environ["DOCUMENTS_BUCKET"],
            index_arn=os.environ["POLICY_INDEX_ARN"],
            model_id=os.environ.get("POLICY_EMBEDDING_MODEL_ID", "cohere.embed-v4:0"),
            docs_domain=os.environ.get("POLICY_DOCS_DOMAIN", "docs.factoredai.sdfles.com"),
            builder_role_arn=os.environ.get("POLICIES_BUILDER_ROLE_ARN") or None,
        )

    def clients(self, profile: str) -> tuple[boto3.Session, Embedder, VectorIndex]:
        session = boto3.Session(profile_name=profile, region_name=self.region)
        if self.builder_role_arn:
            credentials = session.client("sts").assume_role(
                RoleArn=self.builder_role_arn,
                RoleSessionName="build-policies",
                DurationSeconds=BUILD_SESSION_SECONDS,
            )["Credentials"]
            session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=self.region,
            )
        embedder = Embedder(bedrock_runtime(BUILD_CONFIG, session), self.model_id)
        return session, embedder, VectorIndex(s3vectors(BUILD_CONFIG, session), self.index_arn)


@build_app.command("publish")
def publish(
    sources: Annotated[
        Path | None, typer.Option(help="A local folder of sources instead of the policies bucket")
    ] = None,
    prune: Annotated[
        bool, typer.Option(help="With --sources, remove the published documents missing from the folder")
    ] = False,
    profile: Profile = "personal",
) -> None:
    config = Config.load()
    session, embedder, index = config.clients(profile)
    s3 = session.client("s3")
    policies = S3Store(s3, config.policies_bucket)
    target = Target(
        sources=LocalStore(sources) if sources else policies,
        policies=policies,
        documents=S3Store(s3, config.documents_bucket),
        embedder=embedder,
        index=index,
        docs_domain=config.docs_domain,
    )
    report = build(target, prune=prune or sources is None)
    for problem in report.problems:
        typer.echo(str(problem), err=True)
    typer.echo(
        f"built {len(report.built)}, skipped {len(report.skipped)}, removed {len(report.removed)}, "
        f"failed {len({problem.file for problem in report.problems})}, "
        f"existing PDFs kept {len(report.pdfs_kept)}"
    )
    typer.echo(
        f"embedded {report.embedded}, vectors written {report.written}, deleted {report.deleted}, "
        f"duplicates {report.duplicates} of {report.candidates} ({report.duplicate_ratio:.1%})"
    )
    for doc_id, count in sorted(report.chunks_per_document.items()):
        typer.echo(f"{doc_id:48s} {count:>5} chunks")
    typer.echo(f"corpus {report.corpus_hash}")
    raise typer.Exit(code=1 if report.problems else 0)


@build_app.command("validate")
def validate_sources(sources: Folder) -> None:
    loaded = load(LocalStore(sources), policy_facts(), Limits(), Chunking())
    for problem in loaded.problems:
        typer.echo(str(problem), err=True)
    files = len({problem.file for problem in loaded.problems})
    typer.echo(f"{len(loaded.editions)} editions valid, {files} files with problems")
    raise typer.Exit(code=1 if loaded.problems else 0)


@build_app.command("render")
def render_sources(
    sources: Folder,
    out: Annotated[Path, typer.Option(file_okay=False, help="Where to write <country>/<edition>.pdf")],
    country: Annotated[str | None, typer.Option(help="Render only this country's editions")] = None,
) -> None:
    if country is not None and country not in COUNTRIES:
        raise typer.BadParameter(f"one of {', '.join(COUNTRIES)}", param_hint="--country")
    loaded = load(LocalStore(sources), policy_facts(), Limits(), Chunking(), RENDERABLE)
    for problem in loaded.problems:
        typer.echo(str(problem), err=True)
    for document in sorted(loaded.editions, key=lambda item: item.doc_id):
        if country is not None and document.country != country:
            continue
        pdf = render_pdf(document, chunk_document(document))
        key = pdf_key(document.country, document.doc_id, document.version, document.facts.version)
        path = out / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf.data)
        typer.echo(f"{key:56s} {pdf.page_count - 1:>3} pages")
    raise typer.Exit(code=1 if loaded.problems else 0)


@tune_app.command()
def tune_policies(
    queries: Annotated[Path, typer.Option(help="Labeled queries, TOML")],
    out: Annotated[Path, typer.Option(help="Where to write the tuning result")] = DATA_DIR
    / "policies/tuning.json",
    profile: Profile = "personal",
) -> None:
    config = Config.load()
    session, embedder, index = config.clients(profile)
    manifest = read_manifest(S3Store(session.client("s3"), config.policies_bucket))
    result = tune(
        VectorRetriever(embedder, index), load_queries(queries), manifest["corpus_hash"], config.model_id
    )
    out.write_text(result.to_json(), encoding="utf-8")
    typer.echo(result.to_json())
