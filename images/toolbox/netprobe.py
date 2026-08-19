#!/usr/bin/env python3
"""Small UDP RTT/loss probe used by LOG100 laboratories."""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mesurer le RTT, la variation du délai et la perte avec de petites sondes UDP."
    )
    parser.add_argument("host", help="nom ou adresse de la cible")
    parser.add_argument("--port", type=int, default=7000, help="port UDP (défaut : 7000)")
    parser.add_argument("--count", type=int, default=20, help="nombre de sondes")
    parser.add_argument("--interval", type=float, default=0.1, help="intervalle entre les sondes en secondes")
    parser.add_argument("--timeout", type=float, default=1.0, help="délai maximal d’attente en secondes")
    parser.add_argument("--size", type=int, default=64, help="taille minimale de la charge utile en octets")
    parser.add_argument("--json", action="store_true", help="produire uniquement du JSON")
    return parser.parse_args()


def summarize(sent: int, rtts: list[float]) -> dict[str, float | int | None]:
    received = len(rtts)
    lost = sent - received
    jitter = None
    if len(rtts) >= 2:
        jitter = statistics.fmean(abs(b - a) for a, b in zip(rtts, rtts[1:]))
    return {
        "sent": sent,
        "received": received,
        "lost": lost,
        "loss_percent": (lost / sent * 100.0) if sent else 0.0,
        "rtt_min_ms": min(rtts) if rtts else None,
        "rtt_avg_ms": statistics.fmean(rtts) if rtts else None,
        "rtt_max_ms": max(rtts) if rtts else None,
        "jitter_mean_abs_ms": jitter,
    }


def main() -> None:
    args = parse_args()
    address = socket.getaddrinfo(args.host, args.port, family=socket.AF_INET, type=socket.SOCK_DGRAM)[0][4]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)
    rtts: list[float] = []

    for sequence in range(1, args.count + 1):
        stamp = time.monotonic_ns()
        prefix = f"LOG100 {sequence} {stamp} ".encode("ascii")
        payload = prefix + b"x" * max(0, args.size - len(prefix))
        start = time.monotonic_ns()
        sock.sendto(payload, address)
        try:
            data, _ = sock.recvfrom(max(65535, args.size + 128))
        except socket.timeout:
            if not args.json:
                print(f"sonde {sequence:03d} : délai dépassé")
        else:
            end = time.monotonic_ns()
            if data == payload:
                rtt_ms = (end - start) / 1_000_000.0
                rtts.append(rtt_ms)
                if not args.json:
                    print(f"sonde {sequence:03d} : RTT={rtt_ms:.2f} ms")
        if sequence < args.count:
            time.sleep(args.interval)

    result = summarize(args.count, rtts)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("--- résumé ---")
        print(f"envoyées={result['sent']} reçues={result['received']} perdues={result['lost']} ({result['loss_percent']:.1f} %)")
        if result["rtt_avg_ms"] is not None:
            print(
                "RTT min/moy/max = "
                f"{result['rtt_min_ms']:.2f}/{result['rtt_avg_ms']:.2f}/{result['rtt_max_ms']:.2f} ms"
            )
        if result["jitter_mean_abs_ms"] is not None:
            print(f"variation moyenne entre RTT successifs = {result['jitter_mean_abs_ms']:.2f} ms")


if __name__ == "__main__":
    main()
