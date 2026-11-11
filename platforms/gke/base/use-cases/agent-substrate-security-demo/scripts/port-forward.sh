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

# Shared PID- and context-verified kubectl port-forward helpers (never uses pkill).

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

pf_cmdline() {
  local pid="$1" cmd=""
  if [[ -r "/proc/${pid}/cmdline" ]]; then
    cmd="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  fi
  if [[ -z "${cmd}" ]]; then
    cmd="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
  fi
  printf '%s' "${cmd}"
}

stop_single_managed_pf() {
  local pidfile="$1"
  if [[ -f "${pidfile}" ]]; then
    local pid cmdline
    pid="$(tr -cd '0-9' < "${pidfile}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      cmdline="$(pf_cmdline "${pid}")"
      if [[ -n "${cmdline}" && "${cmdline}" == *"kubectl"*"port-forward"* ]]; then
        kill "${pid}" 2>/dev/null || true
        local tick
        for tick in {1..20}; do
          kill -0 "${pid}" 2>/dev/null || break
          sleep 0.1
        done
        if kill -0 "${pid}" 2>/dev/null; then
          kill -9 "${pid}" 2>/dev/null || true
        fi
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
  mkdir -m 0700 -p "${state_dir}"
  chmod 0700 "${state_dir}"
  local pidfile="${state_dir}/pf-${name}.pid"
  local ctx
  ctx="$(kubectl config current-context 2>/dev/null || true)"

  if [[ -f "${pidfile}" ]]; then
    local existing_pid existing_cmd
    existing_pid="$(tr -cd '0-9' < "${pidfile}")"
    if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
      existing_cmd="$(pf_cmdline "${existing_pid}")"
      if [[ "${existing_cmd}" == *"kubectl"*"port-forward"* \
         && "${existing_cmd}" == *"-n ${ns}"* \
         && "${existing_cmd}" == *"${lport}:${rport}"* \
         && ( -z "${ctx}" || "${existing_cmd}" == *"--context ${ctx}"* ) ]] \
         && probe_matches "${lport}" "${probe_path}" "${expected}"; then
        return 0
      fi
    fi
  fi

  stop_single_managed_pf "${pidfile}"
  if port_is_listening "${lport}"; then
    sleep 0.3
    if port_is_listening "${lport}"; then
      if probe_matches "${lport}" "${probe_path}" "${expected}" && [[ -n "${expected}" ]]; then
        return 0
      fi
      echo "Error: local port 127.0.0.1:${lport} is already occupied by an unrelated listener." >&2
      echo "Set GATEWAY_LOCAL_PORT or PROM_LOCAL_PORT to an unused local port and retry." >&2
      return 1
    fi
  fi

  local ctx_args=()
  if [[ -n "${ctx}" ]]; then
    ctx_args=(--context "${ctx}")
  fi
  kubectl ${ctx_args[@]+"${ctx_args[@]}"} -n "${ns}" port-forward --address 127.0.0.1 "${target}" "${lport}:${rport}" \
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
