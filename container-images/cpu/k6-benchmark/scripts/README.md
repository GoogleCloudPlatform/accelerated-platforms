# k6 Benchmark scripts

This directory contains [k6](https://k6.io/) scripts used to benchmark Machine
Learning inference workloads.

These scripts are packaged into the `k6-benchmark` container image and copied to
`/app/scripts/`.

## Adding new scripts

To add a new benchmark:

1. Place your new k6 script (with `.js` extension) in this directory.
1. Update this README.md to document the new script and its configuration (e.g.,
   expected environment variables, payload format).
1. The script will be automatically included in the container image when it is
   rebuilt.
