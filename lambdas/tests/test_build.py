import importlib
import importlib.util
import os
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


def test_bytecode_is_identical_across_builds_and_trusted_without_the_source_time(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for target in (first, second):
        (target / "pkg").mkdir(parents=True)
        (target / "pkg" / "mod.py").write_text("VALUE = 1\n")
    build.compile_bytecode(first)
    os.utime(second / "pkg" / "mod.py", (0, 0))
    build.compile_bytecode(second)

    [pyc] = (first / "pkg" / "__pycache__").glob("mod.*.pyc")
    assert pyc.read_bytes() == (second / "pkg" / "__pycache__" / pyc.name).read_bytes()
    assert int.from_bytes(pyc.read_bytes()[4:8], "little") == 0b01
    assert b"/var/task/pkg/mod.py" in pyc.read_bytes()
