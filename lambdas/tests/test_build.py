import importlib
import importlib.util
from pathlib import Path

import build


def test_every_deployed_function_has_an_entry_that_exposes_its_handler() -> None:
    assert set(build.FUNCTIONS) == {
        "crud",
        "messages",
        "chat-notifier",
        "chatbot",
        "auth-post-confirmation",
        "auth-pre-token-generation",
        "auth-custom-message",
    }
    for function in build.FUNCTIONS.values():
        for module in function.entries.values():
            assert callable(importlib.import_module(module).handler)
        assert set(function.packages) <= set(build.SOURCES)


def test_the_entry_file_exposes_the_handler_lambda_calls(tmp_path: Path) -> None:
    path = tmp_path / "pre_token_generation.py"
    path.write_text(build.entry("auth.pre_token_generation"))
    spec = importlib.util.spec_from_file_location("entry", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.handler)
