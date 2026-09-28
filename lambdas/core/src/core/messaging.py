import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal, cast, get_args

import boto3
from boto3.dynamodb.conditions import Key

from core.conditional import put_if_absent
from core.ids import InvalidId, format_instant, parse_uuid7, successor, uuid7_time

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

SenderType = Literal["customer", "assistant", "agent"]

MAX_CLOCK_SKEW = timedelta(minutes=2)
MAX_TEXT_LENGTH = 2000


class InvalidMessage(ValueError):
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

    @property
    def message_key(self) -> str:
        return f"{self.room_id}#{self.sent_at}#{self.message_id}"

    def to_item(self) -> dict[str, str]:
        return {
            "customer_id": self.customer_id,
            "message_key": self.message_key,
            "room_id": self.room_id,
            "message_id": self.message_id,
            "sender_type": self.sender_type,
            "text": self.text,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }

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
        )

    def public(self) -> dict[str, str]:
        return {
            "room_id": self.room_id,
            "message_id": self.message_id,
            "sender_type": self.sender_type,
            "text": self.text,
            "sent_at": self.sent_at,
            "created_at": self.created_at,
        }


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


def customer_message(customer_id: str, room_id: str, message_id: str, text: str, now: datetime) -> Message:
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
    )


def reply_to(message: Message, sender_type: SenderType, text: str, now: datetime) -> Message:
    return Message(
        customer_id=message.customer_id,
        room_id=message.room_id,
        message_id=str(successor(uuid.UUID(message.message_id))),
        sender_type=sender_type,
        text=text,
        sent_at=message.sent_at,
        created_at=format_instant(now),
    )


class Messaging:
    def __init__(self, rooms: "Table", messages: "Table") -> None:
        self._rooms = rooms
        self._messages = messages

    @classmethod
    def from_session(cls, session: boto3.Session) -> "Messaging":
        dynamodb = session.resource("dynamodb")
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

    def _stored(self, message: Message) -> Message:
        item = self._messages.get_item(
            Key={"customer_id": message.customer_id, "message_key": message.message_key}, ConsistentRead=True
        )["Item"]
        return Message.from_item(item)

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
