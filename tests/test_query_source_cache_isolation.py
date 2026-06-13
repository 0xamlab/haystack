"""Cross-tenant isolation: the query/source caches (_SOURCE_CACHE/_DF_CACHE) are process-global and
were keyed by an org-AGNOSTIC identity — `source_id` (shared visibility omitted org) and the
content/url/connection hashes. Two different orgs with byte-identical content (or the same
url/connection) collided on one cache entry. Both are now org-scoped; within-org dedup is preserved.
"""

from __future__ import annotations

from apps.api_server.routers.query._cache_classes import _source_cache_key
from apps.api_server.schemas.data_map import DataSource
from apps.api_server.services.source_registration_scope import resolve_registration_scopes


def _identity(key: str) -> str:
    return key  # stand-in for reg.source_id_for (returns the derivation input verbatim)


def _scopes(org_id: str) -> str:
    return resolve_registration_scopes(
        cache_key="CONTENT_HASH",
        visibility="shared",  # the previously org-agnostic branch
        auth_user_id=None,
        auth_key_id=None,
        owner_user_id=None,
        owner_key_id=None,
        source_id_for_fn=_identity,
        org_id=org_id,
    )[3]


def test_resolve_registration_scopes_shared_is_org_scoped():
    a, b = _scopes("orgA"), _scopes("orgB")
    assert a != b  # identical shared content -> distinct source_id per org (no cross-org collision)
    assert a == _scopes("orgA")  # stable within an org (dedup preserved)
    assert "orgA" in a


def test_source_cache_key_content_is_org_scoped():
    src = DataSource(name="x", csv="a,b\n1,2\n")
    ka = _source_cache_key(src, org_id="orgA")[0]
    kb = _source_cache_key(src, org_id="orgB")[0]
    assert ka != kb  # identical csv -> distinct cache key per org
    assert ka == _source_cache_key(src, org_id="orgA")[0]  # stable within an org


def test_source_cache_key_url_is_org_scoped():
    src = DataSource(name="x", url="https://example.com/data.csv")
    assert _source_cache_key(src, org_id="orgA")[0] != _source_cache_key(src, org_id="orgB")[0]


def test_source_cache_key_registry_id_is_unaffected():
    # A registry source's key IS its source_id, already made org-unique by resolve_registration_scopes
    # — so the cache key is the id verbatim regardless of the calling org.
    src = DataSource(name="x", source_id="reg-123")
    assert _source_cache_key(src, org_id="orgA")[0] == "reg-123"
    assert _source_cache_key(src, org_id="orgB")[0] == "reg-123"
