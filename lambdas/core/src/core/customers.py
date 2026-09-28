import os

import boto3

from core.conditional import put_if_absent


def create_customer(session: boto3.Session, customer_id: str, email: str, created_at: str) -> bool:
    table = session.resource("dynamodb").Table(os.environ["TABLE_CUSTOMERS"])
    return put_if_absent(
        table, {"customer_id": customer_id, "email": email, "created_at": created_at}, "customer_id"
    )
