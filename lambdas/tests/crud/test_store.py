from typing import Any

import pytest

from crud.store import Store
from harness import Aws

ITEMS = [{"customer_id": "c1", "transaction_key": f"p#{index:03d}", "amount": index} for index in range(60)]


def test_unprocessed_items_are_retried_until_every_transaction_is_written(
    aws: Aws, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = aws.transactions.meta.client
    write = client.batch_write_item
    throttled = {"calls": 0}

    def throttling(**request: Any) -> Any:
        throttled["calls"] += 1
        requests = request["RequestItems"][aws.transactions.name]
        if throttled["calls"] <= 2:
            written = write(RequestItems={aws.transactions.name: requests[:5]})
            return {**written, "UnprocessedItems": {aws.transactions.name: requests[5:]}}
        return write(**request)

    monkeypatch.setattr(client, "batch_write_item", throttling)

    Store(aws.customers, aws.products, aws.transactions, aws.complaints).write_account([], ITEMS)

    assert throttled["calls"] > 3
    assert sorted(str(item["transaction_key"]) for item in aws.transactions.scan()["Items"]) == [
        item["transaction_key"] for item in ITEMS
    ]
