"""Measure total server-side performance against a running, warmed service."""
from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/v1/remove-background")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--token", default="")
    args = parser.parse_args()
    if not args.file.exists() or args.requests < 1 or args.concurrency < 1:
        parser.error("Provide an existing --file and positive request counts")
    payload = args.file.read_bytes()
    headers = {"X-API-Key": args.token} if args.token else {}

    def call(_: int) -> float:
        with httpx.Client(timeout=180) as client:
            start = time.perf_counter()
            response = client.post(args.url, files={"file": (args.file.name, payload, "image/png")}, headers=headers)
            response.raise_for_status()
            return (time.perf_counter() - start) * 1000

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        values = sorted(executor.map(call, range(args.requests)))
    p95 = values[max(0, int((len(values) - 1) * .95))]
    print({"count": len(values), "concurrency": args.concurrency,
           "mean_ms": round(statistics.mean(values), 2),
           "p50_ms": round(statistics.median(values), 2),
           "p95_ms": round(p95, 2), "max_ms": round(max(values), 2)})


if __name__ == "__main__":
    main()
