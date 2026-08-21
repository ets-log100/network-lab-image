#!/usr/bin/env bash
set -euo pipefail

RUNTIME=${CONTAINER_RUNTIME:-podman}
TAG=${TAG:-dev}
PREFIX=${PREFIX:-localhost/log100-net}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

for image in toolbox web dns link router; do
    printf 'Construction de %s-%s:%s\n' "$PREFIX" "$image" "$TAG"
    "$RUNTIME" build \
        --tag "${PREFIX}-${image}:${TAG}" \
        "$ROOT/images/$image"
done
