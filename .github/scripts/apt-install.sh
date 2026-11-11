#!/usr/bin/env bash
# Install apt packages on a hosted runner.
#
# The runner's Ubuntu mirror occasionally stops resolving for minutes
# ("Temporary failure resolving 'archive.ubuntu.com'"), which fails the fetch
# even though the package list is already on the image. Refreshing the indexes
# is therefore best-effort and the install itself is retried, so a transient
# DNS or download failure does not abort the job.
#
# Usage: apt-install.sh PACKAGE [PACKAGE...]
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: apt-install.sh PACKAGE [PACKAGE...]" >&2
    exit 2
fi

packages=("$@")
update() {
    sudo apt-get -o Acquire::Retries=5 -o Acquire::https::Timeout=30 update || true
}

update
for attempt in 1 2 3; do
    if sudo apt-get install -y --no-install-recommends \
        -o Acquire::Retries=5 \
        "${packages[@]}"; then
        exit 0
    fi
    [ "$attempt" -eq 3 ] && break
    sleep $((attempt * 20))
    update
done

echo "::error::apt could not install: ${packages[*]}" >&2
exit 1
