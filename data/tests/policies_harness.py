import shutil
from dataclasses import dataclass
from pathlib import Path

from clara_testing import FakeBedrockRuntime, FakeS3Vectors, local_embedder, local_index
from core.retrieval import NON_FILTERABLE

from bankdata.policies.build import Target
from bankdata.policies.store import LocalStore

SAMPLE = Path(__file__).resolve().parents[1] / "policies" / "sample"
SOURCES = SAMPLE / "sources"
DOMAIN = "docs.factoredai.sdfles.com"


@dataclass
class Corpus:
    sources: LocalStore
    policies: LocalStore
    documents: LocalStore
    bedrock: FakeBedrockRuntime
    vectors: FakeS3Vectors

    @property
    def target(self) -> Target:
        return Target(
            sources=self.sources,
            policies=self.policies,
            documents=self.documents,
            embedder=local_embedder(self.bedrock),
            index=local_index(self.vectors),
            docs_domain=DOMAIN,
        )

    def source(self, key: str) -> Path:
        return self.sources.root / key


def corpus(root: Path) -> Corpus:
    shutil.copytree(SOURCES, root / "sources")
    return Corpus(
        LocalStore(root / "sources"),
        LocalStore(root / "policies"),
        LocalStore(root / "documents"),
        FakeBedrockRuntime(),
        FakeS3Vectors(NON_FILTERABLE),
    )
