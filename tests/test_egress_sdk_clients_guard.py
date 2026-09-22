"""B10 PR4: the egress_sdk_clients sibling guard.

raw_egress only matches httpx/urllib/requests/boto3, so it is BLIND to the connectors' primary
non-httpx transports (aiobotocore session.create_client — the default async S3 read path; GCS
storage.Client; azure Blob{Service,}Client; neo4j GraphDatabase.driver; asyncpg.connect;
smtplib.SMTP). This guard surfaces every such construction outside the approved egress wrappers, so
a NEW unguarded SDK transport (e.g. a new connector that forgets to enforce) fails fatally instead
of shipping with raw_egress green.

Note: this is DETECTION of construction sites, not enforce-ordering verification — the enforce
often lives in a caller (neo4j _connect_sync, data_connection_browse._sync), so enforce-precedes
stays a code-review concern aided by the guard surfacing every site."""

from __future__ import annotations

import pytest

from scripts.reliability_guards import GUARDS, run_guards
from scripts.reliability_guards.guards.egress_sdk_clients import _RE


@pytest.mark.parametrize(
    "line",
    [
        'async with session.create_client("s3", **kwargs) as client:',
        "return storage.Client(project=config.get('project_id'))",
        "return GraphDatabase.driver(uri, auth=auth)",
        "conn = await asyncpg.connect(dsn)",
        "service = BlobServiceClient(account_url=url, credential=None)",
        "service = BlobServiceClient.from_connection_string(cs)",
        "svc = AsyncBlobServiceClient.from_connection_string(cs)",  # Async-prefixed alias still flags
        "with smtplib.SMTP(host, port) as server:",
    ],
)
def test_regex_flags_real_sdk_constructions(line):
    assert _RE.search(line) is not None


@pytest.mark.parametrize(
    "line",
    [
        "from azure.storage.blob import BlobClient, BlobServiceClient",  # import, no call
        "smtp_factory=smtplib.SMTP,",  # factory reference, not a call
        "smtp_factory: Callable[..., Any] = smtplib.SMTP",  # default-arg reference
        "_PUBLIC_SYNC_CLIENT: httpx.Client | None = None",  # httpx is raw_egress's job, not this guard
        "client = boto3.client('s3', **kwargs)",  # boto3 is raw_egress's job",
        "conn = sqlite3.connect(path)",  # local sqlite, not a network SDK client",
    ],
)
def test_regex_ignores_non_constructions_and_out_of_scope(line):
    assert _RE.search(line) is None


def test_guard_is_registered():
    assert "egress_sdk_clients" in GUARDS


def test_guard_runs_clean_on_tree():
    # every current SDK-client site is baselined; no NEW violations
    result = run_guards(guards=["egress_sdk_clients"])
    assert result["egress_sdk_clients"]["new"] == []
    # and it is actually finding the known sites (not a no-op regex)
    assert len(result["egress_sdk_clients"]["known"]) >= 8
