---
icon: robot
description: Use the Algenta docs with any AI — the auto-generated llms.txt context files, per-page Markdown, the built-in MCP server, and copy/open-in-chat actions.
---

# Using these docs with AI

These docs are built to be read by machines as well as people. Algenta is a deep product, so the documentation is structured so that an AI assistant — Claude, ChatGPT, Cursor, or your own bot — can pull in accurate, current context and answer questions about the engine without guessing.

Everything here works against the published Algenta docs site (for example `https://docs.algenta.ai`). Swap in your own docs domain if you are reading a self-published copy.

## LLM-ready context files

GitBook publishes the entire documentation set as plain-text context files at well-known paths, regenerated on every change. Point any model at them.

| Path | What it contains |
| --- | --- |
| `/llms.txt` | A structured map of the docs — every page title, description, and link. The right size for a system prompt or a retrieval index. |
| `/llms-full.txt` | The full text of every page concatenated into one document. Drop it straight into a long-context model. |
| `<any-page>.md` | The raw Markdown of a single page — append nothing special; the page is served as Markdown to clients that ask for it. |

```bash title="Fetch the full docs as one LLM context document"
curl -sS https://docs.algenta.ai/llms-full.txt -o algenta-docs.txt
# Then attach algenta-docs.txt to your prompt, or chunk it into a vector store.
```

{% hint style="info" %}
`llms.txt` is the index; `llms-full.txt` is the corpus. For a retrieval pipeline, embed `llms-full.txt` in chunks and keep `llms.txt` as the table of contents. For a single long-context call, `llms-full.txt` alone is usually enough.
{% endhint %}

## The built-in MCP server

GitBook exposes these docs as a [Model Context Protocol](../sdk/mcp.md) server, so an MCP-aware client can search and read the documentation as a live tool — no scraping, always current.

```text title="MCP endpoint"
https://docs.algenta.ai/~gitbook/mcp
```

Add it to an MCP client the same way you would any other server. For example, in a client that takes a URL-based server:

```json title="Example MCP client entry"
{
  "mcpServers": {
    "algenta-docs": {
      "url": "https://docs.algenta.ai/~gitbook/mcp"
    }
  }
}
```

Once connected, the assistant can answer "how do I run the Mojo engine?" or "what is `device_identity_mismatch`?" by reading the actual pages instead of relying on its training data.

{% hint style="warning" %}
The docs MCP server is distinct from Algenta's own [MCP server](../sdk/mcp.md), which exposes the *engine* (run simulations, query data) rather than the documentation. Use the docs MCP for questions about Algenta; use the product MCP to actually call the engine.
{% endhint %}

## Per-page actions

Every page carries actions for moving its content into a chat:

* **Copy as Markdown** — copy the clean Markdown of the current page to paste into any assistant.
* **Open in ChatGPT / Claude** — open the current page as context in a new chat with one click.
* **View as Markdown** — see the raw `.md` behind the rendered page.

These are the fastest way to ask a question about the page you are already reading.

## Point your own chatbot at the docs

To ground a custom assistant, you have three good options, smallest effort first:

1. **Long-context prompt** — fetch `/llms-full.txt` and attach it to the conversation. Best for one-off or low-volume use.
2. **Retrieval (RAG)** — chunk and embed `/llms-full.txt`, and use `/llms.txt` as a citation map. Best for a production assistant over a large surface.
3. **MCP tool** — connect the assistant to `/~gitbook/mcp` so it reads pages on demand. Best when you want always-fresh answers with no re-indexing.

Because the context files and the MCP server regenerate from the same source as this site, every approach stays in sync with the published docs.

## For documentation owners

A few of the AI features above depend on settings in the GitBook organization, not on anything in this repository:

* **Page Actions** must be enabled for the site to turn on *Copy as Markdown*, *Open in ChatGPT/Claude*, and the docs MCP server at `/~gitbook/mcp`.
* **AI Search** (in-site natural-language search) requires a GitBook Premium or Ultimate plan.
* `/llms.txt`, `/llms-full.txt`, and per-page `.md` are served automatically on any published site — no configuration needed.

## Related pages

{% content-ref url="../sdk/mcp.md" %}
[mcp.md](../sdk/mcp.md)
{% endcontent-ref %}

{% content-ref url="quick-reference.md" %}
[quick-reference.md](quick-reference.md)
{% endcontent-ref %}

{% content-ref url="glossary.md" %}
[glossary.md](glossary.md)
{% endcontent-ref %}
