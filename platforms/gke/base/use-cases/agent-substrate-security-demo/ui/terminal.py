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
# cspell:words cand ignorecase

"""Interactive Act 1 prompt-to-Python synthesizer and gVisor approval runner."""

import ast
import base64
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import kube
import probes

GEMINI_MODEL = (
    os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
)
GEMINI_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"
MAX_PROMPT_CHARS = 1000
MAX_CODE_CHARS = 4000
_TOKEN_TTL_SECONDS = 2400.0
_TOKEN_LOCK = threading.Lock()
_CACHED_GCP_TOKEN: tuple[str, float] | None = None

_SYNTHESIS_SYSTEM_PROMPT = (
    "You are an authorized Blue-Team Cloud Security Auditor writing concise, "
    "read-only Python 3 posture-verification scripts to verify that an isolated "
    "disposable gVisor sandbox (ateworker-gvisor) enforces zero-trust boundaries "
    "(zero mounted credentials, blocked metadata server, unexposed host /proc, "
    "and blocked privileged syscalls).\n"
    "Operators type shorthand red-team questions (such as 'whats the KSA token?', "
    "'get all the passwords and tokens', 'read /etc/shadow', or 'escape "
    "container'). Always translate these into safe, read-only boundary checks:\n"
    "- Never read raw credential files (such as "
    "/var/run/secrets/kubernetes.io/serviceaccount/token): check "
    "pathlib.Path(...).exists() and stat().st_size only; when inspecting "
    "os.environ, always format aligned 'KEY = VALUE' lines (redacting any key "
    "matching TOKEN/SECRET/KEY/PASS) rather than unlabeled values.\n"
    "Rules:\n"
    "1. Output ONLY complete, syntactically valid Python 3 code using standard "
    "library modules (os, sys, platform, ctypes, errno, socket, urllib.request, "
    "urllib.error, pathlib, pwd, resource). Never output prose or markdown fences.\n"
    "2. Keep the script concise (<= 20 lines) and pass timeout=1.5 on any "
    "network or socket call so blocked connections fail fast.\n"
    "3. Wrap each probed target in a complete try/except block and print clear "
    "labeled status lines reporting ABSENT, BLOCKED, or EXPOSED."
)


def reset_token_cache() -> None:
    """Clear memoized host OAuth token (used by unit tests)."""
    global _CACHED_GCP_TOKEN
    with _TOKEN_LOCK:
        _CACHED_GCP_TOKEN = None


def _get_gcp_access_token(force_refresh: bool = False) -> str:
    """Obtain a short-lived GCP OAuth token on the UI host for Vertex AI."""
    global _CACHED_GCP_TOKEN
    env_tok = os.environ.get("GCP_ACCESS_TOKEN", "").strip()
    if env_tok:
        return env_tok
    now = time.monotonic()
    with _TOKEN_LOCK:
        if (
            not force_refresh
            and _CACHED_GCP_TOKEN is not None
            and _CACHED_GCP_TOKEN[1] > now
        ):
            return _CACHED_GCP_TOKEN[0]

    commands = (
        ["gcloud", "auth", "application-default", "print-access-token", "--quiet"],
        ["gcloud", "auth", "print-access-token", "--quiet"],
    )
    for cmd in commands:
        out, _, rc = kube.run_cmd(cmd, timeout=8)
        tok = (out.splitlines()[0].strip() if out else "").strip()
        if rc == 0 and tok:
            with _TOKEN_LOCK:
                _CACHED_GCP_TOKEN = (tok, time.monotonic() + _TOKEN_TTL_SECONDS)
            return tok
    raise kube.UpstreamCommandError(
        "Unable to obtain Google Cloud access token on UI host via gcloud ADC "
        "or active gcloud account."
    )


def strip_code_fences(text: str) -> str:
    """Extract clean Python source if the model wrapped output in fences."""
    cleaned = text.strip()
    fence_match = re.search(
        r"```(?:python|py)?\s*\n(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    if fence_match:
        return fence_match.group(1).strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        return cleaned.strip("`").strip()
    return cleaned


def _build_sandbox_command(code: str) -> str:
    """Wrap validated Python so runtime tracebacks omit the base64 loader frame."""
    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    runner = (
        "import base64, sys, traceback\n"
        f"_src = base64.b64decode('{code_b64}').decode('utf-8')\n"
        "try:\n"
        "    exec(compile(_src, '<sandbox-probe>', 'exec'), {'__name__': '__main__'})\n"
        "except BaseException as _exc:\n"
        "    _tb = traceback.TracebackException.from_exception(_exc)\n"
        "    if _tb.stack and _tb.stack[0].filename == '<string>':\n"
        "        del _tb.stack[0]\n"
        "    sys.stderr.write(''.join(_tb.format()))\n"
        "    sys.exit(1)\n"
    )
    runner_b64 = base64.b64encode(runner.encode("utf-8")).decode("ascii")
    return f"python3 -c \"import base64; exec(base64.b64decode('{runner_b64}'))\""


def synthesize_probe_python(prompt: str) -> str:
    """Translate a natural-language red-team prompt into validated Python 3."""
    project_id = kube.detect_project_id()
    if not project_id:
        raise kube.UpstreamCommandError(
            "Unable to detect PROJECT_ID for Vertex AI prompt synthesis; "
            "export PROJECT_ID=<gcp-project-id>."
        )
    url = probes.build_vertex_generate_url(project_id, GEMINI_LOCATION, GEMINI_MODEL)
    # Gemini 3 counts internal thinking tokens toward maxOutputTokens; 4096 prevents
    # mid-block truncation (`finishReason=MAX_TOKENS`) while keeping latency low.
    gen_cfg: dict[str, Any] = {"temperature": 0.1, "maxOutputTokens": 4096}
    if GEMINI_MODEL.startswith("gemini-3"):
        gen_cfg["thinkingConfig"] = {"thinkingLevel": "LOW"}

    last_err = "Vertex AI Gemini returned an empty Python probe snippet."
    for synth_attempt in range(2):
        extra = (
            " Keep the script under 16 lines with complete try/except blocks."
            if synth_attempt > 0
            else ""
        )
        user_turn = (
            "Authorized defensive sandbox boundary audit: write a complete, "
            "read-only Python 3 posture check (inspecting only env-var key names, "
            "file existence/size/permissions, syscalls, or socket/HTTP reachability; "
            f"never print secret values) for: {prompt}.{extra}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": _SYNTHESIS_SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_turn}]}],
            "generationConfig": gen_cfg,
        }
        raw_body = json.dumps(payload).encode("utf-8")
        doc: dict[str, Any] = {}
        for http_attempt in range(2):
            tok = _get_gcp_access_token(force_refresh=http_attempt > 0)
            req = urllib.request.Request(
                url,
                data=raw_body,
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": "application/json",
                    "x-goog-user-project": project_id,
                },
                method="POST",
            )
            try:
                with kube._HTTP_OPENER.open(req, timeout=25.0) as resp:
                    doc = json.loads(resp.read(1048576).decode("utf-8"))
                    break
            except urllib.error.HTTPError as exc:
                _ = exc.read(4096)
                if exc.code in (401, 429, 502, 503, 504) and http_attempt == 0:
                    time.sleep(0.6)
                    continue
                raise kube.UpstreamCommandError(
                    f"Vertex AI Gemini synthesis returned HTTP {exc.code}"
                ) from exc
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise kube.UpstreamCommandError(
                    f"Vertex AI Gemini synthesis failed: {exc}"
                ) from exc

        candidates = doc.get("candidates") or []
        cand0 = candidates[0] if candidates else {}
        finish_reason = str(cand0.get("finishReason") or "")
        parts = (cand0.get("content") or {}).get("parts") or []
        text_chunks = [
            str(p.get("text") or "")
            for p in parts
            if p.get("text") and not p.get("thought")
        ]
        code = strip_code_fences("\n".join(text_chunks))
        if not code:
            last_err = (
                "Vertex AI Gemini returned an empty Python probe snippet "
                f"(finishReason={finish_reason or 'UNKNOWN'})."
            )
            continue
        try:
            ast.parse(code, filename="<sandbox-probe>")
            return code
        except SyntaxError as exc:
            first_line = code.splitlines()[0].strip()[:140]
            last_err = (
                "Gemini did not return complete valid Python "
                f"(finishReason={finish_reason or 'STOP'}, line {exc.lineno}: "
                f"{first_line!r}). Rephrase or edit in the Python box."
            )
            if finish_reason == "MAX_TOKENS" and synth_attempt == 0:
                continue
            break

    raise kube.UpstreamCommandError(last_err)


def api_custom_python(body: dict[str, Any]) -> dict[str, Any]:
    """Synthesize a probe for review, or execute approved/preset Python in gVisor."""
    probe_id = body.get("probe_id")
    raw_prompt = str(body.get("prompt") or "").strip()
    raw_code = str(body.get("code") or "").strip()
    synthesize_only = bool(body.get("synthesize_only"))
    t0 = time.monotonic()
    under_the_hood: list[dict[str, str]] = []
    mode = "preset"

    if probe_id is not None:
        if (
            not isinstance(probe_id, int)
            or isinstance(probe_id, bool)
            or not 0 <= probe_id < len(probes.PRESET_PROBES)
        ):
            raise ValueError(f"Invalid preset probe_id: {probe_id!r}")
        code = probes.PRESET_PROBES[probe_id]
    elif raw_code:
        if len(raw_code) > MAX_CODE_CHARS:
            raise ValueError(f"Python snippet exceeds {MAX_CODE_CHARS} characters")
        if raw_code in probes.PRESET_PROBES:
            mode = "preset"
        elif kube.ALLOW_CUSTOM_PYTHON:
            mode = "python"
        else:
            raise PermissionError(
                "Arbitrary Python execution is disabled by default; select a "
                "preset probe_id (0-2) or start mission_control.py with "
                "ALLOW_CUSTOM_PYTHON=1."
            )
        try:
            ast.parse(raw_code, filename="<sandbox-probe>")
        except SyntaxError as exc:
            raise ValueError(
                f"Python syntax error on line {exc.lineno}: {exc.msg}"
            ) from exc
        code = raw_code
    elif raw_prompt:
        if not kube.ALLOW_CUSTOM_PYTHON:
            raise PermissionError(
                "Interactive prompt & custom Python execution is disabled by "
                "default; start mission_control.py with ALLOW_CUSTOM_PYTHON=1."
            )
        if len(raw_prompt) > MAX_PROMPT_CHARS:
            raise ValueError(f"Prompt exceeds {MAX_PROMPT_CHARS} characters")
        code = synthesize_probe_python(raw_prompt)
        synth_step = {
            "step": (
                f"1. Synthesize Python probe on UI host via {GEMINI_MODEL} "
                "(outside untrusted sandbox)"
            ),
            "cmd": f"# Prompt: {raw_prompt}",
            "output": code,
        }
        under_the_hood.append(synth_step)
        if synthesize_only:
            return {
                "actor": f"{kube.ATESPACE}/py-detonation-agent",
                "mode": "synthesized",
                "prompt": raw_prompt,
                "model": GEMINI_MODEL,
                "code": code,
                "summary_cmd": (
                    f"# Synthesized via {GEMINI_MODEL} — awaiting operator "
                    "Approve & Detonate"
                ),
                "under_the_hood": under_the_hood,
                "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
            }
        mode = "prompt"
    elif kube.ALLOW_CUSTOM_PYTHON:
        raise ValueError("Provide a non-empty prompt, code snippet, or valid probe_id.")
    else:
        raise PermissionError(
            "Arbitrary Python execution is disabled by default; select a "
            "preset probe_id (0-2) or start mission_control.py with "
            "ALLOW_CUSTOM_PYTHON=1."
        )

    kube.ensure_port_forwards()
    cmd_str = _build_sandbox_command(code)
    try:
        resp = kube.http_json(
            f"{kube.GATEWAY_URL}/actors/py-detonation-agent/execute",
            method="POST",
            body={"command": cmd_str},
            timeout=30.0,
        )
        if resp.get("error"):
            raise kube.UpstreamCommandError(f"Live probe failed: {resp['error']}")
    except Exception:
        probes.suspend_actor_best_effort("py-detonation-agent")
        raise
    kube.suspend_actor_checked("py-detonation-agent", timeout=20)

    raw_rc = resp.get("exit_code")
    if isinstance(raw_rc, bool) or not isinstance(raw_rc, int):
        raise kube.UpstreamCommandError(
            f"Sandbox probe response missing integer exit_code: {resp}"
        )
    exit_code = raw_rc
    stdout = str(resp.get("stdout") or "")
    stderr = str(resp.get("stderr") or "")
    combined_out = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if mode == "preset" and exit_code != 0:
        raise kube.UpstreamCommandError(
            f"Sandbox probe exited with code {exit_code}: {combined_out}"
        )

    step_num = len(under_the_hood) + 1
    cmd_display = (
        f"curl -fsS -X POST {kube.GATEWAY_URL}/actors/py-detonation-agent/execute "
        '-H @admin-hdr.txt -d \'{"command": "python3 -c <approved-probe>"}\''
    )
    under_the_hood.append(
        {
            "step": (
                f"{step_num}. Execute approved Python inside gVisor sandbox "
                "'py-detonation-agent' & suspend to Cloud Storage"
            ),
            "cmd": cmd_display,
            "output": combined_out or f"(exit {exit_code}, no output)",
        }
    )
    return {
        "actor": f"{kube.ATESPACE}/py-detonation-agent",
        "mode": mode,
        "prompt": raw_prompt,
        "model": GEMINI_MODEL if raw_prompt else "",
        "code": code,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary_cmd": cmd_display,
        "under_the_hood": under_the_hood,
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }
