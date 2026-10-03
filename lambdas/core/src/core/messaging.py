import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from core.conditional import put_if_absent
from core.ids import InvalidId, format_instant, parse_uuid7, successor, uuid7_time

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

SenderType = Literal["customer", "assistant", "agent"]

MAX_CLOCK_SKEW = timedelta(minutes=2)
MAX_TEXT_LENGTH = 2000
TURN_MARK_TTL = timedelta(minutes=5)

Json = dict[str, Any]


class InvalidMessage(ValueError):
    pass


class TurnInProgress(Exception):
    pass


@dataclass(frozen=True)
class Message:
    customer_id: str
    room_id: str
    message_id: str
    sender_type: SenderType
    text: str
    sent_at: str
    created_at: str
    origin_trace_id: str | None = None
    parts: tuple[Json, ...] = ()
    facts: tuple[Json, ...] = ()
    draft: tuple[Json, ...] = ()
    source: str | None = None

    @property
    def message_key(self) -> str:
        return f"{self.room_id}#{self.sent_at}#{self.message_id}"

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "customer_id": self.customer_id,
            "message_key": self.message_key,
            "room_id": self.room_id,
            "message_id": self.message_id,
            "sender_type": self.sender_type,
            "text": self.text,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }
        if self.origin_trace_id:
            item["origin_trace_id"] = self.origin_trace_id
        for name in ("parts", "facts", "draft"):
            if getattr(self, name):
                item[name] = list(getattr(self, name))
        if self.source:
            item["source"] = self.source
        return item

    @classmethod
    def from_item(cls, item: Mapping[str, Any]) -> "Message":
        sender_type = item["sender_type"]
        if sender_type not in get_args(SenderType):
            raise InvalidMessage(f"unknown sender_type {sender_type}")
        return cls(
            customer_id=str(item["customer_id"]),
            room_id=str(item["room_id"]),
            message_id=str(item["message_id"]),
            sender_type=cast(SenderType, sender_type),
            text=str(item["text"]),
            sent_at=str(item["sent_at"]),
            created_at=str(item["created_at"]),
            origin_trace_id=str(item["origin_trace_id"]) if item.get("origin_trace_id") else None,
            parts=tuple(plain(item.get("parts") or [])),
            facts=tuple(plain(item.get("facts") or [])),
            draft=tuple(plain(item.get("draft") or [])),
            source=str(item["source"]) if item.get("source") else None,
        )

    def public(self) -> dict[str, Any]:
        public: dict[str, Any] = {
            "room_id": self.room_id,
            "message_id": self.message_id,
            "sender_type": self.sender_type,
            "text": self.text,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }
        if self.parts:
            public["parts"] = list(self.parts)
        return public


@dataclass(frozen=True)
class Room:
    customer_id: str
    room_id: str
    created_at: str
    delegated_to_human: bool

    @classmethod
    def from_item(cls, item: Mapping[str, Any]) -> "Room":
        return cls(
            customer_id=str(item["customer_id"]),
            room_id=str(item["room_id"]),
            created_at=str(item["created_at"]),
            delegated_to_human=bool(item.get("delegated_to_human", False)),
        )

    def public(self) -> dict[str, str]:
        return {"room_id": self.room_id, "created_at": self.created_at}


def customer_message(
    customer_id: str,
    room_id: str,
    message_id: str,
    text: str,
    now: datetime,
    origin_trace_id: str | None = None,
) -> Message:
    try:
        parse_uuid7(room_id)
        sent_at = uuid7_time(parse_uuid7(message_id))
    except InvalidId as error:
        raise InvalidMessage(str(error)) from error
    if abs(now - sent_at) > MAX_CLOCK_SKEW:
        raise InvalidMessage("message_id is too far from server time")
    body = text.strip()
    if not body:
        raise InvalidMessage("text is empty")
    if len(body) > MAX_TEXT_LENGTH:
        raise InvalidMessage(f"text is longer than {MAX_TEXT_LENGTH} characters")
    return Message(
        customer_id=customer_id,
        room_id=room_id,
        message_id=message_id,
        sender_type="customer",
        text=body,
        sent_at=format_instant(sent_at),
        created_at=format_instant(now),
        origin_trace_id=origin_trace_id,
    )


def plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [plain(entry) for entry in value]
    if isinstance(value, dict):
        return {key: plain(entry) for key, entry in value.items()}
    return value


def reply_key(message: Message) -> str:
    return f"{message.room_id}#{message.sent_at}#{successor(uuid.UUID(message.message_id))}"


def reply_to(
    message: Message,
    sender_type: SenderType,
    text: str,
    now: datetime,
    parts: tuple[Json, ...] = (),
    facts: tuple[Json, ...] = (),
    draft: tuple[Json, ...] = (),
    source: str | None = None,
) -> Message:
    return Message(
        customer_id=message.customer_id,
        room_id=message.room_id,
        message_id=str(successor(uuid.UUID(message.message_id))),
        sender_type=sender_type,
        text=text,
        sent_at=message.sent_at,
        created_at=format_instant(now),
        origin_trace_id=message.origin_trace_id,
        parts=parts,
        facts=facts,
        draft=draft,
        source=source,
    )


class Messaging:
    def __init__(self, rooms: "Table", messages: "Table") -> None:
        self._rooms = rooms
        self._messages = messages

    @classmethod
    def from_dynamodb(cls, dynamodb: "DynamoDBServiceResource") -> "Messaging":
        return cls(dynamodb.Table(os.environ["TABLE_ROOMS"]), dynamodb.Table(os.environ["TABLE_MESSAGES"]))

    def send(self, message: Message) -> tuple[Message, bool]:
        self._open_room(message.customer_id, message.room_id, message.created_at)
        return self.write(message)

    def write(self, message: Message) -> tuple[Message, bool]:
        if put_if_absent(self._messages, message.to_item(), "message_key"):
            return message, True
        return self._stored(message), False

    def room(self, customer_id: str, room_id: str) -> Room | None:
        item = self._rooms.get_item(
            Key={"customer_id": customer_id, "room_id": room_id}, ConsistentRead=True
        ).get("Item")
        return Room.from_item(item) if item else None

    def latest_room(self, customer_id: str) -> Room | None:
        items = self._rooms.query(
            KeyConditionExpression=Key("customer_id").eq(customer_id), ScanIndexForward=False, Limit=1
        )["Items"]
        return Room.from_item(items[0]) if items else None

    def history(self, customer_id: str, room_id: str) -> list[Message]:
        condition = Key("customer_id").eq(customer_id) & Key("message_key").begins_with(f"{room_id}#")
        messages: list[Message] = []
        page = self._messages.query(KeyConditionExpression=condition, ConsistentRead=True)
        messages.extend(Message.from_item(item) for item in page["Items"])
        while "LastEvaluatedKey" in page:
            page = self._messages.query(
                KeyConditionExpression=condition,
                ConsistentRead=True,
                ExclusiveStartKey=page["LastEvaluatedKey"],
            )
            messages.extend(Message.from_item(item) for item in page["Items"])
        return messages

    def stored(self, customer_id: str, message_key: str) -> Message | None:
        item = self._messages.get_item(
            Key={"customer_id": customer_id, "message_key": message_key}, ConsistentRead=True
        ).get("Item")
        return Message.from_item(item) if item else None

    def take_turn(self, message: Message, now: datetime) -> None:
        try:
            self._rooms.update_item(
                Key={"customer_id": message.customer_id, "room_id": message.room_id},
                UpdateExpression="SET turn_message_id = :message, turn_started_at = :now",
                ConditionExpression="attribute_exists(room_id) AND (attribute_not_exists(turn_message_id) "
                "OR turn_message_id = :message OR turn_started_at < :expired)",
                ExpressionAttributeValues={
                    ":message": message.message_id,
                    ":now": format_instant(now),
                    ":expired": format_instant(now - TURN_MARK_TTL),
                },
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise TurnInProgress(message.room_id) from error
            raise

    def release_turn(self, message: Message) -> None:
        try:
            self._rooms.update_item(
                Key={"customer_id": message.customer_id, "room_id": message.room_id},
                UpdateExpression="REMOVE turn_message_id, turn_started_at",
                ConditionExpression="turn_message_id = :message",
                ExpressionAttributeValues={":message": message.message_id},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    def _stored(self, message: Message) -> Message:
        stored = self.stored(message.customer_id, message.message_key)
        assert stored is not None
        return stored

    def _open_room(self, customer_id: str, room_id: str, created_at: str) -> None:
        put_if_absent(
            self._rooms,
            {
                "customer_id": customer_id,
                "room_id": room_id,
                "created_at": created_at,
                "delegated_to_human": False,
            },
            "room_id",
        )
