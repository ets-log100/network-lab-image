#!/usr/bin/env bash
set -euo pipefail

RUNTIME=${CONTAINER_RUNTIME:-podman}
TAG=${TAG:-dev}
PREFIX=${PREFIX:-localhost/log100-net}
SUFFIX="u$(id -u)-$$"
NETWORK="log100-image-smoke-$SUFFIX"
WEB="log100-image-web-$SUFFIX"
DNS="log100-image-dns-$SUFFIX"
CLIENT="log100-image-client-$SUFFIX"

cleanup() {
    "$RUNTIME" rm -f "$CLIENT" "$WEB" "$DNS" >/dev/null 2>&1 || true
    "$RUNTIME" network rm -f "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$RUNTIME" network create "$NETWORK" >/dev/null

"$RUNTIME" run -d --name "$WEB" --network "$NETWORK" --network-alias web \
    "${PREFIX}-web:${TAG}" >/dev/null
"$RUNTIME" run -d --name "$DNS" --network "$NETWORK" --network-alias dns \
    "${PREFIX}-dns:${TAG}" >/dev/null
"$RUNTIME" run -d --name "$CLIENT" --network "$NETWORK" \
    "${PREFIX}-toolbox:${TAG}" sleep infinity >/dev/null

for _ in $(seq 1 20); do
    if "$RUNTIME" exec "$CLIENT" curl -fsS http://web:8080/healthz >/dev/null 2>&1; then
        break
    fi
    sleep 0.25
done
"$RUNTIME" exec "$CLIENT" curl -fsS http://web:8080/healthz >/dev/null
printf 'Test de fumée HTTP : OK\n'

for _ in $(seq 1 20); do
    result=$("$RUNTIME" exec "$CLIENT" dig +short +time=1 +tries=1 @dns health.log100. A 2>/dev/null || true)
    if [[ "$result" == "127.0.0.1" ]]; then
        break
    fi
    sleep 0.25
done
result=$("$RUNTIME" exec "$CLIENT" dig +short +time=1 +tries=1 @dns health.log100. A)
[[ "$result" == "127.0.0.1" ]]
printf 'Test de fumée DNS : OK\n'

printf 'Tous les tests de fumée des images ont réussi.\n'
