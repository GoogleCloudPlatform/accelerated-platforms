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

"""Pin every PromQL selector and dashboard displayName to one GKE cluster.

Managed Prometheus is per project, so a query without a `cluster` matcher mixes
metrics across clusters in the project. `dashboards.sh` pipes each dashboard JSON
through this script before upload so repository JSON remains cluster-agnostic:

  promql_scope.py dashboard CLUSTER [ATESPACE] < dashboard.json > scoped.json
  promql_scope.py query CLUSTER 'sum(rate(agent_gateway_chat_turns_total[2m]))'
"""

import json
import re
import sys
from typing import Any

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
LABEL_LIST_KEYWORDS = {
    "by",
    "without",
    "on",
    "ignoring",
    "group_left",
    "group_right",
}
IDENT = re.compile(r"[A-Za-z_:][A-Za-z0-9_:]*")
HAS_CLUSTER = re.compile(r'(^|[{,\s])"?cluster"?\s*(=|!=|=~|!~)')


def escape_label_value(value: str) -> str:
    """Escape backslashes, double quotes, and newlines for PromQL literals."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _skip_string(q: str, i: int) -> int:
    """Return index past quoted string at q[i]; raise on unterminated quote."""
    quote = q[i]
    start = i
    i += 1
    while i < len(q):
        if q[i] == "\\" and quote != "`":
            if i + 1 >= len(q):
                raise ValueError(f"unterminated escape in string at index {start}: {q}")
            i += 2
            continue
        if q[i] == quote:
            return i + 1
        i += 1
    raise ValueError(f"unterminated {quote} string at index {start}: {q}")


def _matching(q: str, i: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at q[i], skipping strings."""
    depth = 0
    while i < len(q):
        c = q[i]
        if c == "#":
            nl = q.find("\n", i)
            i = len(q) if nl == -1 else nl + 1
            continue
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


def _selector_has_cluster(body: str) -> bool:
    """Return True if selector body has a top-level `cluster` label matcher."""
    stripped_parts: list[str] = []
    idx = 0
    while idx < len(body):
        if body[idx] in "\"'`":
            idx = _skip_string(body, idx)
        else:
            stripped_parts.append(body[idx])
            idx += 1
    return bool(HAS_CLUSTER.search("".join(stripped_parts)))


def scope(q: str, cluster: str) -> str:
    """Add an escaped `cluster` label matcher to every PromQL selector in q."""
    matcher = f'cluster="{escape_label_value(cluster)}"'
    out: list[str] = []
    i = 0
    while i < len(q):
        c = q[i]
        if c == "#":
            nl = q.find("\n", i)
            end = len(q) if nl == -1 else nl + 1
            out.append(q[i:end])
            i = end
        elif c in "\"'`":
            j = _skip_string(q, i)
            out.append(q[i:j])
            i = j
        elif c == "{":
            j = _matching(q, i, "{", "}")
            body = q[i + 1 : j]
            if _selector_has_cluster(body):
                out.append(q[i : j + 1])
            elif body.strip().rstrip(",").strip():
                cleaned = body.rstrip().rstrip(",").rstrip()
                out.append("{" + cleaned + ", " + matcher + "}")
            else:
                out.append("{" + matcher + "}")
            i = j + 1
        elif c == "[":
            j = _matching(q, i, "[", "]")
            out.append(q[i : j + 1])
            i = j + 1
        elif IDENT.match(q, i) and (
            i == 0 or not (q[i - 1].isalnum() or q[i - 1] in "_.")
        ):
            m = IDENT.match(q, i)
            assert m is not None
            word = m.group(0)
            lower_word = word.lower()
            j = m.end()
            k = j
            while k < len(q) and q[k].isspace():
                k += 1
            nxt = q[k] if k < len(q) else ""
            if lower_word in LABEL_LIST_KEYWORDS and nxt == "(":
                end = _matching(q, k, "(", ")")
                out.append(q[i : end + 1])
                i = end + 1
            elif lower_word == "offset":
                out.append(word)
                i = j
                while i < len(q) and q[i].isspace():
                    out.append(q[i])
                    i += 1
                d = re.match(r"-?[0-9A-Za-z_]+", q[i:])
                if d:
                    out.append(d.group(0))
                    i += d.end()
            elif lower_word in KEYWORDS or nxt in ("(", "{"):
                out.append(word)
                i = j
            else:
                out.append(word + "{" + matcher + "}")
                i = j
        elif c.isdigit() or (c == "." and i + 1 < len(q) and q[i + 1].isdigit()):
            m = re.match(r"[0-9.]+(e[+-]?[0-9]+)?", q[i:], re.IGNORECASE)
            assert m is not None
            out.append(m.group(0))
            i += m.end()
        else:
            out.append(c)
            i += 1
    return "".join(out)


def scope_log_filter(f: str, cluster: str, atespace: str | None = None) -> str:
    """Narrow a Logs Explorer filter to one cluster and optional atespace."""
    escaped_cluster = escape_label_value(cluster)
    updated = f
    if atespace:
        escaped_as = escape_label_value(atespace)
        updated = updated.replace(
            '"ate.atespace"="security-demo"', f'"ate.atespace"="{escaped_as}"'
        )
    if "resource.labels.cluster_name" in updated:
        return updated
    return updated + f'\nresource.labels.cluster_name="{escaped_cluster}"'


def scope_monitoring_filter(f: str, cluster: str) -> str:
    """Pin a Cloud Monitoring timeSeriesFilter string to one GKE cluster."""
    if "resource.labels.cluster" in f or "resource.label.cluster" in f:
        return f
    return f + f' resource.labels.cluster="{escape_label_value(cluster)}"'


def _scope_node(obj: Any, cluster: str, atespace: str | None) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "prometheusQuery" and isinstance(v, str):
                out[k] = scope(v, cluster)
            elif (
                k == "timeSeriesFilter"
                and isinstance(v, dict)
                and isinstance(v.get("filter"), str)
            ):
                out[k] = {
                    **v,
                    "filter": scope_monitoring_filter(v["filter"], cluster),
                }
            elif (
                k == "logsPanel"
                and isinstance(v, dict)
                and isinstance(v.get("filter"), str)
            ):
                out[k] = {
                    **v,
                    "filter": scope_log_filter(v["filter"], cluster, atespace),
                }
            elif (
                k == "title"
                and isinstance(v, str)
                and atespace
                and "security-demo atespace" in v
            ):
                out[k] = v.replace("security-demo atespace", f"{atespace} atespace")
            else:
                out[k] = _scope_node(v, cluster, atespace)
        return out
    if isinstance(obj, list):
        return [_scope_node(v, cluster, atespace) for v in obj]
    return obj


def scope_dashboard(obj: Any, cluster: str, atespace: str | None = None) -> Any:
    """Scope queries, Monitoring/log filters, and displayName to `cluster`."""
    res = _scope_node(obj, cluster, atespace)
    if isinstance(res, dict) and isinstance(res.get("displayName"), str):
        suffix = f" ({cluster})"
        if not res["displayName"].endswith(suffix):
            res["displayName"] = res["displayName"] + suffix
    return res


def main(argv: list[str]) -> None:
    if len(argv) in (3, 4) and argv[1] == "dashboard":
        atespace = argv[3] if len(argv) == 4 else None
        json.dump(
            scope_dashboard(json.load(sys.stdin), argv[2], atespace),
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    elif len(argv) == 4 and argv[1] == "query":
        print(scope(argv[3], argv[2]))
    else:
        sys.exit(
            f"usage: {argv[0]} dashboard CLUSTER [ATESPACE] "
            f"| {argv[0]} query CLUSTER PROMQL"
        )


if __name__ == "__main__":
    main(sys.argv)
