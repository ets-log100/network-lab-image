#!/usr/bin/env bash
set -euo pipefail

RUNTIME=${CONTAINER_RUNTIME:-podman}
TAG=${TAG:-dev}
PREFIX=${PREFIX:-localhost/log100-net}
SUFFIX="u$(id -u)-$$"
FRONT="log100-image-front-$SUFFIX"
BACK="log100-image-back-$SUFFIX"
WEB="log100-image-web-$SUFFIX"
SERVER="log100-image-server-$SUFFIX"
LINK="log100-image-link-$SUFFIX"
CLIENT="log100-image-client-$SUFFIX"
DNS="log100-image-dns-$SUFFIX"

cleanup() {
    "$RUNTIME" rm -f "$CLIENT" "$LINK" "$SERVER" "$WEB" "$DNS" >/dev/null 2>&1 || true
    "$RUNTIME" network rm -f "$FRONT" "$BACK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$RUNTIME" network create "$FRONT" >/dev/null
"$RUNTIME" network create "$BACK" >/dev/null

"$RUNTIME" run -d --name "$WEB" --network "$BACK" --network-alias web \
    "${PREFIX}-web:${TAG}" >/dev/null
"$RUNTIME" run -d --name "$SERVER" --network "$BACK" --network-alias server \
    "${PREFIX}-toolbox:${TAG}" sh -lc 'iperf3 -s -D; udp-echo --port 7000' >/dev/null
"$RUNTIME" run -d --name "$LINK" \
    --network "$FRONT" --network "$BACK" --network-alias link \
    -e LINK_TCP_MAPS='5201=server:5201,8080=web:8080' \
    -e LINK_UDP_MAPS='7000=server:7000' \
    -e LINK_DELAY_MS=10 \
    -e LINK_JITTER_MS=2 \
    -e LINK_BANDWIDTH_MBIT=20 \
    -e LINK_UDP_LOSS_PERCENT=0 \
    "${PREFIX}-link:${TAG}" >/dev/null
"$RUNTIME" run -d --name "$CLIENT" --network "$FRONT" \
    "${PREFIX}-toolbox:${TAG}" sleep infinity >/dev/null

for _ in $(seq 1 40); do
    if "$RUNTIME" exec "$CLIENT" curl -fsS http://link:8080/healthz >/dev/null 2>&1; then
        break
    fi
    sleep 0.25
done
"$RUNTIME" exec "$CLIENT" curl -fsS http://link:8080/healthz >/dev/null
printf 'Test de fumée HTTP via link : OK\n'

"$RUNTIME" exec "$CLIENT" netprobe link --count 5 --interval 0.02 --timeout 1 --json >/tmp/log100-netprobe.json
python3 - <<'PY'
import json
with open('/tmp/log100-netprobe.json', encoding='utf-8') as f:
    d=json.load(f)
assert d['received'] == 5, d
assert d['rtt_avg_ms'] >= 10, d
PY
printf 'Test de fumée sonde UDP via link : OK\n'

"$RUNTIME" exec "$CLIENT" iperf3 -c link -p 5201 -t 2 -J >/tmp/log100-iperf.json
python3 - <<'PY'
import json
with open('/tmp/log100-iperf.json', encoding='utf-8') as f:
    d=json.load(f)
bps=d['end']['sum_received']['bits_per_second']
assert bps > 1_000_000, bps
assert bps < 35_000_000, bps
PY
printf 'Test de fumée débit TCP via link : OK\n'

# DNS image retains its independent smoke check.
"$RUNTIME" run -d --name "$DNS" --network "$FRONT" --network-alias dns \
    "${PREFIX}-dns:${TAG}" >/dev/null
for _ in $(seq 1 20); do
    result=$("$RUNTIME" exec "$CLIENT" dig +short +time=1 +tries=1 @dns health.log100. A 2>/dev/null || true)
    [[ "$result" == "127.0.0.1" ]] && break
    sleep 0.25
done
result=$("$RUNTIME" exec "$CLIENT" dig +short +time=1 +tries=1 @dns health.log100. A)
[[ "$result" == "127.0.0.1" ]]
printf 'Test de fumée DNS : OK\n'

printf 'Tous les tests de fumée des images ont réussi.\n'
