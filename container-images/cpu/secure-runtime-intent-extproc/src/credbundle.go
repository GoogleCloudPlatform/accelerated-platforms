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
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
	"sync"
)

type certCache struct {
	path string
	mu   sync.Mutex
	fi   os.FileInfo
	cert *tls.Certificate
}

func newCertLoader(path string) func(*tls.ClientHelloInfo) (*tls.Certificate, error) {
	c := &certCache{path: path}
	return func(_ *tls.ClientHelloInfo) (*tls.Certificate, error) {
		return c.get()
	}
}

func (c *certCache) get() (*tls.Certificate, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	fi, err := os.Stat(c.path)
	if err != nil {
		return nil, fmt.Errorf("stat credential bundle %q: %w", c.path, err)
	}
	if c.cert != nil && os.SameFile(c.fi, fi) && fi.ModTime().Equal(c.fi.ModTime()) && fi.Size() == c.fi.Size() {
		return c.cert, nil
	}
	cert, err := tls.LoadX509KeyPair(c.path, c.path)
	if err != nil {
		return nil, fmt.Errorf("load credential bundle %q: %w", c.path, err)
	}
	c.fi, c.cert = fi, &cert
	return c.cert, nil
}

type poolCache struct {
	path string
	mu   sync.Mutex
	fi   os.FileInfo
	pool *x509.CertPool
}

func newPoolLoader(path string) func() (*x509.CertPool, error) {
	c := &poolCache{path: path}
	return c.get
}

func (c *poolCache) get() (*x509.CertPool, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	fi, err := os.Stat(c.path)
	if err != nil {
		return nil, fmt.Errorf("stat trust bundle %q: %w", c.path, err)
	}
	if c.pool != nil && os.SameFile(c.fi, fi) && fi.ModTime().Equal(c.fi.ModTime()) && fi.Size() == c.fi.Size() {
		return c.pool, nil
	}
	pemBytes, err := os.ReadFile(c.path)
	if err != nil {
		return nil, fmt.Errorf("read trust bundle %q: %w", c.path, err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(pemBytes) {
		return nil, fmt.Errorf("trust bundle %q contains no valid certificates", c.path)
	}
	c.fi, c.pool = fi, pool
	return pool, nil
}
