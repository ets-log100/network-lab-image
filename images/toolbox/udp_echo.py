#!/usr/bin/env python3
"""Minimal UDP echo server for LOG100 experiments."""

import argparse
import socket


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur d’écho UDP minimal pour les laboratoires LOG100.")
    parser.add_argument("--port", type=int, default=7000)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    print(f"Serveur d’écho UDP en écoute sur le port {args.port}", flush=True)
    while True:
        data, addr = sock.recvfrom(65535)
        sock.sendto(data, addr)


if __name__ == "__main__":
    main()
