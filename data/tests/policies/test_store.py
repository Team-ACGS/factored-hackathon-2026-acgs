from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from botocore.exceptions import ClientError

from bankdata.policies.store import LocalStore, S3Store

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class FakeS3:
    def __init__(self, code: str | None = None) -> None:
        self.code = code
        self.puts: list[dict[str, Any]] = []

    def put_object(self, **request: Any) -> dict[str, Any]:
        self.puts.append(request)
        if self.code:
            raise ClientError({"Error": {"Code": self.code, "Message": "no"}}, "PutObject")
        return {}


def store(client: FakeS3) -> S3Store:
    return S3Store(cast("S3Client", client), "documents")


def test_s3_create_writes_only_if_the_key_is_absent() -> None:
    client = FakeS3()

    assert store(client).create("PE/a.pdf", b"pdf", "application/pdf", "immutable")

    assert client.puts[0]["IfNoneMatch"] == "*"
    assert client.puts[0]["CacheControl"] == "immutable"


@pytest.mark.parametrize("code", ["PreconditionFailed", "ConditionalRequestConflict"])
def test_s3_create_keeps_an_existing_key(code: str) -> None:
    assert not store(FakeS3(code)).create("PE/a.pdf", b"pdf", "application/pdf")


def test_s3_create_raises_any_other_error() -> None:
    with pytest.raises(ClientError):
        store(FakeS3("AccessDenied")).create("PE/a.pdf", b"pdf", "application/pdf")


def test_local_create_keeps_an_existing_file(tmp_path: Path) -> None:
    local = LocalStore(tmp_path)

    assert local.create("PE/a.pdf", b"first", "application/pdf")
    assert not local.create("PE/a.pdf", b"second", "application/pdf")

    assert local.read("PE/a.pdf") == b"first"
