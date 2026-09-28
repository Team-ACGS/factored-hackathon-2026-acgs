from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table


def put_if_absent(table: "Table", item: Mapping[str, Any], key: str) -> bool:
    try:
        table.put_item(Item=dict(item), ConditionExpression=f"attribute_not_exists({key})")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
    return True
