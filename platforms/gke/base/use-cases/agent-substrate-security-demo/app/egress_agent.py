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

"""Zero-secret HTTP fetch actor (egress-agent-v1) for Act 3 egress demo.

Holds zero credentials inside the sandbox; sends `Authorization: Bearer placeholder`
so the out-of-sandbox `atenet-egress` proxy swaps the real token on the wire for
allowlisted FQDNs (`httpbin.org`) while the local DNS relay blocks unlisted domains.
"""

import urllib.request

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse

app = FastAPI()


@app.get("/readyz")
def readyz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


@app.get("/fetch")
def fetch(url: str = Query(...)) -> PlainTextResponse:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer placeholder",
                "User-Agent": "agent-substrate-egress-demo/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return PlainTextResponse(
                resp.read().decode("utf-8", errors="replace"),
                status_code=resp.status,
            )
    except Exception as exc:
        return PlainTextResponse(f'fetch: Get "{url}": {exc}\n', status_code=502)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
