import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"


DEFAULT_PLATFORM = "x86_64-manylinux2014"
AMAZON_LINUX_2023 = "x86_64-manylinux_2_28"


@dataclass(frozen=True)
class Function:
    project: str
    packages: tuple[str, ...]
    entries: dict[str, str]
    platform: str = DEFAULT_PLATFORM


FUNCTIONS = {
    "crud": Function("clara-crud", ("core", "crud"), {"handler.py": "crud.handler"}),
    "messages": Function("clara-messages", ("core", "messages"), {"handler.py": "messages.handler"}),
    "chat-notifier": Function(
        "clara-chat-notifier", ("core", "chat_notifier"), {"handler.py": "chat_notifier.handler"}
    ),
    "chatbot": Function(
        "clara-chatbot", ("core", "chatbot"), {"handler.py": "chatbot.handler"}, AMAZON_LINUX_2023
    ),
    "auth-post-confirmation": Function(
        "clara-auth", ("core", "auth"), {"post_confirmation.py": "auth.post_confirmation"}
    ),
    "auth-pre-token-generation": Function(
        "clara-auth", ("core", "auth"), {"pre_token_generation.py": "auth.pre_token_generation"}
    ),
    "auth-custom-message": Function(
        "clara-auth", ("core", "auth"), {"custom_message.py": "auth.custom_message"}
    ),
}

SOURCES = {
    "core": ROOT / "core/src/core",
    "auth": ROOT / "auth/src/auth",
    "crud": ROOT / "crud/src/crud",
    "messages": ROOT / "messages/src/messages",
    "chat_notifier": ROOT / "chat_notifier/src/chat_notifier",
    "chatbot": ROOT / "chatbot/src/chatbot",
}


def entry(module: str) -> str:
    return f'from {module} import handler\n\n__all__ = ["handler"]\n'


def build(name: str, function: Function) -> None:
    target = DIST / name
    with tempfile.TemporaryDirectory() as scratch:
        requirements = Path(scratch) / "requirements.txt"
        run(
            "uv",
            "export",
            "--quiet",
            "--frozen",
            "--no-dev",
            "--no-emit-workspace",
            "--package",
            function.project,
            "--output-file",
            str(requirements),
        )
        run(
            "uv",
            "pip",
            "install",
            "--quiet",
            "--no-deps",
            "--target",
            str(target),
            "--python-version",
            "3.12",
            "--python-platform",
            function.platform,
            "--only-binary",
            ":all:",
            "--requirement",
            str(requirements),
        )
    for package in function.packages:
        shutil.copytree(SOURCES[package], target / package, ignore=shutil.ignore_patterns("__pycache__"))
    for filename, module in function.entries.items():
        (target / filename).write_text(entry(module))


def run(*command: str) -> None:
    subprocess.run(command, check=True, cwd=ROOT)


def main(names: list[str]) -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    for name in names or list(FUNCTIONS):
        build(name, FUNCTIONS[name])
        print(f"built dist/{name}")


if __name__ == "__main__":
    main(sys.argv[1:])
