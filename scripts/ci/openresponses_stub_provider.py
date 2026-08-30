#!/usr/bin/env python3
"""CI-only deterministic stub upstream for the OpenResponses conformance job.

Stands in for a real LLM provider so the openresponses/openresponses compliance CLI can run
against a REAL, network-listening instance of /v1/responses with zero external API key and
fully deterministic content -- matching the "openai_compatible" provider backend's real,
already-supported wire contract (apps/api_server/services/llm_provider_service/_chat_api.py,
_payload_builders.py, _response_parsing.py), the exact same request/response shape the existing
in-process fake in tests/test_llm_chat_completions_tool_calling_contract.py's
_FakeUpstreamClient asserts against -- just reachable over a real socket instead of a
monkeypatched httpx.AsyncClient, because the compliance CLI drives our app over real HTTP.

Not a general-purpose OpenAI mock: it implements exactly the one endpoint
(POST /chat/completions) and exactly the one behavior the conformance filter's scenarios need --
echo a deterministic assistant message, or (when the request carries `tools`) call the first
tool with a fixed, deterministic argument blob. No model, no randomness, no network egress.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_COMPLETION_ID = "chatcmpl_openresponses_stub_0001"


class _StubHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        # Quiet by default; uncomment for local debugging.
        pass

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler name
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            body = {}

        tools = body.get("tools") or []
        model = body.get("model", "stub-model")

        if tools:
            first_tool = tools[0]
            function_name = (
                first_tool.get("function", {}).get("name")
                if isinstance(first_tool.get("function"), dict)
                else first_tool.get("name")
            ) or "unknown_tool"
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_openresponses_stub_1",
                        "type": "function",
                        "function": {
                            "name": function_name,
                            "arguments": json.dumps({"location": "San Francisco, CA"}),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        else:
            message = {
                "role": "assistant",
                "content": (
                    "This is a deterministic stub response for OpenResponses "
                    "conformance testing."
                ),
            }
            finish_reason = "stop"

        response_body = {
            "id": _COMPLETION_ID,
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": message,
                }
            ],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        }
        payload = json.dumps(response_body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=58100)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), _StubHandler)
    print(f"openresponses stub provider listening on 127.0.0.1:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
