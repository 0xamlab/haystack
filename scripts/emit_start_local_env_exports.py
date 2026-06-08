from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.emit_env_exports import emit_env_exports

_ALLOWED_EXACT_KEYS = {
    "ALGENTA_API_KEY",
    "DE_API_KEY",
    "ALGENTA_LLM_PROVIDER_MODELS_JSON",
    "ALGENTA_MCP_PORT",
    "OLLAMA_HOST",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "GROQ_API_KEY",
    "XAI_API_KEY",
}
_ALLOWED_PREFIXES = (
    "ALGENTA_LOCAL_",
    "DE_LOCAL_",
)


def emit_start_local_env_exports(path: Path) -> list[str]:
    exports = emit_env_exports(path)
    filtered: list[str] = []
    for export_line in exports:
        prefix, remainder = export_line.split(" ", 1)
        if prefix != "export":
            continue
        key = remainder.split("=", 1)[0]
        if key in _ALLOWED_EXACT_KEYS or key.startswith(_ALLOWED_PREFIXES):
            filtered.append(export_line)
    return filtered


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: emit_start_local_env_exports.py <env-file>", file=sys.stderr)
        return 2
    try:
        exports = emit_start_local_env_exports(Path(argv[1]))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for line in exports:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
