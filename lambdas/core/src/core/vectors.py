import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import batched
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
    from mypy_boto3_s3vectors import S3VectorsClient

EMBEDDING_DIMENSION = 1024
EMBED_BATCH = 96
WRITE_BATCH = 500
LIST_PAGE = 1000

SEARCH_DOCUMENT = "search_document"
SEARCH_QUERY = "search_query"

TURN_CONFIG = Config(connect_timeout=1, read_timeout=3, retries={"total_max_attempts": 1, "mode": "standard"})
BUILD_CONFIG = Config(
    connect_timeout=5, read_timeout=60, retries={"total_max_attempts": 5, "mode": "adaptive"}
)

Metadata = dict[str, Any]


def bedrock_runtime(
    config: Config = TURN_CONFIG, session: boto3.Session | None = None
) -> "BedrockRuntimeClient":
    return (session or boto3.Session()).client("bedrock-runtime", config=config)


def s3vectors(config: Config = TURN_CONFIG, session: boto3.Session | None = None) -> "S3VectorsClient":
    return (session or boto3.Session()).client("s3vectors", config=config)


@dataclass(frozen=True)
class Embedder:
    client: "BedrockRuntimeClient"
    model_id: str

    def embed(self, texts: Sequence[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch in batched(texts, EMBED_BATCH):
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({"texts": list(batch), "input_type": input_type, "truncate": "NONE"}),
            )
            embeddings = json.loads(response["body"].read())["embeddings"]
            if len(embeddings) != len(batch):
                raise ValueError(f"expected {len(batch)} embeddings, got {len(embeddings)}")
            vectors.extend([float(x) for x in embedding] for embedding in embeddings)
        return vectors


@dataclass(frozen=True)
class Vector:
    key: str
    data: list[float]
    metadata: Metadata


@dataclass(frozen=True)
class Match:
    key: str
    distance: float
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class VectorIndex:
    client: "S3VectorsClient"
    index_arn: str

    def query(self, vector: Sequence[float], k: int, where: Mapping[str, Any]) -> list[Match]:
        response = self.client.query_vectors(
            indexArn=self.index_arn,
            topK=k,
            queryVector={"float32": list(vector)},
            filter=dict(where),
            returnMetadata=True,
            returnDistance=True,
        )
        return [
            Match(item["key"], float(item.get("distance", 1.0)), item.get("metadata") or {})
            for item in response["vectors"]
        ]

    def put(self, vectors: Iterable[Vector]) -> int:
        written = 0
        for batch in batched(vectors, WRITE_BATCH):
            self.client.put_vectors(
                indexArn=self.index_arn,
                vectors=[
                    {"key": vector.key, "data": {"float32": vector.data}, "metadata": vector.metadata}
                    for vector in batch
                ],
            )
            written += len(batch)
        return written

    def delete(self, keys: Iterable[str]) -> int:
        deleted = 0
        for batch in batched(keys, WRITE_BATCH):
            self.client.delete_vectors(indexArn=self.index_arn, keys=list(batch))
            deleted += len(batch)
        return deleted

    def keys(self) -> list[str]:
        found: list[str] = []
        token: str | None = None
        while True:
            page = (
                self.client.list_vectors(indexArn=self.index_arn, maxResults=LIST_PAGE, nextToken=token)
                if token
                else self.client.list_vectors(indexArn=self.index_arn, maxResults=LIST_PAGE)
            )
            found.extend(item["key"] for item in page["vectors"])
            token = page.get("nextToken")
            if not token:
                return found


def where_equal(conditions: Mapping[str, str | int]) -> dict[str, Any]:
    clauses = [{name: {"$eq": value}} for name, value in sorted(conditions.items())]
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}
