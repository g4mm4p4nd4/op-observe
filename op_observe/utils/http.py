"""Minimal HTTP client utilities to avoid external dependencies."""

from __future__ import annotations

from dataclasses import dataclass
import json
import ssl
from typing import Any, Mapping, MutableMapping, Optional
import urllib.error
import urllib.parse
import urllib.request


@dataclass(slots=True)
class HttpResponse:
    """Lightweight HTTP response wrapper."""

    status_code: int
    text: str
    headers: Mapping[str, str]

    def json(self) -> Any:
        if not self.text:
            return None
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Response body is not valid JSON") from exc


class HTTPSession:
    """Simplified HTTP session supporting the subset of requests used in the project."""

    def __init__(self) -> None:
        self.headers: MutableMapping[str, str] = {}

    # Public API ----------------------------------------------------------
    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        headers: Optional[Mapping[str, str]] = None,
        verify: bool = True,
        timeout: float = 30,
    ) -> HttpResponse:
        request_url = self._apply_params(url, params)
        request_headers = dict(self.headers)
        if headers:
            request_headers.update(headers)

        body: Optional[bytes]
        if json is not None:
            body = self._encode_json(json)
            request_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            body = self._encode_data(data, request_headers)
        else:
            body = None

        request = urllib.request.Request(
            request_url,
            data=body,
            headers=request_headers,
            method=method.upper(),
        )
        context = None
        if not verify and request.full_url.lower().startswith("https"):
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                response_text = response.read().decode("utf-8")
                response_headers = dict(response.headers.items())
                status = response.status
        except urllib.error.HTTPError as err:
            response_text = err.read().decode("utf-8") if err.fp else ""
            response_headers = dict(err.headers.items()) if err.headers else {}
            status = err.code
        except urllib.error.URLError as err:  # pragma: no cover - network failure
            raise ConnectionError(err.reason) from err

        return HttpResponse(status_code=status, text=response_text, headers=response_headers)

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("PUT", url, **kwargs)

    # Internal helpers ----------------------------------------------------
    @staticmethod
    def _apply_params(url: str, params: Optional[Mapping[str, Any]]) -> str:
        if not params:
            return url
        parsed = urllib.parse.urlparse(url)
        existing = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        merged = {**existing, **{k: str(v) for k, v in params.items()}}
        query = urllib.parse.urlencode(merged)
        rebuilt = parsed._replace(query=query)
        return urllib.parse.urlunparse(rebuilt)

    @staticmethod
    def _encode_json(payload: Any) -> bytes:
        return json.dumps(payload).encode("utf-8")

    @staticmethod
    def _encode_data(data: Any, headers: MutableMapping[str, str]) -> Optional[bytes]:
        if data is None:
            return None
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, Mapping):
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            return urllib.parse.urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
        return str(data).encode("utf-8")


__all__ = ["HTTPSession", "HttpResponse"]
