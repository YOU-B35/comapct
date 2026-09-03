"""Static, same-origin Amazon JSON requests through an authorized ZClaw page.

This module deliberately contains no Network discovery.  Production work can
only invoke entries reviewed into ``STATIC_AUTHENTICATED_ENDPOINTS``.  The
registry is empty until a real Seller Central session has produced approved,
redacted request/response fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from app.amazon.scope_planner import normalize_scope
from app.ziniao import cli_tools

SELLER_ORIGIN = "https://sellercentral.amazon.com"
_ALLOWED_SCOPES = frozenset({"daily", "reports", "account_health"})
_ALLOWED_METHODS = frozenset({"GET", "POST"})
_RESULT_FIELDS = frozenset({"metrics", "products", "outbound_orders", "seller_news", "cases"})
_REQUIRED_FIELDS = {
    "daily": frozenset({"metrics", "outbound_orders"}),
    "reports": frozenset({"products"}),
    "account_health": frozenset({"metrics"}),
}
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{2,79}$")
_MAX_BODY_CHARS = 1_000_000

RequestBuilder = Callable[[], Mapping[str, Any]]
ResponseMapper = Callable[[Any], Mapping[str, list[dict[str, Any]]]]


def _empty_request() -> Mapping[str, Any]:
    return {}


def _empty_mapper(_: Any) -> Mapping[str, list[dict[str, Any]]]:
    return {}


@dataclass(frozen=True)
class StaticAuthenticatedEndpoint:
    """A code-reviewed Seller Central request; never construct this from input."""

    key: str
    scope: str
    page_url: str
    method: str
    path: str
    provides: frozenset[str]
    version: str
    approved_at: str
    request_builder: RequestBuilder = _empty_request
    response_mapper: ResponseMapper = _empty_mapper
    csrf_meta_name: str = ""
    csrf_header_name: str = ""
    timeout_seconds: int = 30


@dataclass
class StaticScopeResult:
    scope: str = ""
    data: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {key: [] for key in _RESULT_FIELDS}
    )
    endpoint_keys: list[str] = field(default_factory=list)
    endpoint_versions: list[str] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    provided_fields: set[str] = field(default_factory=set)

    @property
    def complete(self) -> bool:
        required_fields = _REQUIRED_FIELDS.get(self.scope)
        return bool(required_fields) and required_fields.issubset(self.provided_fields)


# Do not add a guessed path here.  Each entry requires a real, redacted fixture
# and a mapper test before being approved into source control.
STATIC_AUTHENTICATED_ENDPOINTS: tuple[StaticAuthenticatedEndpoint, ...] = ()


def _validate_endpoint(endpoint: StaticAuthenticatedEndpoint) -> None:
    if not _KEY_RE.fullmatch(endpoint.key):
        raise ValueError("endpoint key is invalid")
    if endpoint.scope not in _ALLOWED_SCOPES:
        raise ValueError("endpoint scope is invalid")
    if endpoint.method.upper() not in _ALLOWED_METHODS:
        raise ValueError("endpoint method is invalid")
    page = urlsplit(endpoint.page_url)
    if page.scheme != "https" or page.netloc != "sellercentral.amazon.com":
        raise ValueError("endpoint page_url must be a Seller Central HTTPS URL")
    path = urlsplit(endpoint.path)
    if path.scheme or path.netloc or not endpoint.path.startswith("/") or endpoint.path.startswith("//"):
        raise ValueError("endpoint path must be a same-origin absolute path")
    if not endpoint.provides or not endpoint.provides.issubset(_RESULT_FIELDS):
        raise ValueError("endpoint provides contains an unsupported result field")
    if not endpoint.version or not endpoint.approved_at:
        raise ValueError("endpoint approval metadata is required")
    if bool(endpoint.csrf_meta_name) != bool(endpoint.csrf_header_name):
        raise ValueError("CSRF meta and header names must be configured together")
    if endpoint.timeout_seconds < 5 or endpoint.timeout_seconds > 60:
        raise ValueError("endpoint timeout must be between 5 and 60 seconds")


def _safe_request_payload(endpoint: StaticAuthenticatedEndpoint) -> dict[str, Any]:
    request = dict(endpoint.request_builder() or {})
    unexpected = set(request) - {"query", "body"}
    if unexpected:
        raise ValueError("request builder returned unsupported fields")
    query = request.get("query") or {}
    body = request.get("body")
    if not isinstance(query, Mapping):
        raise ValueError("request query must be an object")
    safe_query: dict[str, str] = {}
    for key, value in query.items():
        name = str(key).strip()
        if not name or len(name) > 100 or isinstance(value, (dict, list, tuple, set)):
            raise ValueError("request query contains an invalid value")
        safe_query[name] = str(value)
    if body is not None:
        encoded_body = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        if len(encoded_body) > 32_000:
            raise ValueError("request body is too large")
        body = json.loads(encoded_body)
    if endpoint.method.upper() == "GET" and body is not None:
        raise ValueError("GET endpoint cannot define a request body")
    return {"query": safe_query, "body": body}


def build_browser_fetch_script(endpoint: StaticAuthenticatedEndpoint) -> str:
    """Build the fixed browser-side fetch template for an approved endpoint."""
    _validate_endpoint(endpoint)
    request = _safe_request_payload(endpoint)
    spec = {
        "origin": SELLER_ORIGIN,
        "method": endpoint.method.upper(),
        "path": endpoint.path,
        "query": request["query"],
        "body": request["body"],
        "csrfMetaName": endpoint.csrf_meta_name,
        "csrfHeaderName": endpoint.csrf_header_name,
        "maxChars": _MAX_BODY_CHARS,
    }
    encoded = json.dumps(spec, ensure_ascii=False, separators=(",", ":"))
    return f"""async () => {{
  const spec = {encoded};
  if (window.location.origin !== spec.origin) {{
    return {{ ok: false, error: 'UNEXPECTED_PAGE_ORIGIN' }};
  }}
  const url = new URL(spec.path, window.location.origin);
  for (const [key, value] of Object.entries(spec.query)) url.searchParams.set(key, value);
  const headers = {{ Accept: 'application/json' }};
  if (spec.csrfMetaName && spec.csrfHeaderName) {{
    const meta = document.querySelector(`meta[name="${{spec.csrfMetaName}}"]`);
    const token = meta && meta.content ? meta.content : '';
    if (token) headers[spec.csrfHeaderName] = token;
  }}
  const init = {{ method: spec.method, credentials: 'same-origin', headers }};
  if (spec.body !== null) {{
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(spec.body);
  }}
  const response = await fetch(url.toString(), init);
  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  if (text.length > spec.maxChars) {{
    return {{ ok: false, status: response.status, error: 'RESPONSE_TOO_LARGE' }};
  }}
  if (!contentType.toLowerCase().includes('application/json')) {{
    return {{ ok: false, status: response.status, error: 'NON_JSON_RESPONSE' }};
  }}
  let body;
  try {{ body = JSON.parse(text); }} catch (_) {{
    return {{ ok: false, status: response.status, error: 'INVALID_JSON_RESPONSE' }};
  }}
  if (!response.ok) return {{ ok: false, status: response.status, error: 'HTTP_ERROR' }};
  return {{ ok: true, status: response.status, body }};
}}()"""


def _unwrap_exec_response(value: Any) -> Mapping[str, Any] | None:
    node = cli_tools.decode_json_data(value)
    for _ in range(3):
        if not isinstance(node, Mapping):
            return None
        if any(key in node for key in ("ok", "status", "body", "error")):
            return node
        child = next((node[key] for key in ("result", "value", "data") if key in node), None)
        node = cli_tools.decode_json_data(child)
    return node if isinstance(node, Mapping) else None


def _merge_rows(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    if field != "metrics":
        return [*existing, *incoming]
    merged: dict[str, dict[str, Any]] = {}
    for row in [*existing, *incoming]:
        key = str(row.get("metric_key") or "").strip()
        if key:
            merged[key] = row
    return list(merged.values())


def _scope_endpoints(scope: str) -> tuple[StaticAuthenticatedEndpoint, ...]:
    return tuple(endpoint for endpoint in STATIC_AUTHENTICATED_ENDPOINTS if endpoint.scope == scope)


def fetch_static_scope(store_id: str, scope: str) -> StaticScopeResult:
    """Execute only approved endpoints and return normalized data plus diagnostics."""
    normalized_scope = normalize_scope(scope)
    result = StaticScopeResult(scope=normalized_scope)
    visited_pages: set[str] = set()
    for endpoint in _scope_endpoints(normalized_scope):
        try:
            _validate_endpoint(endpoint)
            if endpoint.page_url not in visited_pages:
                visited = cli_tools.ziniao_page_visit(
                    store_id,
                    endpoint.page_url,
                    wait_until="domcontentloaded",
                    timeout=endpoint.timeout_seconds,
                )
                if not visited.get("ok"):
                    result.diagnostics.append({
                        "endpoint_key": endpoint.key,
                        "status": "page_unavailable",
                        "error": str(visited.get("error") or "page_visit_failed"),
                    })
                    continue
                visited_pages.add(endpoint.page_url)
            executed = cli_tools.ziniao_page_exec(
                store_id,
                build_browser_fetch_script(endpoint),
                timeout=endpoint.timeout_seconds,
            )
            if not executed.get("ok"):
                result.diagnostics.append({
                    "endpoint_key": endpoint.key,
                    "status": "execution_failed",
                    "error": str(executed.get("error") or "page_exec_failed"),
                })
                continue
            response = _unwrap_exec_response(executed.get("data"))
            if not response or not response.get("ok"):
                result.diagnostics.append({
                    "endpoint_key": endpoint.key,
                    "status": "response_failed",
                    "http_status": response.get("status") if response else None,
                    "error": str((response or {}).get("error") or "invalid_response"),
                })
                continue
            mapped = endpoint.response_mapper(response.get("body"))
            if not isinstance(mapped, Mapping):
                raise ValueError("response mapper must return an object")
            for field in endpoint.provides:
                rows = mapped.get(field)
                if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
                    raise ValueError(f"response mapper did not provide {field}")
                normalized_rows = [dict(row) for row in rows]
                result.data[field] = _merge_rows(result.data[field], normalized_rows, field)
                result.provided_fields.add(field)
            result.endpoint_keys.append(endpoint.key)
            result.endpoint_versions.append(endpoint.version)
            result.diagnostics.append({
                "endpoint_key": endpoint.key,
                "status": "success",
                "http_status": response.get("status"),
                "fields": sorted(endpoint.provides),
            })
        except Exception as exc:
            result.diagnostics.append({
                "endpoint_key": endpoint.key,
                "status": "rejected",
                "error": str(exc),
            })
    return result
