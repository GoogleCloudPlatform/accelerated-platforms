#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Shared PID-tracked kubectl port-forward helpers (never uses `pkill -f`).

port_is_listening() {
  local lport="$1"
  python3 - "$lport" <<'EOF'
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.35)
try:
    s.connect(("127.0.0.1", int(sys.argv[1])))
    sys.exit(0)
except OSError:
    sys.exit(1)
finally:
    s.close()
EOF
}

probe_matches() {
  local lport="$1" probe_path="$2" expected="${3:-}"
  local out
  out="$(curl -fsS --max-time 2 "http://127.0.0.1:${lport}${probe_path}" 2>/dev/null)" || return 1
  if [[ -n "${expected}" && "${out}" != *"${expected}"* ]]; then
    return 1
  fi
  return 0
}

stop_single_managed_pf() {
  local pidfile="$1"
  if [[ -f "${pidfile}" ]]; then
    local pid cmdline=""
    pid="$(tr -cd '0-9' < "${pidfile}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      if [[ -r "/proc/${pid}/cmdline" ]]; then
        cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
      fi
      if [[ -z "${cmdline}" || "${cmdline}" == *"port-forward"* ]]; then
        kill "${pid}" 2>/dev/null || true
        wait "${pid}" 2>/dev/null || true
      fi
    fi
    rm -f "${pidfile}"
  fi
}

stop_managed_port_forwards() {
  local state_dir="$1"
  [[ -d "${state_dir}" ]] || return 0
  local pidfile
  for pidfile in "${state_dir}"/pf-*.pid; do
    [[ -e "${pidfile}" ]] || continue
    stop_single_managed_pf "${pidfile}"
  done
}

ensure_managed_port_forward() {
  local state_dir="$1" name="$2" ns="$3" target="$4" lport="$5" rport="$6" probe_path="$7" expected="${8:-}"
  mkdir -p "${state_dir}"
  local pidfile="${state_dir}/pf-${name}.pid"

  if probe_matches "${lport}" "${probe_path}" "${expected}"; then
    return 0
  fi

  if port_is_listening "${lport}"; then
    stop_single_managed_pf "${pidfile}"
    sleep 0.3
    if port_is_listening "${lport}" && ! probe_matches "${lport}" "${probe_path}" "${expected}"; then
      echo "Error: local port 127.0.0.1:${lport} is already occupied by an unrelated listener." >&2
      echo "Set GATEWAY_LOCAL_PORT or PROM_LOCAL_PORT to an unused local port and retry." >&2
      return 1
    fi
  else
    stop_single_managed_pf "${pidfile}"
  fi

  kubectl -n "${ns}" port-forward --address 127.0.0.1 "${target}" "${lport}:${rport}" \
    >"${state_dir}/pf-${name}.log" 2>&1 &
  local new_pid=$!
  echo "${new_pid}" > "${pidfile}"

  local i
  for i in {1..30}; do
    if ! kill -0 "${new_pid}" 2>/dev/null; then
      break
    fi
    if probe_matches "${lport}" "${probe_path}" "${expected}"; then
      return 0
    fi
    sleep 0.5
  done

  echo "Error: kubectl port-forward (${ns}/${target} -> 127.0.0.1:${lport}) failed readiness check on ${probe_path}." >&2
  if [[ -f "${state_dir}/pf-${name}.log" ]]; then
    tail -n 10 "${state_dir}/pf-${name}.log" >&2 || true
  fi
  stop_single_managed_pf "${pidfile}"
  return 1
}
