import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from core.observability import tracer


class PublishRejected(Exception):
    pass


class Publisher:
    def __init__(
        self, url: str, region: str, session: boto3.Session, http: urllib3.PoolManager, timeout: float
    ) -> None:
        self._url = url
        self._region = region
        self._session = session
        self._http = http
        self._timeout = timeout

    @classmethod
    def from_env(cls, timeout: float, retries: bool | None = None) -> "Publisher":
        return cls(
            os.environ["REALTIME_HTTP_URL"],
            os.environ["AWS_REGION"],
            boto3.Session(),
            urllib3.PoolManager(retries=retries),
            timeout,
        )

    @tracer.capture_method(capture_response=False)
    def publish(self, channel: str, events: Sequence[Mapping[str, Any]]) -> None:
        credentials = self._session.get_credentials()
        if credentials is None:
            raise PublishRejected("no credentials to sign with")
        body = json.dumps({"channel": channel, "events": [json.dumps(event) for event in events]})
        request = AWSRequest(
            method="POST", url=self._url, data=body, headers={"Content-Type": "application/json"}
        )
        SigV4Auth(credentials, "appsync", self._region).add_auth(request)
        response = self._http.request(
            "POST",
            self._url,
            body=body,
            headers=dict(request.headers.items()),
            timeout=urllib3.Timeout(total=self._timeout),
        )
        if response.status != 200:
            raise PublishRejected(f"status {response.status}")
        failed = json.loads(response.data).get("failed")
        if failed:
            raise PublishRejected(json.dumps(failed))


def room_channel(customer_id: str, room_id: str) -> str:
    return f"/{os.environ['REALTIME_NAMESPACE']}/{customer_id}/{room_id}"
