from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class Store(Protocol):
    def names(self) -> list[str]: ...

    def read(self, key: str) -> bytes | None: ...

    def write(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None: ...


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
        if cache_control is None:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        else:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, CacheControl=cache_control
            )
