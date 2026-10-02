import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from core.policies import CountryFacts, chunk_id, edition, encode_figures, pdf_key, pdf_url, policy_facts
from core.retrieval import ChunkRecord
from core.vectors import SEARCH_DOCUMENT, Embedder, Vector, VectorIndex

from bankdata.policies.chunk import Chunk, Chunking, chunk_document, embedding_input
from bankdata.policies.dedupe import Candidate, dedupe
from bankdata.policies.document import Problem
from bankdata.policies.pdf import render_pdf
from bankdata.policies.render import RenderedDocument
from bankdata.policies.sources import load
from bankdata.policies.spec import Limits
from bankdata.policies.store import Store

BUILD_VERSION = 2
MANIFEST_KEY = "manifest.json"
FACTS_FILE = "lambdas/core/src/core/policy_facts.toml"
PDF_CACHE = "public, max-age=31536000, immutable"
SOURCES = "<sources>"

Entry = dict[str, Any]


@dataclass(frozen=True)
class Target:
    sources: Store
    policies: Store
    documents: Store
    embedder: Embedder
    index: VectorIndex
    docs_domain: str


@dataclass
class Report:
    problems: list[Problem] = field(default_factory=list)
    built: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    pdfs_kept: list[str] = field(default_factory=list)
    embedded: int = 0
    written: int = 0
    deleted: int = 0
    candidates: int = 0
    duplicates: int = 0
    chunks_per_document: dict[str, int] = field(default_factory=dict)
    corpus_hash: str = ""

    @property
    def duplicate_ratio(self) -> float:
        return self.duplicates / self.candidates if self.candidates else 0.0


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_manifest(store: Store) -> Entry:
    data = store.read(MANIFEST_KEY)
    return json.loads(data) if data else {}


def build(
    target: Target,
    facts: dict[str, CountryFacts] | None = None,
    limits: Limits | None = None,
    chunking: Chunking | None = None,
    prune: bool = True,
) -> Report:
    facts = facts or policy_facts()
    limits = limits or Limits()
    chunking = chunking or Chunking()
    report = Report()
    previous = read_manifest(target.policies)
    before: dict[str, Entry] = previous.get("documents", {})
    facts_state = _facts_state(facts, previous, report)
    stale_countries = {country for country, state in facts_state.items() if state.get("stale")}

    loaded = load(target.sources, facts, limits, chunking)
    report.problems.extend(loaded.problems)
    rendered: list[RenderedDocument] = []
    for document in loaded.editions:
        prior = before.get(document.doc_id)
        source_hash = loaded.source_hashes[document.key]
        problems: list[Problem] = []
        if document.country in stale_countries:
            problems = [Problem(document.key, 1, "facts_version", f"the {document.country} facts changed")]
        elif prior is not None:
            problems = _version_problems(document.key, document.version, source_hash, prior)
        if problems:
            report.problems.extend(problem for problem in problems if problem not in report.problems)
            continue
        rendered.append(document)

    rendered.sort(key=lambda item: item.doc_id)
    chunks = {document.doc_id: chunk_document(document) for document in rendered}
    candidates = [
        Candidate(_chunk_id(document, chunk), document.country, document.topic, chunk.text)
        for document in rendered
        for chunk in chunks[document.doc_id]
    ]
    dropped = dedupe(candidates)
    report.candidates, report.duplicates = len(candidates), len(dropped)

    entries: dict[str, Entry] = dict(before)
    for document in rendered:
        kept = [chunk for chunk in chunks[document.doc_id] if _chunk_id(document, chunk) not in dropped]
        report.chunks_per_document[document.doc_id] = len(kept)
        content_hash = digest(
            {
                "build": BUILD_VERSION,
                "chunking": chunking.params(),
                "model": target.embedder.model_id,
                "markdown": document.markdown(),
                "chunks": [[_chunk_id(document, chunk), chunk.start, chunk.end] for chunk in kept],
            }
        )
        prior = before.get(document.doc_id)
        if prior is not None and prior["content_hash"] == content_hash:
            report.skipped.append(document.doc_id)
            continue
        entry = _publish(target, document, kept, content_hash, loaded.source_hashes[document.key], report)
        stale = sorted(set(prior["vectors"]) - set(entry["vectors"])) if prior else []
        if stale:
            report.deleted += target.index.delete(stale)
        entries[document.doc_id] = entry
        report.built.append(document.doc_id)
        _write_manifest(target, chunking, facts_state, entries, report)

    if prune and before and not loaded.present:
        report.problems.append(Problem(SOURCES, 1, "no_sources", "no source found; nothing is removed"))
        prune = False
    for doc_id in sorted(set(before) - loaded.present) if prune else []:
        report.deleted += target.index.delete(before[doc_id]["vectors"])
        report.removed.append(doc_id)
        del entries[doc_id]
    _write_manifest(target, chunking, facts_state, entries, report)
    return report


def _write_manifest(
    target: Target,
    chunking: Chunking,
    facts_state: dict[str, Entry],
    entries: dict[str, Entry],
    report: Report,
) -> None:
    documents = dict(sorted(entries.items()))
    report.corpus_hash = digest({doc_id: entry["content_hash"] for doc_id, entry in documents.items()})
    manifest = {
        "build": BUILD_VERSION,
        "embedding_model": target.embedder.model_id,
        "chunking": chunking.params(),
        "facts": {
            country: {"version": state["version"], "hash": state["hash"]}
            for country, state in facts_state.items()
        },
        "documents": documents,
        "corpus_hash": report.corpus_hash,
    }
    data = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    if data != target.policies.read(MANIFEST_KEY):
        target.policies.write(MANIFEST_KEY, data, "application/json")


def _facts_state(facts: dict[str, CountryFacts], previous: Entry, report: Report) -> dict[str, Entry]:
    state: dict[str, Entry] = {}
    for country, country_facts in sorted(facts.items()):
        current = {"version": country_facts.version, "hash": digest(encode_figures(country_facts.specs))}
        prior = previous.get("facts", {}).get(country)
        if prior and prior["version"] == current["version"] and prior["hash"] != current["hash"]:
            report.problems.append(
                Problem(FACTS_FILE, 1, "facts_version", f"{country} values changed; raise its version")
            )
            state[country] = {**prior, "stale": True}
        elif prior and current["version"] < prior["version"]:
            report.problems.append(Problem(FACTS_FILE, 1, "facts_version", f"{country} version went back"))
            state[country] = {**prior, "stale": True}
        else:
            state[country] = current
    return state


def _version_problems(key: str, version: int, source_hash: str, prior: Entry) -> list[Problem]:
    if version < prior["version"]:
        return [Problem(key, 1, "version", f"version went back from {prior['version']}")]
    if version == prior["version"] and source_hash != prior["source_hash"]:
        return [Problem(key, 1, "version", "the text changed; raise version")]
    return []


def _chunk_id(document: RenderedDocument, chunk: Chunk) -> str:
    return chunk_id(document.doc_id, document.version, document.facts.version, chunk.section, chunk.number)


def _publish(
    target: Target,
    document: RenderedDocument,
    chunks: list[Chunk],
    content_hash: str,
    source_hash: str,
    report: Report,
) -> Entry:
    key = pdf_key(document.country, document.doc_id, document.version, document.facts.version)
    url = pdf_url(target.docs_domain, key)
    pdf = render_pdf(document, chunks)
    sections = {section.number: section for section in document.sections}
    records = [
        ChunkRecord(
            chunk_id=_chunk_id(document, chunk),
            country=document.country,
            language=document.language,
            group=document.group,
            topic=document.topic,
            doc_type=document.doc_type,
            doc_id=document.doc_id,
            version=document.version,
            facts_version=document.facts.version,
            effective_date=document.effective_date,
            section=sections[chunk.section].heading,
            title=document.title,
            text=chunk.text,
            figures=document.figures(chunk.start, chunk.end, sections[chunk.section]),
            page_start=pdf.pages[(chunk.section, chunk.number)][0],
            page_end=pdf.pages[(chunk.section, chunk.number)][1],
            url=url,
            content_hash=content_hash,
        )
        for chunk in chunks
    ]
    if not target.documents.create(key, pdf.data, "application/pdf", PDF_CACHE):
        report.pdfs_kept.append(key)
    edition_name = edition(document.doc_id, document.version, document.facts.version)
    target.policies.write(
        f"rendered/{document.country}/{edition_name}.md",
        document.markdown().encode(),
        "text/markdown; charset=utf-8",
    )
    embeddings = target.embedder.embed([embedding_text(record) for record in records], SEARCH_DOCUMENT)
    report.embedded += len(embeddings)
    report.written += target.index.put(
        Vector(record.chunk_id, embedding, record.metadata())
        for record, embedding in zip(records, embeddings, strict=True)
    )
    return {
        "country": document.country,
        "topic": document.topic,
        "group": document.group,
        "doc_type": document.doc_type,
        "source_key": document.key,
        "source_hash": source_hash,
        "version": document.version,
        "facts_version": document.facts.version,
        "effective_date": document.effective_date.isoformat(),
        "content_hash": content_hash,
        "pdf_key": key,
        "pdf_url": url,
        "vectors": [record.chunk_id for record in records],
        "pages": {record.chunk_id: [record.page_start, record.page_end] for record in records},
    }


def embedding_text(record: ChunkRecord) -> str:
    return embedding_input(record.title, record.section, record.text)
