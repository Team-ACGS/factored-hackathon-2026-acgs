"""Write-only actions: block_card and create_complaint.

These are deliberately **not** registered in ``core.tools.registry.TOOLS``:
an LLM is never offered them as a tool to call. Only ``chatbot.turn``'s
``act`` node reaches them, and only after a customer has explicitly
confirmed a ``decide``-proposed action (see the ``ask``/``resolve_ask`` dance
in ``turn.py``).

Both functions take two different DynamoDB handles on purpose:

- ``context`` (a `ToolContext`) is used for *reads*; `ToolContext.dynamodb()`
  always assumes a read-only session (see `core.access.customer_session`,
  ``read_only=True``), so it is safe to reuse the same lookups the read
  tools use.
- ``write_dynamodb`` is the plain (non read-only) session the handler already
  holds for `core.messaging`. `role-customer` can write ``products`` and
  ``complaints`` (see infra/stacks/backend/access.tf), so no new IAM
  permission is needed.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from core.cases import Cases
from core.facts import Ledger
from core.facts.values import CaseCode, Label, Last4, Status
from core.tools.context import ToolContext
from core.tools.reads import Reader

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource


def block_card(
    context: ToolContext,
    write_dynamodb: "DynamoDBServiceResource",
    ledger: Ledger,
    card_ref: str,
) -> None:
    """Blocks one of the customer's own cards and records the result as a fact.

    Raises `core.tools.context.NotFound` if ``card_ref`` is not one of the
    customer's cards (the same error the read tools raise), so the caller can
    turn it into a graceful "that is no longer available" reply instead of a
    500.
    """
    [card] = Reader(context).cards_for(card_ref)
    table = write_dynamodb.Table(os.environ["TABLE_PRODUCTS"])
    table.update_item(
        Key={"customer_id": context.customer_id, "product_id": card_ref},
        UpdateExpression="SET product_status = :blocked",
        ConditionExpression="attribute_exists(product_id)",
        ExpressionAttributeValues={":blocked": "Blocked"},
    )
    ledger.add(
        "card",
        {
            "type": Label("card_type", card.type),
            "last4": Last4(card.last4),
            "status": Status("card", "Blocked"),
        },
    )


def create_complaint(
    context: ToolContext,
    write_dynamodb: "DynamoDBServiceResource",
    ledger: Ledger,
    product_id: str,
    transaction_id: str,
) -> None:
    """Opens a complaint for one transaction, idempotently.

    The complaint id is deterministic (derived from ``transaction_id``), the
    same convention the rest of the project uses for conditional writes
    ("every write uses a deterministic id and a condition on the table
    itself", docs/ARD.md). A retried turn can call this twice without
    opening a second complaint.
    """
    complaint_id = f"clara-{transaction_id}"
    item = {
        "customer_id": context.customer_id,
        "complaint_id": complaint_id,
        "area": "claims",
        "status": "Open",
        "creation_date": datetime.now(UTC).isoformat(),
        "transaction_id": transaction_id,
        "product_id": product_id,
    }
    Cases.from_dynamodb(write_dynamodb).write_if_absent(item)
    ledger.add(
        "case",
        {
            "case_id": CaseCode(complaint_id),
            "type": Label("case_type", "claim"),
            "stage": Status("stage", "opened"),
        },
    )