from typing import Any

from core.facts.values import Ledger
from core.tools.context import Decide, ToolContext, ToolResult, Verdict
from core.tools.registry import TOOLS, Tool, call


def list_cards(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("list_cards", arguments, context, ledger)


def card_status(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("card_status", arguments, context, ledger)


def search_movements(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("search_movements", arguments, context, ledger)


def merchant_history(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("merchant_history", arguments, context, ledger)


def spend_summary(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("spend_summary", arguments, context, ledger)


def recurring_charges(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("recurring_charges", arguments, context, ledger)


def charge_facts(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("charge_facts", arguments, context, ledger)


def case_status(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("case_status", arguments, context, ledger)


def recall(context: ToolContext, ledger: Ledger, **arguments: Any) -> ToolResult:
    return call("recall", arguments, context, ledger)


__all__ = [
    "TOOLS",
    "Decide",
    "Tool",
    "ToolContext",
    "ToolResult",
    "Verdict",
    "call",
    "card_status",
    "case_status",
    "charge_facts",
    "list_cards",
    "merchant_history",
    "recall",
    "recurring_charges",
    "search_movements",
    "spend_summary",
]
