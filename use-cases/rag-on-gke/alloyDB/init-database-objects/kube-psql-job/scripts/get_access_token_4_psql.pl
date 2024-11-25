#!/usr/bin/perl
# Copyright 2024 Google LLC
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

use HTTP::Tiny;
use JSON::PP;

$handle=HTTP::Tiny->new(default_headers=>{"Metadata-Flavor" => "Google"});
$url_base="http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/";
$result=$handle->get($url_base."email");
(my $pg_user = $result->{content}) =~ s/\.gserviceaccount.com$//g;
$result=$handle->get($url_base."token");
$token_json=  decode_json $result->{content};
$access_token= $token_json->{access_token};
print "PGUSER=\"$pg_user\"\n";
print "PGPASSWORD=\"$access_token\"\n"
