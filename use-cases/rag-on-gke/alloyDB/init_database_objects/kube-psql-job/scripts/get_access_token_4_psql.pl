#!/usr/bin/perl
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
