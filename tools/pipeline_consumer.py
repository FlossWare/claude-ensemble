#!/usr/bin/env python3
"""Stage 3: GA Consumer — queries numerical sequences via REST API.

Two modes:
  1. Library:  from pipeline_consumer import SequenceStore
     store = SequenceStore("http://aio-01:5000")
     batch = store.get_batch("sourcecode", size=100)

  2. CLI:      python3 pipeline_consumer.py stats
               python3 pipeline_consumer.py channels --type sourcecode --size 50

GA experiments use library mode to pull training sequences via REST API.
Workers never touch PostgreSQL directly.
"""

import argparse
import json
import sys

import requests


class SequenceStore:
    """Query interface for GA experiments — all access via REST API."""

    def __init__(self, api_base="http://aio-01:5000"):
        self.api_base = api_base.rstrip("/")

    def get_batch(self, file_type=None, size=100, min_complexity=None, max_length=None):
        params = {"size": size}
        if file_type:
            params["type"] = file_type
        if min_complexity is not None:
            params["min_complexity"] = min_complexity
        if max_length is not None:
            params["max_length"] = max_length

        resp = requests.get(f"{self.api_base}/sequences/batch", params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result.get("batch", result.get("sequences", []))

    def get_stats(self):
        resp = requests.get(f"{self.api_base}/sequences/stats", timeout=10)
        resp.raise_for_status()
        return resp.json().get("stats", [])

    def get_input_channels(self, file_type=None, size=50, max_length=500):
        """Return sequences formatted for GA input channels (8 channels).

        Maps sequence features to the 8 input channels of SelfAwareContext:
          ch0: line_lengths (normalized to 0-1)
          ch1: indentation_depths (normalized)
          ch2: nesting_patterns (normalized)
          ch3: char_frequencies[a-z] (26 values, cyclically)
          ch4: char_frequencies[0-9+symbols]
          ch5: entropy (repeated)
          ch6: complexity (repeated)
          ch7: avg_line_length (repeated)
        """
        params = {"size": size, "max_length": max_length}
        if file_type:
            params["type"] = file_type

        resp = requests.get(f"{self.api_base}/sequences/channels", params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if "sequences" in result:
            return result["sequences"]

        batch = self.get_batch(file_type, size, max_length=max_length)
        results = []

        for row in batch:
            ll = row.get("line_lengths") or []
            ind = row.get("indentation_depths") or []
            nest = row.get("nesting_patterns") or []
            cf = row.get("char_frequencies") or [0.0] * 256

            max_ll = max(ll) if ll else 1
            max_ind = max(ind) if ind else 1
            max_nest = max(nest) if nest else 1
            if max_ll == 0: max_ll = 1
            if max_ind == 0: max_ind = 1
            if max_nest == 0: max_nest = 1

            seq_len = max(len(ll), len(ind), len(nest), 1)
            channels = []
            for step in range(min(seq_len, max_length)):
                ch = [0.0] * 8
                ch[0] = (ll[step] / max_ll) if step < len(ll) and max_ll > 0 else 0.0
                ch[1] = (ind[step] / max_ind) if step < len(ind) and max_ind > 0 else 0.0
                ch[2] = (nest[step] / max_nest) if step < len(nest) and max_nest > 0 else 0.0
                ch[3] = cf[97 + (step % 26)] if len(cf) > 122 else 0.0
                ch[4] = cf[48 + (step % 10)] if len(cf) > 57 else 0.0
                ch[5] = row.get("entropy", 0) / 8.0
                ch[6] = min(row.get("complexity_score", 0), 1.0)
                ch[7] = min((row.get("avg_line_length", 0)) / 120.0, 1.0)
                channels.append(ch)

            results.append({
                "file_id": row.get("file_id", ""),
                "file_type": row.get("file_type", ""),
                "num_steps": len(channels),
                "channels": channels,
            })

        return results


def main():
    parser = argparse.ArgumentParser(description="Stage 3: GA consumer for numerical sequences (REST API)")
    parser.add_argument("--api-base", default="http://aio-01:5000")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="Print sequence stats")

    ch = sub.add_parser("channels", help="Print channel data for GA")
    ch.add_argument("--type", default=None)
    ch.add_argument("--size", type=int, default=5)
    ch.add_argument("--max-length", type=int, default=100)

    batch = sub.add_parser("batch", help="Print raw batch")
    batch.add_argument("--type", default=None)
    batch.add_argument("--size", type=int, default=10)

    args = parser.parse_args()
    store = SequenceStore(args.api_base)

    if args.cmd == "stats":
        for row in store.get_stats():
            print(f"  {row.get('file_type','?'):15s}: {row.get('count',0):>6} seqs, "
                  f"avg_len={row.get('avg_length','?')}, "
                  f"avg_complexity={row.get('avg_complexity',0):.3f}, "
                  f"avg_entropy={row.get('avg_entropy',0):.2f}")

    elif args.cmd == "channels":
        sequences = store.get_input_channels(args.type, args.size, args.max_length)
        print(f"Got {len(sequences)} sequences")
        for seq in sequences[:3]:
            print(f"  {seq['file_id'][:12]}... type={seq['file_type']} steps={seq['num_steps']}")

    elif args.cmd == "batch":
        rows = store.get_batch(args.type, args.size)
        print(f"Got {len(rows)} sequences")
        for row in rows:
            print(f"  {row.get('file_id','?')[:12]}... type={row.get('file_type','?')} "
                  f"len={row.get('sequence_length',0)} complexity={row.get('complexity_score',0):.3f}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
