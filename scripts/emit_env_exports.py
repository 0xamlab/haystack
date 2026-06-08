from __future__ import annotations

import ast
import re
import shlex
import sys
from pathlib import Path

_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_value(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        try:
            value = ast.literal_eval(text)
        except Exception:
            return text[1:-1]
        return value if isinstance(value, str) else str(value)
    return text


def emit_env_exports(path: Path) -> list[str]:
    exports: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = stripped[len("export ") :].lstrip() if stripped.startswith("export ") else stripped
        if "=" not in body:
            raise ValueError(f"{path}:{line_number} must use KEY=value syntax.")
        key, raw_value = body.split("=", 1)
        normalized_key = key.strip()
        if not _ENV_KEY_PATTERN.fullmatch(normalized_key):
            raise ValueError(
                f"{path}:{line_number} has invalid environment variable name '{normalized_key}'."
            )
        exports.append(f"export {normalized_key}={shlex.quote(_parse_value(raw_value))}")
    return exports


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: emit_env_exports.py <env-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        exports = emit_env_exports(path)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for line in exports:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
