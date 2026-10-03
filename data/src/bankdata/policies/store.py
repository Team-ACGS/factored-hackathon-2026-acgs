from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import PutObjectRequestTypeDef

EXISTS = ("PreconditionFailed", "ConditionalRequestConflict")


class Store(Protocol):
    def names(self) -> list[str]: ...

    def read(self, key: str) -> bytes | None: ...

    def write(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None: ...

    def create(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> bool: ...


@dataclass
class LocalStore:
    root: Path
    writes: list[str] = field(default_factory=list)

    def names(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_file()
        )

    def read(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.is_file() else None

    def write(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.writes.append(key)

    def create(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> bool:
        if (self.root / key).exists():
            return False
        self.write(key, data, content_type, cache_control)
        return True


@dataclass(frozen=True)
class S3Store:
    client: "S3Client"
    bucket: str

    def names(self) -> list[str]:
        found: list[str] = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket):
            found.extend(item["Key"] for item in page.get("Contents", []))
        return sorted(found)

    def read(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise

    def write(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None:
        self.client.put_object(**self._request(key, data, content_type, cache_control))

    def create(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> bool:
        try:
            request = self._request(key, data, content_type, cache_control)
            request["IfNoneMatch"] = "*"
            self.client.put_object(**request)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in EXISTS:
                return False
            raise
        return True

    def _request(
        self, key: str, data: bytes, content_type: str, cache_control: str | None
    ) -> "PutObjectRequestTypeDef":
        request: PutObjectRequestTypeDef = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if cache_control is not None:
            request["CacheControl"] = cache_control
        return request
