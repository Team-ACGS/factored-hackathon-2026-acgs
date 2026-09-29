import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
)
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from core.access import AccessDenied, Pool, Principal, customer_session
from core.accounts import Accounts, public_transaction
from core.customers import read_customer
from core.ids import InvalidId, format_instant, parse_uuid7, uuid7_time
from core.observability import logger, metrics, tracer
from crud.catalog import COUNTRIES, LANGUAGES
from crud.cursor import InvalidCursor, decode_cursor, encode_cursor
from crud.generator import Claim, Score, generate, manual_transaction
from crud.store import CustomerNotFound, SetupAlreadyCompleted, Store

SERVICE = "crud"
PAGE_SIZE = 20
MAX_CLOCK_SKEW = timedelta(minutes=2)
SUFFIX_ATTEMPTS = 20

app = APIGatewayRestResolver(cors=CORSConfig(allow_origin="*", max_age=300))


class Conflict(ServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(409, message)


def _customer() -> Principal:
    claims = app.current_event.request_context.authorizer.claims or {}
    try:
        principal = Principal.from_claims(claims)
    except AccessDenied as error:
        raise ForbiddenError(str(error)) from error
    if principal.pool is not Pool.CUSTOMERS:
        raise ForbiddenError("only customers reach their own data")
    logger.append_keys(customer_id=principal.subject)
    return principal


def _body() -> dict[str, Any]:
    try:
        body = json.loads(app.current_event.body or "")
    except json.JSONDecodeError as error:
        raise BadRequestError("body is not JSON") from error
    if not isinstance(body, dict):
        raise BadRequestError("body is not an object")
    return body


def _json(status: int, body: dict[str, Any]) -> Response[str]:
    return Response(status_code=status, content_type=content_types.APPLICATION_JSON, body=json.dumps(body))


def _uuid7_path(value: str, what: str) -> str:
    try:
        parse_uuid7(value)
    except InvalidId as error:
        raise NotFoundError(f"{what} not found") from error
    return value


def _profile(customer: dict[str, Any]) -> dict[str, Any]:
    return {
        "country": customer["country"],
        "language": customer["language"],
        "setup_completed": customer["setup_completed_at"] is not None,
    }


def _now() -> datetime:
    return datetime.now(UTC)


@app.get("/crud/profile")
@tracer.capture_method(capture_response=False)
def get_profile() -> dict[str, Any]:
    principal = _customer()
    customer = read_customer(customer_session(principal.subject, SERVICE).dynamodb, principal.subject)
    if customer is None:
        raise NotFoundError("customer not found")
    return {"profile": _profile(customer)}


@app.post("/crud/profile/setup")
@tracer.capture_method(capture_response=False)
def complete_setup() -> Response[str]:
    principal = _customer()
    body = _body()
    country, language = body.get("country"), body.get("language")
    if (
        not isinstance(country, str)
        or not isinstance(language, str)
        or country not in COUNTRIES
        or language not in LANGUAGES
    ):
        raise BadRequestError(
            f"country must be one of {sorted(COUNTRIES)} and language one of {list(LANGUAGES)}"
        )
    store = Store.from_dynamodb(customer_session(principal.subject, SERVICE).dynamodb)
    try:
        claimed = store.claim_setup(principal.subject, country, language, format_instant(_now()))
    except CustomerNotFound as error:
        raise NotFoundError("customer not found") from error
    except SetupAlreadyCompleted as error:
        raise Conflict("setup already completed") from error
    claim = _claim(principal.subject, claimed.country, claimed.setup_claimed_at)
    account = generate(claim)
    store.write_account(account.cards, account.transactions)
    try:
        customer = store.complete_setup(principal.subject, format_instant(_now()))
    except SetupAlreadyCompleted as error:
        raise Conflict("setup already completed") from error
    logger.info("setup completed", country=claim.country.code, transactions=len(account.transactions))
    metrics.add_metric(name="SetupsCompleted", unit=MetricUnit.Count, value=1)
    return _json(
        201,
        {
            "profile": _profile(customer),
            "cases": [
                {"kind": kind.value, "transaction": public_transaction(item)} for kind, item in account.cases
            ],
        },
    )


@app.get("/crud/cards")
@tracer.capture_method(capture_response=False)
def list_cards() -> dict[str, Any]:
    principal = _customer()
    accounts = Accounts.from_dynamodb(customer_session(principal.subject, SERVICE).dynamodb)
    return {"cards": accounts.cards(principal.subject)}


@app.get("/crud/cards/<product_id>")
@tracer.capture_method(capture_response=False)
def get_card(product_id: str) -> dict[str, Any]:
    principal = _customer()
    _uuid7_path(product_id, "card")
    cursor = app.current_event.get_query_string_value("cursor")
    try:
        after_key = decode_cursor(cursor, product_id) if cursor is not None else None
    except InvalidCursor as error:
        raise BadRequestError(str(error)) from error
    accounts = Accounts.from_dynamodb(customer_session(principal.subject, SERVICE).dynamodb)
    card = accounts.card(principal.subject, product_id)
    if card is None:
        raise NotFoundError("card not found")
    transactions, next_key = accounts.newest_transactions(principal.subject, product_id, PAGE_SIZE, after_key)
    return {
        "card": card,
        "transactions": transactions,
        "next_cursor": encode_cursor(next_key) if next_key else None,
        "server_time": format_instant(_now()),
    }


@app.get("/crud/cards/<product_id>/transactions/<transaction_id>")
@tracer.capture_method(capture_response=False)
def get_transaction(product_id: str, transaction_id: str) -> dict[str, Any]:
    principal = _customer()
    _uuid7_path(product_id, "card")
    _uuid7_path(transaction_id, "transaction")
    accounts = Accounts.from_dynamodb(customer_session(principal.subject, SERVICE).dynamodb)
    transaction = accounts.transaction(principal.subject, product_id, transaction_id)
    if transaction is None:
        raise NotFoundError("transaction not found")
    return {"transaction": transaction}


@app.post("/crud/cards/<product_id>/transactions")
@tracer.capture_method(capture_response=False)
def add_transaction(product_id: str) -> Response[str]:
    principal = _customer()
    _uuid7_path(product_id, "card")
    body = _body()
    transaction_id, kind, score = (
        body.get("transaction_id"),
        body.get("kind"),
        body.get("score", Score.MISSED.value),
    )
    if kind not in ("normal", "suspicious") or score not in [option.value for option in Score]:
        raise BadRequestError("kind must be normal or suspicious, and score flagged, missed or none")
    try:
        minted_at = uuid7_time(parse_uuid7(transaction_id))
    except InvalidId as error:
        raise BadRequestError(str(error)) from error
    if abs(_now() - minted_at) > MAX_CLOCK_SKEW:
        raise BadRequestError("transaction_id is too far from server time")

    dynamodb = customer_session(principal.subject, SERVICE).dynamodb
    accounts, store = Accounts.from_dynamodb(dynamodb), Store.from_dynamodb(dynamodb)
    if accounts.card(principal.subject, product_id) is None:
        raise NotFoundError("card not found")
    stored = accounts.transaction(principal.subject, product_id, str(transaction_id))
    if stored is not None:
        return _json(200, {"transaction": stored})
    stored_claim = store.claim(principal.subject)
    if stored_claim is None:
        raise NotFoundError("customer not found")
    claim = _claim(principal.subject, stored_claim.country, stored_claim.setup_claimed_at)

    rng = secrets.SystemRandom()
    if kind == "normal":
        item = manual_transaction(rng, claim, product_id, str(transaction_id))
    else:
        item = manual_transaction(
            rng,
            claim,
            product_id,
            str(transaction_id),
            _reserve_suffix(store, principal.subject),
            Score(score),
        )
    if not store.add_transaction(item):
        concurrent = accounts.transaction(principal.subject, product_id, str(transaction_id))
        return _json(200, {"transaction": concurrent})
    logger.info("transaction added", kind=kind, transaction_id=transaction_id)
    metrics.add_metric(name="TransactionsAdded", unit=MetricUnit.Count, value=1)
    return _json(201, {"transaction": public_transaction(item)})


def _draw_suffix() -> int:
    return 1000 + secrets.randbelow(9000)


def _reserve_suffix(store: Store, customer_id: str) -> int:
    for _ in range(SUFFIX_ATTEMPTS):
        suffix = _draw_suffix()
        if store.reserve_suspicious_suffix(customer_id, suffix):
            return suffix
    raise ServiceError(503, "no free merchant suffix, try again")


def _claim(customer_id: str, country: str | None, claimed_at: str | None) -> Claim:
    if country not in COUNTRIES or claimed_at is None:
        raise Conflict("setup not started")
    return Claim(
        customer_id=customer_id, country=COUNTRIES[country], anchor=datetime.fromisoformat(claimed_at)
    )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST, clear_state=True)
@tracer.capture_lambda_handler(capture_response=False)
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
