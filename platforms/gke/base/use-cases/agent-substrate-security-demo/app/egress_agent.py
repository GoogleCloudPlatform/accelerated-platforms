#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Zero-secret HTTP(S) fetch actor (egress-agent-v1) for Act 3 egress demo.

Holds zero credentials inside the sandbox; sends `Authorization: Bearer placeholder`
so the out-of-sandbox `atenet-egress` proxy swaps the real token on the wire for
allowlisted FQDNs while the local DNS relay and `atenet-egress` block unlisted
destinations.
"""

import http.client
import urllib.error
import urllib.parse
import urllib.request
from typing import IO, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse

app = FastAPI()
MAX_FETCH_BYTES = 1_048_576


def validate_fetch_url(url: str) -> str:
    """Allow only clean http:// and https:// URLs with a non-empty hostname."""
    if not url or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        raise ValueError(f"URL contains whitespace or control characters: {url!r}")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"Unsupported URL scheme or missing host: {url!r}")
    return url


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate every HTTP redirect target so 30x cannot switch schemes."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        validate_fetch_url(resolved)
        return super().redirect_request(req, fp, code, msg, headers, resolved)


@app.get("/readyz")
def readyz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


@app.get("/fetch")
def fetch(url: str = Query(...)) -> PlainTextResponse:
    try:
        validated_url = validate_fetch_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    req = urllib.request.Request(
        validated_url,
        headers={
            "Authorization": "Bearer placeholder",
            "User-Agent": "agent-substrate-egress-demo/1.0",
        },
    )
    opener = urllib.request.build_opener(SafeRedirectHandler())
    try:
        with opener.open(req, timeout=10) as resp:
            return PlainTextResponse(
                resp.read(MAX_FETCH_BYTES).decode("utf-8", errors="replace"),
                status_code=resp.status,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except urllib.error.HTTPError as exc:
        err_text = exc.read(MAX_FETCH_BYTES).decode("utf-8", errors="replace")
        return PlainTextResponse(err_text, status_code=exc.code)
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        TimeoutError,
        OSError,
    ) as exc:
        return PlainTextResponse(
            f'fetch: Get "{validated_url}": {exc}\n', status_code=502
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
