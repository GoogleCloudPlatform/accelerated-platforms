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

import "testing"

func TestParseActorRef(t *testing.T) {
	for _, tc := range []struct{ in, want string }{
		{"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-sandbox", "secure-runtime/triage-sandbox"},
		{"spiffe://substrate-actor.local/actor/secure-runtime/triage-sandbox", "secure-runtime/triage-sandbox"},
		{"secure-runtime/triage-sandbox", "secure-runtime/triage-sandbox"},
	} {
		if got := ParseActorRef(tc.in); got != tc.want {
			t.Errorf("ParseActorRef(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestPolicyStoreEvaluate(t *testing.T) {
	store := NewPolicyStore(50)
	spiffe := "spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1"

	if ok, code, _, _ := store.Evaluate(spiffe, "GET", "api.github.com", "/repos/demo-org/demo-repo/issues/42", true); ok || code != 403 {
		t.Fatalf("expected default-deny 403, got ok=%v code=%d", ok, code)
	}
	store.SetRule(IntentRule{
		Actor:             "secure-runtime/triage-1",
		Intent:            "github_issue_read_only",
		AllowedHosts:      []string{"api.github.com"},
		AllowedMethods:    []string{"GET", "HEAD"},
		AllowedPathPrefix: []string{"/repos/demo-org/demo-repo/"},
	})
	if ok, code, _, intent := store.Evaluate(spiffe, "GET", "api.github.com:443", "/repos/demo-org/demo-repo/issues/42?state=open", true); !ok || code != 200 || intent != "github_issue_read_only" {
		t.Fatalf("expected GET 200, got ok=%v code=%d intent=%q", ok, code, intent)
	}
	if ok, code, _, _ := store.Evaluate(spiffe, "POST", "api.github.com", "/repos/demo-org/demo-repo/issues/42/comments", true); ok || code != 403 {
		t.Fatalf("expected POST 403, got ok=%v code=%d", ok, code)
	}
	if ok, code, _, _ := store.Evaluate(spiffe, "GET", "api.github.com", "/repos/other-org/other-repo/issues", true); ok || code != 403 {
		t.Fatalf("expected other-repo GET 403, got ok=%v code=%d", ok, code)
	}
	for _, traversalPath := range []string{
		"/repos/demo-org/demo-repo/../../victim-org/private-repo/issues/1",
		"/repos/demo-org/demo-repo/%2e%2e/%2e%2e/victim-org/private-repo/issues/1",
		"/repos/demo-org/demo-repo/./issues/42",
		"/repos/demo-org/demo-repo\\..\\victim-org/private-repo",
		"/repos/demo-org/demo-repo-other/issues/1",
		"repos/demo-org/demo-repo/issues/42",
	} {
		if ok, code, _, _ := store.Evaluate(spiffe, "GET", "api.github.com", traversalPath, true); ok || code != 403 {
			t.Fatalf("expected traversal/boundary path %q to be rejected with 403, got ok=%v code=%d", traversalPath, ok, code)
		}
	}
	store.DeleteRule("secure-runtime/triage-1")
	if ok, code, _, _ := store.Evaluate(spiffe, "GET", "api.github.com", "/repos/demo-org/demo-repo/issues/42", true); ok || code != 403 {
		t.Fatalf("expected 403 after delete, got ok=%v code=%d", ok, code)
	}
}
