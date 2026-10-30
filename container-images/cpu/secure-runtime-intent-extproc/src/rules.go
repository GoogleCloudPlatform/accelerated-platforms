// Copyright 2026 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"fmt"
	"net/url"
	"strings"
	"sync"
	"time"
)

// IntentRule defines the L7 HTTP policy registered by the agent harness for a
// specific actor turn (after intent classification in before_tool_callback).
type IntentRule struct {
	Actor              string   `json:"actor"`
	Intent             string   `json:"intent"`
	AllowedHosts       []string `json:"allowed_hosts"`
	AllowedMethods     []string `json:"allowed_methods"`
	AllowedPathPrefix  []string `json:"allowed_path_prefixes"`
	HasAuthHeaderCheck bool     `json:"has_auth_header_check,omitempty"`
	UpdatedAt          string   `json:"updated_at"`
}

// AuditEvent records each L7 egress decision made by intent-extproc.
type AuditEvent struct {
	Timestamp     string `json:"timestamp"`
	ActorIdentity string `json:"ate.actor.identity"`
	ActorRef      string `json:"ate.actor.ref"`
	Intent        string `json:"intent"`
	Method        string `json:"http.method"`
	Authority     string `json:"http.authority"`
	Path          string `json:"http.path"`
	HasAuthHeader bool   `json:"credential_injected"`
	Decision      string `json:"decision"`
	StatusCode    int    `json:"status_code"`
	Reason        string `json:"reason"`
}

// PolicyStore manages dynamic per-actor L7 rules and a bounded ring buffer of
// recent audit decisions.
type PolicyStore struct {
	mu          sync.RWMutex
	rules       map[string]IntentRule
	defaultRule *IntentRule
	events      []AuditEvent
	maxEvents   int
}

func NewPolicyStore(maxEvents int) *PolicyStore {
	if maxEvents <= 0 {
		maxEvents = 200
	}
	return &PolicyStore{
		rules:     make(map[string]IntentRule),
		maxEvents: maxEvents,
	}
}

func (s *PolicyStore) SetRule(rule IntentRule) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rule.Actor = strings.TrimSpace(rule.Actor)
	for i, m := range rule.AllowedMethods {
		rule.AllowedMethods[i] = strings.ToUpper(strings.TrimSpace(m))
	}
	for i, h := range rule.AllowedHosts {
		rule.AllowedHosts[i] = strings.ToLower(strings.TrimSpace(h))
	}
	rule.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	if rule.Actor == "*" || rule.Actor == "default" {
		r := rule
		s.defaultRule = &r
		return
	}
	s.rules[rule.Actor] = rule
}

func (s *PolicyStore) DeleteRule(actor string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	actor = strings.TrimSpace(actor)
	if actor == "*" || actor == "default" {
		s.defaultRule = nil
		return
	}
	delete(s.rules, actor)
}

func (s *PolicyStore) ListRules() map[string]IntentRule {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make(map[string]IntentRule, len(s.rules)+1)
	for k, v := range s.rules {
		out[k] = v
	}
	if s.defaultRule != nil {
		out["*"] = *s.defaultRule
	}
	return out
}

func (s *PolicyStore) RecordAudit(ev AuditEvent) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.events) >= s.maxEvents {
		s.events = s.events[1:]
	}
	s.events = append(s.events, ev)
}

func (s *PolicyStore) ListAuditEvents() []AuditEvent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]AuditEvent, len(s.events))
	copy(out, s.events)
	return out
}

// ParseActorRef extracts "<atespace>/<actor>" from a Substrate SPIFFE ID such as:
//   - spiffe://substrate-actor.local/worker-for-actor/<atespace>/<name>
//   - spiffe://substrate-actor.local/actor/<atespace>/<name>
// If rawIdentity is already "<atespace>/<name>", it returns it as-is.
func ParseActorRef(rawIdentity string) string {
	rawIdentity = strings.TrimSpace(rawIdentity)
	if rawIdentity == "" {
		return ""
	}
	if !strings.HasPrefix(rawIdentity, "spiffe://") {
		return rawIdentity
	}
	u, err := url.Parse(rawIdentity)
	if err != nil {
		return rawIdentity
	}
	segments := strings.Split(strings.TrimPrefix(u.Path, "/"), "/")
	if len(segments) == 3 && (segments[0] == "worker-for-actor" || segments[0] == "actor") {
		return segments[1] + "/" + segments[2]
	}
	return rawIdentity
}

// Evaluate checks whether the given request headers satisfy the active IntentRule
// for the actor. Enforcement is default-deny when no rule is registered for the
// actor (or wildcard default).
func (s *PolicyStore) Evaluate(actorIdentity, method, authority, reqPath string, hasAuthHeader bool) (allowed bool, statusCode int, reason string, intent string) {
	actorRef := ParseActorRef(actorIdentity)
	method = strings.ToUpper(strings.TrimSpace(method))
	host := strings.ToLower(strings.TrimSpace(authority))
	if colon := strings.IndexByte(host, ':'); colon != -1 {
		host = host[:colon]
	}
	cleanPath := reqPath
	if q := strings.IndexByte(cleanPath, '?'); q != -1 {
		cleanPath = cleanPath[:q]
	}

	s.mu.RLock()
	rule, ok := s.rules[actorRef]
	if !ok {
		// Also check by bare actor name if registered without atespace prefix.
		if slash := strings.IndexByte(actorRef, '/'); slash != -1 {
			rule, ok = s.rules[actorRef[slash+1:]]
		}
	}
	if !ok && s.defaultRule != nil {
		rule = *s.defaultRule
		ok = true
	}
	s.mu.RUnlock()

	if !ok {
		return false, 403, fmt.Sprintf("intent-extproc: no active intent policy registered for actor %q (default-deny)", actorRef), "none"
	}

	intent = rule.Intent

	// 1. Check host allowlist (if non-empty).
	if len(rule.AllowedHosts) > 0 {
		hostAllowed := false
		for _, h := range rule.AllowedHosts {
			if h == "*" || h == host {
				hostAllowed = true
				break
			}
		}
		if !hostAllowed {
			return false, 403, fmt.Sprintf("intent-extproc: host %q is not permitted by intent %q (allowed hosts: %v)", host, rule.Intent, rule.AllowedHosts), intent
		}
	}

	// 2. Check HTTP method allowlist.
	methodAllowed := false
	for _, m := range rule.AllowedMethods {
		if m == "*" || m == method {
			methodAllowed = true
			break
		}
	}
	if !methodAllowed {
		return false, 403, fmt.Sprintf("intent-extproc: HTTP method %s to %s%s is blocked by intent %q (allowed methods: %v)", method, host, cleanPath, rule.Intent, rule.AllowedMethods), intent
	}

	// 3. Check URL path prefix allowlist (if non-empty).
	if len(rule.AllowedPathPrefix) > 0 {
		pathAllowed := false
		for _, p := range rule.AllowedPathPrefix {
			if p == "*" || strings.HasPrefix(cleanPath, p) {
				pathAllowed = true
				break
			}
		}
		if !pathAllowed {
			return false, 403, fmt.Sprintf("intent-extproc: path %q on %s is outside the scope of intent %q (allowed prefixes: %v)", cleanPath, host, rule.Intent, rule.AllowedPathPrefix), intent
		}
	}

	return true, 200, fmt.Sprintf("allowed by intent %q", rule.Intent), intent
}
