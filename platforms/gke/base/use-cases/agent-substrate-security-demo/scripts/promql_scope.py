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

"""Pin every PromQL selector to one cluster.

Managed Prometheus is per project, so a query without a `cluster` matcher mixes every cluster that reports
into the project (an instructor's second cluster, a shared workshop project). dashboards.sh runs each
dashboard through this before upload, so the repo's JSON stays cluster-agnostic.

  promql_scope.py dashboard CLUSTER < dashboard.json > scoped.json   # every "prometheusQuery" and logsPanel filter
  promql_scope.py query CLUSTER 'sum(rate(workshop_chat_turns_total[2m]))'

Handles the PromQL the workshop and substrate dashboards use: UTF-8 quoted selectors ({"a.b", "l"="v"}),
classic selectors (name{l="v"}), bare metric names, range/subquery brackets, and label lists after
by/without/on/ignoring/group_left/group_right. A selector that already matches on `cluster` is left alone.
"""

import json
import re
import sys
from typing import Any

# Aggregation operators can be followed by `by (…)` instead of `(`, so they're never metric names here.
KEYWORDS = {
    "by",
    "without",
    "on",
    "ignoring",
    "group_left",
    "group_right",
    "offset",
    "bool",
    "and",
    "or",
    "unless",
    "atan2",
    "inf",
    "nan",
    "sum",
    "min",
    "max",
    "avg",
    "count",
    "stddev",
    "stdvar",
    "topk",
    "bottomk",
    "quantile",
    "count_values",
    "group",
    "limitk",
    "limit_ratio",
}
LABEL_LIST_KEYWORDS = {"by", "without", "on", "ignoring", "group_left", "group_right"}
IDENT = re.compile(r"[A-Za-z_:][A-Za-z0-9_:]*")
HAS_CLUSTER = re.compile(r'(^|[{,\s])"?cluster"?\s*(=|!=|=~|!~)')


def _skip_string(q: str, i: int) -> int:
    """Index just past the quoted string starting at q[i]."""
    quote = q[i]
    i += 1
    while i < len(q) and q[i] != quote:
        i += 2 if q[i] == "\\" else 1
    return i + 1


def _matching(q: str, i: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at q[i], skipping strings."""
    depth = 0
    while i < len(q):
        c = q[i]
        if c in "\"'`":
            i = _skip_string(q, i)
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unbalanced {open_ch}{close_ch} in: {q}")


def scope(q: str, cluster: str) -> str:
    """Adds a cluster label matcher to every PromQL selector in q."""
    matcher = f'cluster="{cluster}"'
    out: list[str] = []
    i = 0
    while i < len(q):
        c = q[i]
        if c in "\"'`":
            j = _skip_string(q, i)
            out.append(q[i:j])
            i = j
        elif c == "{":
            j = _matching(q, i, "{", "}")
            body = q[i + 1 : j]
            if HAS_CLUSTER.search(body):
                out.append(q[i : j + 1])
            elif body.strip():
                out.append("{" + body.rstrip() + ", " + matcher + "}")
            else:
                out.append("{" + matcher + "}")
            i = j + 1
        elif c == "[":
            j = _matching(q, i, "[", "]")
            # A subquery's inner expression lives before the ':'; only durations follow it.
            out.append(q[i : j + 1])
            i = j + 1
        elif IDENT.match(q, i) and (
            i == 0 or not (q[i - 1].isalnum() or q[i - 1] in "_.")
        ):
            m = IDENT.match(q, i)
            assert m is not None
            word = m.group(0)
            j = m.end()
            k = j
            while k < len(q) and q[k].isspace():
                k += 1
            nxt = q[k] if k < len(q) else ""
            if word in LABEL_LIST_KEYWORDS and nxt == "(":
                end = _matching(q, k, "(", ")")
                out.append(q[i : end + 1])
                i = end + 1
            elif word == "offset":
                out.append(word)
                i = j
                # the duration after offset is not a metric name
                while i < len(q) and q[i].isspace():
                    out.append(q[i])
                    i += 1
                d = re.match(r"-?[0-9A-Za-z_]+", q[i:])
                if d:
                    out.append(d.group(0))
                    i += d.end()
            elif word.lower() in KEYWORDS or nxt == "(" or nxt == "{":
                out.append(
                    word
                )  # function, keyword, or a name whose {…} the brace branch scopes
                i = j
            else:
                out.append(word + "{" + matcher + "}")
                i = j
        elif c.isdigit() or (c == "." and i + 1 < len(q) and q[i + 1].isdigit()):
            m = re.match(r"[0-9.]+(e[+-]?[0-9]+)?", q[i:], re.I)
            assert m is not None
            out.append(m.group(0))
            i += m.end()
        else:
            out.append(c)
            i += 1
    return "".join(out)


def scope_log_filter(f: str, cluster: str) -> str:
    """A Logs Explorer filter narrowed to one cluster (lines are ANDed)."""
    if "resource.labels.cluster_name" in f:
        return f
    return f + f'\nresource.labels.cluster_name="{cluster}"'


def scope_dashboard(obj: Any, cluster: str) -> Any:
    """Recursively scopes all prometheusQuery and logsPanel filters in a dashboard dict."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "prometheusQuery" and isinstance(v, str):
                out[k] = scope(v, cluster)
            elif (
                k == "logsPanel"
                and isinstance(v, dict)
                and isinstance(v.get("filter"), str)
            ):
                out[k] = {**v, "filter": scope_log_filter(v["filter"], cluster)}
            else:
                out[k] = scope_dashboard(v, cluster)
        return out
    if isinstance(obj, list):
        return [scope_dashboard(v, cluster) for v in obj]
    return obj


def main(argv: list[str]) -> None:
    if len(argv) >= 3 and argv[1] == "dashboard":
        json.dump(scope_dashboard(json.load(sys.stdin), argv[2]), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif len(argv) == 4 and argv[1] == "query":
        print(scope(argv[3], argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
