#!/usr/bin/env python3
"""CP Algorithms documentation scraper.

Covers:
  - Algebra (binary exponentiation, number theory, modular arithmetic)
  - Data Structures (segment trees, Fenwick trees, DSU, treaps)
  - Dynamic Programming (divide and conquer DP, Knuth's optimization)
  - String Processing (hashing, suffix arrays, Aho-Corasick)
  - Linear Algebra (Gauss elimination, matrix exponentiation)
  - Combinatorics (binomial coefficients, Catalan numbers, Burnside's lemma)
  - Numerical Methods (ternary search, Newton's method, FFT)
  - Geometry (convex hull, segment intersection, Delaunay triangulation)
  - Graph Algorithms (BFS, DFS, shortest paths, flows, matching, decompositions)
  - Miscellaneous (game theory, scheduling, meet in the middle)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class CPAlgorithmsScraper(BaseScraper):
    """Scrape CP Algorithms competitive programming reference articles."""

    SOURCES = {
        "algebra": {
            "pages": {
                "https://cp-algorithms.com/algebra/binary-exp.html": "Binary Exponentiation",
                "https://cp-algorithms.com/algebra/euclid-algorithm.html": "Euclidean Algorithm",
                "https://cp-algorithms.com/algebra/extended-euclid-algorithm.html": "Extended Euclidean Algorithm",
                "https://cp-algorithms.com/algebra/linear-diophantine-equation.html": "Linear Diophantine Equations",
                "https://cp-algorithms.com/algebra/fibonacci-numbers.html": "Fibonacci Numbers",
                "https://cp-algorithms.com/algebra/sieve-of-eratosthenes.html": "Sieve of Eratosthenes",
                "https://cp-algorithms.com/algebra/prime-sieve-linear.html": "Linear Sieve",
                "https://cp-algorithms.com/algebra/primality_tests.html": "Primality Tests",
                "https://cp-algorithms.com/algebra/factorization.html": "Integer Factorization",
                "https://cp-algorithms.com/algebra/phi-function.html": "Euler's Totient Function",
                "https://cp-algorithms.com/algebra/divisors.html": "Number of Divisors / Sum of Divisors",
                "https://cp-algorithms.com/algebra/module-inverse.html": "Modular Inverse",
                "https://cp-algorithms.com/algebra/chinese-remainder-theorem.html": "Chinese Remainder Theorem",
                "https://cp-algorithms.com/algebra/primitive-root.html": "Primitive Root",
                "https://cp-algorithms.com/algebra/discrete-log.html": "Discrete Logarithm",
                "https://cp-algorithms.com/algebra/discrete-root.html": "Discrete Root",
                "https://cp-algorithms.com/algebra/montgomery_multiplication.html": "Montgomery Multiplication",
                "https://cp-algorithms.com/algebra/balanced-ternary.html": "Balanced Ternary",
                "https://cp-algorithms.com/algebra/gray-code.html": "Gray Code",
            },
        },
        "data-structures": {
            "pages": {
                "https://cp-algorithms.com/data_structures/stack_order_statistics.html": "Minimum Stack / Minimum Queue",
                "https://cp-algorithms.com/data_structures/sparse-table.html": "Sparse Table",
                "https://cp-algorithms.com/data_structures/disjoint_set_union.html": "Disjoint Set Union",
                "https://cp-algorithms.com/data_structures/fenwick.html": "Fenwick Tree",
                "https://cp-algorithms.com/data_structures/segment_tree.html": "Segment Tree",
                "https://cp-algorithms.com/data_structures/segment_tree_lazy.html": "Segment Tree with Lazy Propagation",
                "https://cp-algorithms.com/data_structures/segment_tree_persistent.html": "Persistent Segment Tree",
                "https://cp-algorithms.com/data_structures/segment_tree_2d.html": "2D Segment Tree",
                "https://cp-algorithms.com/data_structures/sqrt_decomposition.html": "Sqrt Decomposition",
                "https://cp-algorithms.com/data_structures/treap.html": "Treap",
                "https://cp-algorithms.com/data_structures/sqrt-tree.html": "Sqrt Tree",
                "https://cp-algorithms.com/data_structures/randomized_heap.html": "Randomized Heap",
            },
        },
        "dynamic-programming": {
            "pages": {
                "https://cp-algorithms.com/dynamic_programming/divide-and-conquer-dp.html": "Divide and Conquer DP",
                "https://cp-algorithms.com/dynamic_programming/knuth-optimization.html": "Knuth's Optimization",
                "https://cp-algorithms.com/dynamic_programming/profile-dynamics.html": "DP on Broken Profile",
                "https://cp-algorithms.com/dynamic_programming/zero_matrix.html": "Finding the Largest Zero Submatrix",
            },
        },
        "string-processing": {
            "pages": {
                "https://cp-algorithms.com/string/string-hashing.html": "String Hashing",
                "https://cp-algorithms.com/string/rabin-karp.html": "Rabin-Karp Algorithm",
                "https://cp-algorithms.com/string/prefix-function.html": "Prefix Function (KMP)",
                "https://cp-algorithms.com/string/z-function.html": "Z-function",
                "https://cp-algorithms.com/string/suffix-array.html": "Suffix Array",
                "https://cp-algorithms.com/string/suffix-automaton.html": "Suffix Automaton",
                "https://cp-algorithms.com/string/aho_corasick.html": "Aho-Corasick Algorithm",
                "https://cp-algorithms.com/string/suffix-tree-ukkonen.html": "Suffix Tree (Ukkonen's Algorithm)",
                "https://cp-algorithms.com/string/manacher.html": "Manacher's Algorithm",
                "https://cp-algorithms.com/string/lyndon_factorization.html": "Lyndon Factorization",
                "https://cp-algorithms.com/string/expression_parsing.html": "Expression Parsing",
            },
        },
        "linear-algebra": {
            "pages": {
                "https://cp-algorithms.com/linear_algebra/linear-system-gauss.html": "Gauss Method for Solving Systems of Linear Equations",
                "https://cp-algorithms.com/linear_algebra/determinant-gauss.html": "Determinant of a Matrix (Gauss)",
                "https://cp-algorithms.com/linear_algebra/determinant-kraut.html": "Determinant of a Matrix (Kraut)",
                "https://cp-algorithms.com/linear_algebra/rank-matrix.html": "Rank of a Matrix",
                "https://cp-algorithms.com/linear_algebra/matrix-exponentiation.html": "Matrix Exponentiation",
            },
        },
        "combinatorics": {
            "pages": {
                "https://cp-algorithms.com/combinatorics/binomial-coefficients.html": "Binomial Coefficients",
                "https://cp-algorithms.com/combinatorics/catalan-numbers.html": "Catalan Numbers",
                "https://cp-algorithms.com/combinatorics/inclusion-exclusion.html": "Inclusion-Exclusion Principle",
                "https://cp-algorithms.com/combinatorics/burnside.html": "Burnside's Lemma / Polya Enumeration Theorem",
                "https://cp-algorithms.com/combinatorics/stars_and_bars.html": "Stars and Bars",
                "https://cp-algorithms.com/combinatorics/generating-functions.html": "Generating Functions",
                "https://cp-algorithms.com/combinatorics/kirchhoff-theorem.html": "Kirchhoff's Theorem",
            },
        },
        "numerical-methods": {
            "pages": {
                "https://cp-algorithms.com/num_methods/ternary_search.html": "Ternary Search",
                "https://cp-algorithms.com/num_methods/roots_newton.html": "Newton's Method for Finding Roots",
                "https://cp-algorithms.com/num_methods/simpson-integration.html": "Integration by Simpson's Formula",
                "https://cp-algorithms.com/algebra/fft.html": "Fast Fourier Transform (FFT)",
            },
        },
        "geometry": {
            "pages": {
                "https://cp-algorithms.com/geometry/basic-geometry.html": "Basic Geometry",
                "https://cp-algorithms.com/geometry/segment-intersection.html": "Finding Intersection of Two Segments",
                "https://cp-algorithms.com/geometry/check-segments-intersection.html": "Check if Two Segments Intersect",
                "https://cp-algorithms.com/geometry/circle-line-intersection.html": "Intersection of Circle and Line",
                "https://cp-algorithms.com/geometry/circle-circle-intersection.html": "Intersection of Two Circles",
                "https://cp-algorithms.com/geometry/convex-hull.html": "Convex Hull",
                "https://cp-algorithms.com/geometry/convex_hull_trick.html": "Convex Hull Trick",
                "https://cp-algorithms.com/geometry/point-in-convex-polygon.html": "Point in Convex Polygon",
                "https://cp-algorithms.com/geometry/minkowski.html": "Minkowski Sum of Convex Polygons",
                "https://cp-algorithms.com/geometry/picks-theorem.html": "Pick's Theorem",
                "https://cp-algorithms.com/geometry/lattice-points.html": "Lattice Points Inside Non-Lattice Polygon",
                "https://cp-algorithms.com/geometry/length-of-segments-union.html": "Length of Union of Segments",
                "https://cp-algorithms.com/geometry/nearest_points.html": "Finding the Nearest Pair of Points",
                "https://cp-algorithms.com/geometry/area-of-simple-polygon.html": "Area of Simple Polygon",
                "https://cp-algorithms.com/geometry/planar.html": "Planar Graph Face Counting",
                "https://cp-algorithms.com/geometry/tangent-to-convex-polygon.html": "Tangent Lines to Convex Polygon",
                "https://cp-algorithms.com/geometry/halfplane-intersection.html": "Half-plane Intersection",
                "https://cp-algorithms.com/geometry/delaunay.html": "Delaunay Triangulation and Voronoi Diagram",
                "https://cp-algorithms.com/geometry/vertical_decomposition.html": "Vertical Decomposition",
                "https://cp-algorithms.com/geometry/grahams-scan-convex-hull.html": "Graham's Scan Convex Hull",
            },
        },
        "graph-algorithms": {
            "pages": {
                "https://cp-algorithms.com/graph/breadth-first-search.html": "Breadth First Search (BFS)",
                "https://cp-algorithms.com/graph/depth-first-search.html": "Depth First Search (DFS)",
                "https://cp-algorithms.com/graph/topological-sort.html": "Topological Sort",
                "https://cp-algorithms.com/graph/finding-cycle.html": "Cycle Detection",
                "https://cp-algorithms.com/graph/connected-components.html": "Connected Components",
                "https://cp-algorithms.com/graph/strongly-connected-components.html": "Strongly Connected Components (Kosaraju)",
                "https://cp-algorithms.com/graph/strongly_connected_components_tarjan.html": "Strongly Connected Components (Tarjan)",
                "https://cp-algorithms.com/graph/bridge-searching.html": "Bridge Finding",
                "https://cp-algorithms.com/graph/cutpoints.html": "Articulation Points (Cut Vertices)",
                "https://cp-algorithms.com/graph/bridge-searching-online.html": "Bridge Finding Online",
                "https://cp-algorithms.com/graph/biconnected-components.html": "Biconnected Components",
                "https://cp-algorithms.com/graph/dijkstra.html": "Dijkstra's Algorithm",
                "https://cp-algorithms.com/graph/dijkstra_sparse.html": "Dijkstra on Sparse Graphs",
                "https://cp-algorithms.com/graph/bellman_ford.html": "Bellman-Ford Algorithm",
                "https://cp-algorithms.com/graph/all-pair-shortest-path-floyd-warshall.html": "Floyd-Warshall Algorithm",
                "https://cp-algorithms.com/graph/01_bfs.html": "0-1 BFS",
                "https://cp-algorithms.com/graph/desopo_pape.html": "D'Esopo-Pape Algorithm",
                "https://cp-algorithms.com/graph/mst_prim.html": "Minimum Spanning Tree (Prim's)",
                "https://cp-algorithms.com/graph/mst_kruskal.html": "Minimum Spanning Tree (Kruskal's)",
                "https://cp-algorithms.com/graph/mst_kruskal_with_dsu.html": "Kruskal's with DSU",
                "https://cp-algorithms.com/graph/second_best_mst.html": "Second Best MST",
                "https://cp-algorithms.com/graph/kirchhoff-theorem.html": "Kirchhoff's Theorem (Spanning Tree Count)",
                "https://cp-algorithms.com/graph/pruefer_code.html": "Prufer Code",
                "https://cp-algorithms.com/graph/lca.html": "Lowest Common Ancestor (LCA)",
                "https://cp-algorithms.com/graph/lca_binary_lifting.html": "LCA with Binary Lifting",
                "https://cp-algorithms.com/graph/lca_farachcoltonbender.html": "LCA (Farach-Colton and Bender)",
                "https://cp-algorithms.com/graph/lca_tarjan.html": "LCA (Tarjan's Offline Algorithm)",
                "https://cp-algorithms.com/graph/edmonds_karp.html": "Maximum Flow (Edmonds-Karp / Ford-Fulkerson)",
                "https://cp-algorithms.com/graph/push-relabel.html": "Maximum Flow (Push-Relabel)",
                "https://cp-algorithms.com/graph/dinic.html": "Maximum Flow (Dinic's Algorithm)",
                "https://cp-algorithms.com/graph/flow_with_demands.html": "Flows with Demands",
                "https://cp-algorithms.com/graph/min_cost_flow.html": "Minimum Cost Flow",
                "https://cp-algorithms.com/graph/kuhn_maximum_bipartite_matching.html": "Maximum Bipartite Matching (Kuhn's Algorithm)",
                "https://cp-algorithms.com/graph/hungarian-algorithm.html": "Hungarian Algorithm",
                "https://cp-algorithms.com/graph/euler_path.html": "Euler Path / Euler Circuit",
                "https://cp-algorithms.com/graph/2SAT.html": "2-SAT",
                "https://cp-algorithms.com/graph/hld.html": "Heavy-Light Decomposition",
                "https://cp-algorithms.com/graph/centroid-decomposition.html": "Centroid Decomposition",
                "https://cp-algorithms.com/graph/edge_vertex_connectivity.html": "Edge/Vertex Connectivity",
                "https://cp-algorithms.com/graph/tree_painting.html": "Tree Painting / Rerooting",
            },
        },
        "miscellaneous": {
            "pages": {
                "https://cp-algorithms.com/game_theory/sprague-grundy-nim.html": "Sprague-Grundy Theorem / Nim",
                "https://cp-algorithms.com/others/josephus_problem.html": "Josephus Problem",
                "https://cp-algorithms.com/others/15-puzzle.html": "15 Puzzle Game",
                "https://cp-algorithms.com/others/meet-in-the-middle.html": "Meet in the Middle",
                "https://cp-algorithms.com/schedules/schedule_one_machine.html": "Scheduling on One Machine",
                "https://cp-algorithms.com/schedules/schedule_two_machines.html": "Scheduling on Two Machines",
                "https://cp-algorithms.com/others/stern_brocot_tree_farey_sequences.html": "Stern-Brocot Tree / Farey Sequences",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"cp-algorithms-{source_key}" if source_key else "cp-algorithms"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Competitive Programming Algorithms', ' - CP-Algorithms']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})
        for url, title in pages.items():
            if not self.running:
                break
            item_id = self.make_id(url)
            content = self.fetch_url(url)
            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)
                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"cp-algorithms-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(1.5)
        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping cp-algorithms/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    CPAlgorithmsScraper(base, source_key).run()
