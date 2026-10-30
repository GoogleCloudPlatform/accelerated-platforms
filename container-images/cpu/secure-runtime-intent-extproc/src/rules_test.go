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
	"testing"
)

func TestParseActorRef(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{
			in:   "spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-sandbox",
			want: "secure-runtime/triage-sandbox",
		},
		{
			in:   "spiffe://substrate-actor.local/actor/secure-runtime/triage-sandbox",
			want: "secure-runtime/triage-sandbox",
		},
		{
			in:   "secure-runtime/triage-sandbox",
			want: "secure-runtime/triage-sandbox",
		},
	}

	for _, tc := range cases {
		if got := ParseActorRef(tc.in); got != tc.want {
			t.Errorf("ParseActorRef(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

func TestPolicyStoreEvaluate(t *testing.T) {
	store := NewPolicyStore(50)

	// 1. Default deny when no policy is registered.
	allowed, code, _, _ := store.Evaluate(
		"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1",
		"GET",
		"api.github.com",
		"/repos/demo-org/demo-repo/issues/42",
		true,
	)
	if allowed || code != 403 {
		t.Fatalf("expected default-deny 403 before rule registration, got allowed=%v code=%d", allowed, code)
	}

	// 2. Register read-only GitHub triage intent.
	store.SetRule(IntentRule{
		Actor:             "secure-runtime/triage-1",
		Intent:            "github_issue_read_only",
		AllowedHosts:      []string{"api.github.com"},
		AllowedMethods:    []string{"GET", "HEAD"},
		AllowedPathPrefix: []string{"/repos/demo-org/demo-repo/"},
	})

	// 3. GET on allowed repo path succeeds.
	allowed, code, _, intent := store.Evaluate(
		"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1",
		"GET",
		"api.github.com:443",
		"/repos/demo-org/demo-repo/issues/42?state=open",
		true,
	)
	if !allowed || code != 200 || intent != "github_issue_read_only" {
		t.Fatalf("expected GET to be allowed (200), got allowed=%v code=%d intent=%q", allowed, code, intent)
	}

	// 4. POST on the same repo path (e.g. closing an issue or posting a comment) is blocked 403.
	allowed, code, reason, _ := store.Evaluate(
		"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1",
		"POST",
		"api.github.com",
		"/repos/demo-org/demo-repo/issues/42/comments",
		true,
	)
	if allowed || code != 403 {
		t.Fatalf("expected POST to be blocked (403), got allowed=%v code=%d reason=%q", allowed, code, reason)
	}

	// 5. GET on a different repository path is blocked 403.
	allowed, code, _, _ = store.Evaluate(
		"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1",
		"GET",
		"api.github.com",
		"/repos/other-org/other-repo/issues",
		true,
	)
	if allowed || code != 403 {
		t.Fatalf("expected GET on other repo to be blocked (403), got allowed=%v code=%d", allowed, code)
	}

	// 6. Revoking the actor rule immediately restores default-deny.
	store.DeleteRule("secure-runtime/triage-1")
	allowed, code, _, _ = store.Evaluate(
		"spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-1",
		"GET",
		"api.github.com",
		"/repos/demo-org/demo-repo/issues/42",
		true,
	)
	if allowed || code != 403 {
		t.Fatalf("expected 403 after rule deletion, got allowed=%v code=%d", allowed, code)
	}
}
