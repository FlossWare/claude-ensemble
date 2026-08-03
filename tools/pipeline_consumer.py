#!/usr/bin/env python3
"""Stage 3: GA Consumer — queries PostgreSQL for batches of numerical sequences.

Two modes:
  1. REST server:  python3 pipeline_consumer.py serve --port 5001
     GET /sequences/batch?type=sourcecode&size=100&min_complexity=0.3
     GET /sequences/stats
     GET /sequences/random?size=50&max_length=500

  2. Library:      from pipeline_consumer import SequenceStore
     store = SequenceStore("aio-01", 5433)
     batch = store.get_batch("sourcecode", size=100)

GA experiments use mode 2 to pull training sequences directly.
"""

import argparse
import json
import sys

import psycopg2
import psycopg2.extras


class SequenceStore:
    """Query interface for GA experiments to pull numerical sequences."""

    def __init__(self, host="aio-01", port=5433, dbname="learning", user="sfloess"):
        self.conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user)
        self.conn.set_session(readonly=True, autocommit=True)

    def get_batch(self, file_type=None, size=100, min_complexity=None,
                  max_length=None, randomize=True):
        conditions = []
        params = []

        if file_type:
            conditions.append("file_type = %s")
            params.append(file_type)
        if min_complexity is not None:
            conditions.append("complexity_score >= %s")
            params.append(min_complexity)
        if max_length is not None:
            conditions.append("sequence_length <= %s")
            params.append(max_length)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        order = "ORDER BY random()" if randomize else "ORDER BY id"

        sql = f"""
            SELECT id, file_id, file_type, sequence_length,
                   line_lengths, indentation_depths, char_frequencies,
                   nesting_patterns, complexity_score, entropy,
                   avg_line_length, max_indentation
            FROM learning.numerical_sequences
            {where}
            {order}
            LIMIT %s
        """
        params.append(size)

        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur.fetchall()

    def get_stats(self):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT file_type,
                   COUNT(*) as count,
                   AVG(sequence_length)::int as avg_length,
                   AVG(complexity_score)::float as avg_complexity,
                   AVG(entropy)::float as avg_entropy,
                   MIN(sequence_length) as min_length,
                   MAX(sequence_length) as max_length
            FROM learning.numerical_sequences
            GROUP BY file_type
            ORDER BY count DESC
        """)
        return cur.fetchall()

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
        batch = self.get_batch(file_type, size, max_length=max_length)
        results = []

        for row in batch:
            ll = row["line_lengths"] or []
            ind = row["indentation_depths"] or []
            nest = row["nesting_patterns"] or []
            cf = row["char_frequencies"] or [0.0] * 256

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
                ch[3] = cf[97 + (step % 26)]   # a-z frequencies
                ch[4] = cf[48 + (step % 10)]   # 0-9 frequencies
                ch[5] = row["entropy"] / 8.0 if row["entropy"] else 0.0
                ch[6] = min(row["complexity_score"], 1.0) if row["complexity_score"] else 0.0
                ch[7] = min((row["avg_line_length"] or 0) / 120.0, 1.0)
                channels.append(ch)

            results.append({
                "file_id": row["file_id"],
                "file_type": row["file_type"],
                "num_steps": len(channels),
                "channels": channels,
            })

        return results

    def close(self):
        self.conn.close()


def serve(host, port, pg_host, pg_port):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    store = SequenceStore(pg_host, pg_port)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            if parsed.path == "/sequences/batch":
                ftype = params.get("type", [None])[0]
                size = int(params.get("size", [100])[0])
                min_c = float(params.get("min_complexity", [0])[0]) or None
                max_l = int(params.get("max_length", [0])[0]) or None
                batch = store.get_batch(ftype, size, min_c, max_l)
                self._json_response({"batch": batch, "count": len(batch)})

            elif parsed.path == "/sequences/stats":
                stats = store.get_stats()
                self._json_response({"stats": stats})

            elif parsed.path == "/sequences/random":
                ftype = params.get("type", [None])[0]
                size = int(params.get("size", [50])[0])
                max_l = int(params.get("max_length", [500])[0])
                channels = store.get_input_channels(ftype, size, max_l)
                self._json_response({"sequences": channels, "count": len(channels)})

            elif parsed.path == "/health":
                self._json_response({"status": "ok"})

            else:
                self.send_error(404)

        def _json_response(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())

        def log_message(self, fmt, *args):
            pass  # suppress access logs

    server = HTTPServer((host, port), Handler)
    print(f"Sequence store serving on {host}:{port}")
    print(f"  GET /sequences/batch?type=sourcecode&size=100")
    print(f"  GET /sequences/stats")
    print(f"  GET /sequences/random?type=sourcecode&size=50&max_length=500")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Stage 3: GA consumer for numerical sequences")
    sub = parser.add_subparsers(dest="cmd")

    srv = sub.add_parser("serve", help="Run REST server")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=5001)
    srv.add_argument("--pg-host", default="aio-01")
    srv.add_argument("--pg-port", type=int, default=5433)

    stats = sub.add_parser("stats", help="Print sequence stats")
    stats.add_argument("--pg-host", default="aio-01")
    stats.add_argument("--pg-port", type=int, default=5433)

    args = parser.parse_args()

    if args.cmd == "serve":
        serve(args.host, args.port, args.pg_host, args.pg_port)
    elif args.cmd == "stats":
        store = SequenceStore(args.pg_host, args.pg_port)
        for row in store.get_stats():
            print(f"  {row['file_type']:15s}: {row['count']:>6} seqs, "
                  f"avg_len={row['avg_length']}, avg_complexity={row['avg_complexity']:.3f}, "
                  f"avg_entropy={row['avg_entropy']:.2f}")
        store.close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
