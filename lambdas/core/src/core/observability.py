import os

from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger()
metrics = Metrics()
tracer = Tracer()


def trace_id() -> str | None:
    header = os.environ.get("_X_AMZN_TRACE_ID", "")
    fields = dict(part.split("=", 1) for part in header.split(";") if "=" in part)
    return fields.get("Root")
