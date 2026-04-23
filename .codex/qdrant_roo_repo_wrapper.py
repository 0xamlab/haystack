#!/usr/bin/env python3
import os

os.environ["QDRANT_URL"] = "https://b9e98c47-dc6c-4db2-a038-56f158cd1885.us-east-1-1.aws.cloud.qdrant.io"
os.environ["QDRANT_API_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6OWQzMGY3NTMtNjM4My00MDY0LTk5MGMtZjU0NWEyMGYxYjc2In0.1WDJAuF1zre4LhpKWMnCqo-fq6vJVF7eGA1NWpF6xFQ"
os.environ["OPENAI_API_KEY"] = "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"
os.environ["COLLECTION_NAME"] = "ws-fd69a63ccb0ad2ab"

os.chdir("/Users/angel/Developer/decision-engine")
UV = "/Users/angel/.local/bin/uv"
os.execvp(UV, [UV, "run", "/Users/angel/.codex/mcp-servers/qdrant_roo.py"])
