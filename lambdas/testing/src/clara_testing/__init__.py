import hashlib
import io
import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from botocore.exceptions import ClientError

from core.vectors import EMBED_BATCH, EMBEDDING_DIMENSION, LIST_PAGE, WRITE_BATCH, Embedder, VectorIndex

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient
    from mypy_boto3_s3vectors import S3VectorsClient

INDEX_ARN = "arn:aws:s3vectors:us-east-1:000000000000:bucket/clara-test-policies/index/policies"
MODEL_ID = "cohere.embed-v4:0"
DEFAULT_V4_DIMENSION = 1536

MAX_EMBED_CHARS = 2048
FILTERABLE_BYTES = 2048
METADATA_BYTES = 40 * 1024
NON_FILTERABLE_KEYS = 10
WORD = re.compile(r"[a-z0-9]+")


def local_embedding(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    folded = "".join(
        char for char in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(char)
    )
    vector = [0.0] * dimension
    for word in WORD.findall(folded):
        if len(word) < 4:
            continue
        for feature in {word, word[:5]}:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            slot = int.from_bytes(digest[:4], "big") % dimension
            vector[slot] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _error(code: str, operation: str, message: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, operation)


@dataclass
class FakeBedrockRuntime:
    failures: int = 0
    short: bool = False
    fail_on_call: int | None = None
    calls: list[Mapping[str, Any]] = field(default_factory=list)

    def invoke_model(self, **request: Any) -> dict[str, Any]:
        if self.failures:
            self.failures -= 1
            raise _error("ThrottlingException", "InvokeModel", "slow down")
        body = json.loads(request["body"])
        self.calls.append(body)
        if self.fail_on_call == len(self.calls):
            raise _error("ThrottlingException", "InvokeModel", "slow down")
        texts = body["texts"]
        if not 1 <= len(texts) <= EMBED_BATCH or body.get("truncate") != "NONE":
            raise _error("ValidationException", "InvokeModel", "bad request")
        if body["input_type"] not in ("search_document", "search_query"):
            raise _error("ValidationException", "InvokeModel", "bad input_type")
        if any(len(text) > MAX_EMBED_CHARS for text in texts):
            raise _error("ValidationException", "InvokeModel", "text too long")
        v4 = str(request["modelId"]).startswith("cohere.embed-v4")
        if "output_dimension" in body and not v4:
            raise _error("ValidationException", "InvokeModel", "extraneous key [output_dimension]")
        dimension = int(body.get("output_dimension", DEFAULT_V4_DIMENSION)) if v4 else EMBEDDING_DIMENSION
        embeddings = [local_embedding(text, dimension) for text in texts[: -1 if self.short else None]]
        typed = v4 or "embedding_types" in body
        payload = {
            "id": "local",
            "response_type": "embeddings_by_type" if typed else "embeddings_floats",
            "texts": texts,
            "embeddings": {"float": embeddings} if typed else embeddings,
        }
        return {"body": io.BytesIO(json.dumps(payload).encode()), "contentType": "application/json"}


@dataclass
class FakeS3Vectors:
    non_filterable: frozenset[str]
    vectors: dict[str, tuple[list[float], dict[str, Any]]] = field(default_factory=dict)
    failures: int = 0
    writes: int = 0
    deletes: int = 0

    def __post_init__(self) -> None:
        if len(self.non_filterable) > NON_FILTERABLE_KEYS:
            raise ValueError("too many non-filterable metadata keys")

    def put_vectors(self, *, indexArn: str, vectors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        self._maybe_fail("PutVectors")
        if not 1 <= len(vectors) <= WRITE_BATCH:
            raise _error("ValidationException", "PutVectors", "batch size")
        for vector in vectors:
            data = list(vector["data"]["float32"])
            metadata = dict(vector["metadata"])
            if len(data) != EMBEDDING_DIMENSION:
                raise _error("ValidationException", "PutVectors", "dimension")
            self._check_metadata(metadata)
            self.vectors[vector["key"]] = (data, metadata)
        self.writes += len(vectors)
        return {}

    def delete_vectors(self, *, indexArn: str, keys: Sequence[str]) -> dict[str, Any]:
        self._maybe_fail("DeleteVectors")
        if not 1 <= len(keys) <= WRITE_BATCH:
            raise _error("ValidationException", "DeleteVectors", "batch size")
        for key in keys:
            self.vectors.pop(key, None)
        self.deletes += len(keys)
        return {}

    def list_vectors(
        self, *, indexArn: str, maxResults: int = LIST_PAGE, nextToken: str = "0"
    ) -> dict[str, Any]:
        start = int(nextToken)
        keys = sorted(self.vectors)
        page = keys[start : start + maxResults]
        response: dict[str, Any] = {"vectors": [{"key": key} for key in page]}
        if start + maxResults < len(keys):
            response["nextToken"] = str(start + maxResults)
        return response

    def query_vectors(
        self,
        *,
        indexArn: str,
        topK: int,
        queryVector: Mapping[str, list[float]],
        filter: Mapping[str, Any] | None = None,
        returnMetadata: bool = False,
        returnDistance: bool = False,
    ) -> dict[str, Any]:
        self._maybe_fail("QueryVectors")
        query = queryVector["float32"]
        scored = sorted(
            (1.0 - sum(a * b for a, b in zip(query, data, strict=True)), key, metadata)
            for key, (data, metadata) in self.vectors.items()
            if filter is None or _matches(filter, metadata)
        )
        hits: list[dict[str, Any]] = []
        for distance, key, metadata in scored[:topK]:
            hit: dict[str, Any] = {"key": key}
            if returnDistance:
                hit["distance"] = distance
            if returnMetadata:
                hit["metadata"] = metadata
            hits.append(hit)
        return {"vectors": hits, "distanceMetric": "cosine"}

    def _maybe_fail(self, operation: str) -> None:
        if self.failures:
            self.failures -= 1
            raise _error("ServiceUnavailableException", operation, "try again")

    def _check_metadata(self, metadata: Mapping[str, Any]) -> None:
        for value in metadata.values():
            if not isinstance(value, str | int | float | bool | list):
                raise _error("ValidationException", "PutVectors", "metadata value type")
        filterable = {key: value for key, value in metadata.items() if key not in self.non_filterable}
        if _size(filterable) > FILTERABLE_BYTES or _size(metadata) > METADATA_BYTES:
            raise _error("ValidationException", "PutVectors", "metadata too large")


def _size(metadata: Mapping[str, Any]) -> int:
    return len(json.dumps(metadata, ensure_ascii=False).encode())


def _matches(where: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    if "$and" in where:
        return all(_matches(clause, metadata) for clause in where["$and"])
    return all(
        metadata.get(name) == (condition["$eq"] if isinstance(condition, dict) else condition)
        for name, condition in where.items()
    )


def local_embedder(client: FakeBedrockRuntime) -> Embedder:
    return Embedder(cast("BedrockRuntimeClient", client), MODEL_ID)


def local_index(client: FakeS3Vectors) -> VectorIndex:
    return VectorIndex(cast("S3VectorsClient", client), INDEX_ARN)
