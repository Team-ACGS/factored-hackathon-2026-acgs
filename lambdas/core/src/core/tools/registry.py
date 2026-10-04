from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from core.accounts import ReadIncomplete
from core.facts.values import Ledger, Trace
from core.tools.cards import CardStatusInput, ListCardsInput, card_status, list_cards
from core.tools.cases import CaseStatusInput, case_status
from core.tools.charges import ChargeFactsInput, charge_facts
from core.tools.context import InvalidArgument, NotFound, ToolContext, ToolResult
from core.tools.inputs import Input
from core.tools.memory import RecallInput, recall
from core.tools.movements import (
    MerchantHistoryInput,
    RecurringChargesInput,
    SearchMovementsInput,
    SpendSummaryInput,
    merchant_history,
    recurring_charges,
    search_movements,
    spend_summary,
)
from core.tools.policies import SearchPoliciesInput, search_policies
from core.vectors import POLICY_ATTEMPTS, VectorStoreError

RETRIES = 2


@dataclass(frozen=True)
class Tool:
    name: str
    family: str
    input_model: type[Input]
    run: Callable[[ToolContext, Ledger, Any], list[str]]
    attempts: int = RETRIES + 1

    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool("list_cards", "cards", ListCardsInput, list_cards),
        Tool("card_status", "cards", CardStatusInput, card_status),
        Tool("search_movements", "movements", SearchMovementsInput, search_movements),
        Tool("merchant_history", "movements", MerchantHistoryInput, merchant_history),
        Tool("spend_summary", "movements", SpendSummaryInput, spend_summary),
        Tool("recurring_charges", "movements", RecurringChargesInput, recurring_charges),
        Tool("charge_facts", "movements", ChargeFactsInput, charge_facts),
        Tool("case_status", "cases", CaseStatusInput, case_status),
        Tool("recall", "memory", RecallInput, recall),
        Tool("search_policies", "policies", SearchPoliciesInput, search_policies, POLICY_ATTEMPTS),
    )
}


def call(name: str, arguments: Mapping[str, Any], context: ToolContext, ledger: Ledger) -> ToolResult:
    tool = TOOLS.get(name)
    if tool is None:
        return _error(ledger, name, "invalid_argument", "unknown tool")
    try:
        args = tool.input_model.model_validate(dict(arguments))
    except ValidationError as error:
        return _error(ledger, name, "invalid_argument", _describe(error))
    for attempt in range(tool.attempts):
        try:
            return ToolResult(name, tuple(tool.run(context, ledger, args)))
        except NotFound:
            return _error(ledger, name, "not_found", "no such item among the customer's own")
        except InvalidArgument as error:
            return _error(ledger, name, "invalid_argument", str(error))
        except (ClientError, BotoCoreError, ReadIncomplete, VectorStoreError):
            if attempt + 1 == tool.attempts:
                return _error(ledger, name, "unavailable", "the data could not be read")
    raise AssertionError("unreachable")


def _error(ledger: Ledger, tool: str, code: str, detail: str) -> ToolResult:
    fact = ledger.add("error", {"tool": Trace(tool), "error": Trace(code), "detail": Trace(detail)})
    return ToolResult(tool, (fact.id,))


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in issue['loc']) or 'arguments'}: {issue['msg']}"
        for issue in error.errors()[:3]
    )
