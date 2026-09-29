import os

from aws_lambda_powertools import Logger, Metrics, Tracer

logger = Logger()
metrics = Metrics()
tracer = Tracer(patch_modules=["botocore"])


def trace_id() -> str | None:
    header = os.environ.get("_X_AMZN_TRACE_ID", "")
    fields = dict(part.split("=", 1) for part in header.split(";") if "=" in part)
    return fields.get("Root")


def annotate_origin(origin_trace_id: str | None) -> None:
    if origin_trace_id:
        tracer.put_annotation(key="origin_trace_id", value=origin_trace_id)
