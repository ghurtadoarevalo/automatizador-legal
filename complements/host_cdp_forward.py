"""
Small TCP forwarder to expose Chrome DevTools (CDP) from localhost to Docker.

Why:
- Chrome DevTools often binds only to 127.0.0.1:9222 on macOS.
- Chrome also rejects requests where the Host header isn't localhost or an IP.
- Docker containers therefore can't reliably use http://host.docker.internal:9222.

Solution:
- Run this script on the host to forward 0.0.0.0:9223 -> 127.0.0.1:9222
- Point the container to http://<HOST_IP>:9223 (HOST header becomes an IP -> allowed)

Usage:
  python host_cdp_forward.py --listen-port 9223 --target-port 9222
"""

from __future__ import annotations

import argparse
import socket
import threading


def _pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass


def _handle(client: socket.socket, target_host: str, target_port: int) -> None:
    target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        target.connect((target_host, target_port))
        threading.Thread(target=_pipe, args=(client, target), daemon=True).start()
        threading.Thread(target=_pipe, args=(target, client), daemon=True).start()
    except Exception:
        try:
            client.close()
        except Exception:
            pass
        try:
            target.close()
        except Exception:
            pass


def run_forwarder(listen_port: int = 9223, target_port: int = 9222, listen_host: str = "0.0.0.0", target_host: str = "127.0.0.1") -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-host", default=listen_host)
    ap.add_argument("--listen-port", type=int, default=listen_port)
    ap.add_argument("--target-host", default=target_host)
    ap.add_argument("--target-port", type=int, default=target_port)
    args = ap.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        # Permite reutilizar el puerto inmediatamente en macOS/BSD
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    server.bind((args.listen_host, args.listen_port))
    server.listen(64)
    print(
        f"Forwarding {args.listen_host}:{args.listen_port} -> {args.target_host}:{args.target_port}",
        flush=True,
    )

    while True:
        client, _addr = server.accept()
        threading.Thread(
            target=_handle,
            args=(client, args.target_host, args.target_port),
            daemon=True,
        ).start()
