#!/usr/bin/env python3
"""GeeksforGeeks documentation scraper.

Covers:
  - Data structures (arrays, linked lists, trees, graphs, hash tables, heaps, tries)
  - Sorting and searching algorithms
  - Graph algorithms (shortest path, MST, traversals, connectivity)
  - Dynamic programming, greedy algorithms, backtracking
  - String algorithms and bit manipulation
  - Competitive programming techniques
  - System design (URL shortener, chat, notification systems)
  - Operating systems (scheduling, memory, deadlocks, synchronization)
  - DBMS (normalization, SQL, transactions, indexing)
  - Computer networks (OSI, TCP/IP, DNS, routing, sockets)
  - Compiler design (parsing, code generation, optimization)
  - Theory of computation (automata, grammars, Turing machines, complexity)
  - Object-oriented programming and design patterns
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class GeeksForGeeksScraper(BaseScraper):
    """Scrape GeeksforGeeks tutorials, algorithms, and CS fundamentals."""

    SOURCES = {
        "data-structures": {
            "pages": {
                "https://www.geeksforgeeks.org/data-structures/": "Data Structures Overview",
                "https://www.geeksforgeeks.org/array-data-structure/": "Array Data Structure",
                "https://www.geeksforgeeks.org/linked-list-data-structure/": "Linked List Data Structure",
                "https://www.geeksforgeeks.org/singly-linked-list-tutorial/": "Singly Linked List Tutorial",
                "https://www.geeksforgeeks.org/doubly-linked-list/": "Doubly Linked List",
                "https://www.geeksforgeeks.org/circular-linked-list/": "Circular Linked List",
                "https://www.geeksforgeeks.org/stack-data-structure/": "Stack Data Structure",
                "https://www.geeksforgeeks.org/queue-data-structure/": "Queue Data Structure",
                "https://www.geeksforgeeks.org/priority-queue-set-1-introduction/": "Priority Queue Introduction",
                "https://www.geeksforgeeks.org/deque-set-1-introduction-applications/": "Deque Introduction and Applications",
                "https://www.geeksforgeeks.org/circular-queue-set-1-introduction-array-implementation/": "Circular Queue Introduction",
                "https://www.geeksforgeeks.org/binary-tree-data-structure/": "Binary Tree Data Structure",
                "https://www.geeksforgeeks.org/binary-search-tree-data-structure/": "Binary Search Tree Data Structure",
                "https://www.geeksforgeeks.org/avl-tree-set-1-insertion/": "AVL Tree Insertion",
                "https://www.geeksforgeeks.org/red-black-tree-set-1-introduction-2/": "Red-Black Tree Introduction",
                "https://www.geeksforgeeks.org/b-tree-set-1-introduction-2/": "B-Tree Introduction",
                "https://www.geeksforgeeks.org/heap-data-structure/": "Heap Data Structure",
                "https://www.geeksforgeeks.org/min-heap-in-python/": "Min Heap in Python",
                "https://www.geeksforgeeks.org/max-heap-in-python/": "Max Heap in Python",
                "https://www.geeksforgeeks.org/hashing-data-structure/": "Hashing Data Structure",
                "https://www.geeksforgeeks.org/hash-map-in-python/": "Hash Map in Python",
                "https://www.geeksforgeeks.org/hashset-in-java/": "HashSet in Java",
                "https://www.geeksforgeeks.org/separate-chaining-collision-handling-technique-in-hashing/": "Separate Chaining Collision Handling",
                "https://www.geeksforgeeks.org/open-addressing-collision-handling-technique-in-hashing/": "Open Addressing Collision Handling",
                "https://www.geeksforgeeks.org/graph-data-structure-and-algorithms/": "Graph Data Structure and Algorithms",
                "https://www.geeksforgeeks.org/graph-and-its-representations/": "Graph and Its Representations",
                "https://www.geeksforgeeks.org/adjacency-list-meaning-definition-in-dsa/": "Adjacency List",
                "https://www.geeksforgeeks.org/adjacency-matrix-meaning-and-definition-in-dsa/": "Adjacency Matrix",
                "https://www.geeksforgeeks.org/trie-insert-and-search/": "Trie Insert and Search",
                "https://www.geeksforgeeks.org/introduction-to-trie-data-structure-and-algorithm-tutorials/": "Introduction to Trie",
                "https://www.geeksforgeeks.org/segment-tree-data-structure/": "Segment Tree Data Structure",
                "https://www.geeksforgeeks.org/lazy-propagation-in-segment-tree/": "Lazy Propagation in Segment Tree",
                "https://www.geeksforgeeks.org/binary-indexed-tree-or-fenwick-tree-2/": "Binary Indexed Tree (Fenwick Tree)",
                "https://www.geeksforgeeks.org/disjoint-set-data-structures/": "Disjoint Set Data Structures",
                "https://www.geeksforgeeks.org/union-by-rank-and-path-compression-in-union-find-algorithm/": "Union by Rank and Path Compression",
                "https://www.geeksforgeeks.org/skip-list/": "Skip List",
                "https://www.geeksforgeeks.org/bloom-filters-introduction/": "Bloom Filters Introduction",
            },
        },
        "sorting-algorithms": {
            "pages": {
                "https://www.geeksforgeeks.org/sorting-algorithms/": "Sorting Algorithms Overview",
                "https://www.geeksforgeeks.org/bubble-sort-algorithm/": "Bubble Sort Algorithm",
                "https://www.geeksforgeeks.org/selection-sort-algorithm/": "Selection Sort Algorithm",
                "https://www.geeksforgeeks.org/insertion-sort-algorithm/": "Insertion Sort Algorithm",
                "https://www.geeksforgeeks.org/merge-sort/": "Merge Sort",
                "https://www.geeksforgeeks.org/quick-sort-algorithm/": "Quick Sort Algorithm",
                "https://www.geeksforgeeks.org/heap-sort/": "Heap Sort",
                "https://www.geeksforgeeks.org/radix-sort/": "Radix Sort",
                "https://www.geeksforgeeks.org/counting-sort/": "Counting Sort",
                "https://www.geeksforgeeks.org/bucket-sort-2/": "Bucket Sort",
                "https://www.geeksforgeeks.org/timsort/": "TimSort",
                "https://www.geeksforgeeks.org/stability-in-sorting-algorithms/": "Stability in Sorting Algorithms",
                "https://www.geeksforgeeks.org/comparison-among-bubble-sort-selection-sort-and-insertion-sort/": "Comparison Among Sorting Algorithms",
            },
        },
        "searching-algorithms": {
            "pages": {
                "https://www.geeksforgeeks.org/searching-algorithms/": "Searching Algorithms Overview",
                "https://www.geeksforgeeks.org/linear-search/": "Linear Search",
                "https://www.geeksforgeeks.org/binary-search/": "Binary Search",
                "https://www.geeksforgeeks.org/ternary-search/": "Ternary Search",
                "https://www.geeksforgeeks.org/interpolation-search/": "Interpolation Search",
                "https://www.geeksforgeeks.org/exponential-search/": "Exponential Search",
                "https://www.geeksforgeeks.org/jump-search/": "Jump Search",
                "https://www.geeksforgeeks.org/fibonacci-search/": "Fibonacci Search",
            },
        },
        "graph-algorithms": {
            "pages": {
                "https://www.geeksforgeeks.org/breadth-first-search-or-bfs-for-a-graph/": "Breadth First Search (BFS)",
                "https://www.geeksforgeeks.org/depth-first-search-or-dfs-for-a-graph/": "Depth First Search (DFS)",
                "https://www.geeksforgeeks.org/dijkstras-shortest-path-algorithm-greedy-algo-7/": "Dijkstra's Shortest Path Algorithm",
                "https://www.geeksforgeeks.org/bellman-ford-algorithm-dp-23/": "Bellman-Ford Algorithm",
                "https://www.geeksforgeeks.org/floyd-warshall-algorithm-dp-16/": "Floyd-Warshall Algorithm",
                "https://www.geeksforgeeks.org/prims-minimum-spanning-tree-mst-greedy-algo-5/": "Prim's Minimum Spanning Tree",
                "https://www.geeksforgeeks.org/kruskals-minimum-spanning-tree-algorithm-greedy-algo-2/": "Kruskal's Minimum Spanning Tree",
                "https://www.geeksforgeeks.org/topological-sorting/": "Topological Sorting",
                "https://www.geeksforgeeks.org/strongly-connected-components/": "Strongly Connected Components",
                "https://www.geeksforgeeks.org/tarjan-algorithm/": "Tarjan's Algorithm",
                "https://www.geeksforgeeks.org/kosarajus-strongly-connected-components-algorithm/": "Kosaraju's Algorithm",
                "https://www.geeksforgeeks.org/articulation-points-or-cut-vertices-in-a-graph/": "Articulation Points (Cut Vertices)",
                "https://www.geeksforgeeks.org/bridge-in-a-graph/": "Bridge in a Graph",
                "https://www.geeksforgeeks.org/eulerian-path-and-circuit/": "Eulerian Path and Circuit",
                "https://www.geeksforgeeks.org/hamiltonian-cycle/": "Hamiltonian Cycle",
                "https://www.geeksforgeeks.org/a-search-algorithm/": "A* Search Algorithm",
                "https://www.geeksforgeeks.org/ford-fulkerson-algorithm-for-maximum-flow-problem/": "Ford-Fulkerson Maximum Flow",
                "https://www.geeksforgeeks.org/maximum-bipartite-matching/": "Maximum Bipartite Matching",
                "https://www.geeksforgeeks.org/detect-cycle-in-a-graph/": "Detect Cycle in Directed Graph",
                "https://www.geeksforgeeks.org/detect-cycle-undirected-graph/": "Detect Cycle in Undirected Graph",
                "https://www.geeksforgeeks.org/shortest-path-in-unweighted-graph/": "Shortest Path in Unweighted Graph",
            },
        },
        "dynamic-programming": {
            "pages": {
                "https://www.geeksforgeeks.org/dynamic-programming/": "Dynamic Programming Overview",
                "https://www.geeksforgeeks.org/0-1-knapsack-problem-dp-10/": "0/1 Knapsack Problem",
                "https://www.geeksforgeeks.org/longest-common-subsequence-dp-4/": "Longest Common Subsequence",
                "https://www.geeksforgeeks.org/longest-increasing-subsequence-dp-3/": "Longest Increasing Subsequence",
                "https://www.geeksforgeeks.org/edit-distance-dp-5/": "Edit Distance",
                "https://www.geeksforgeeks.org/matrix-chain-multiplication-dp-8/": "Matrix Chain Multiplication",
                "https://www.geeksforgeeks.org/coin-change-dp-7/": "Coin Change Problem",
                "https://www.geeksforgeeks.org/cutting-a-rod-dp-13/": "Cutting a Rod",
                "https://www.geeksforgeeks.org/subset-sum-problem-dp-25/": "Subset Sum Problem",
                "https://www.geeksforgeeks.org/travelling-salesman-problem-set-1/": "Travelling Salesman Problem",
                "https://www.geeksforgeeks.org/weighted-job-scheduling/": "Weighted Job Scheduling",
                "https://www.geeksforgeeks.org/longest-palindromic-subsequence-dp-12/": "Longest Palindromic Subsequence",
                "https://www.geeksforgeeks.org/minimum-number-of-jumps-to-reach-end-of-a-given-array/": "Minimum Number of Jumps",
                "https://www.geeksforgeeks.org/optimal-binary-search-tree-dp-24/": "Optimal Binary Search Tree",
                "https://www.geeksforgeeks.org/word-break-problem-dp-32/": "Word Break Problem",
                "https://www.geeksforgeeks.org/egg-dropping-puzzle-dp-11/": "Egg Dropping Puzzle",
                "https://www.geeksforgeeks.org/maximum-sum-increasing-subsequence-dp-14/": "Maximum Sum Increasing Subsequence",
                "https://www.geeksforgeeks.org/longest-common-substring-dp-29/": "Longest Common Substring",
                "https://www.geeksforgeeks.org/count-all-possible-paths-from-top-left-to-bottom-right-of-a-mxn-matrix/": "Count All Paths in Matrix",
                "https://www.geeksforgeeks.org/partition-problem-dp-18/": "Partition Problem",
                "https://www.geeksforgeeks.org/maximum-subarray-sum-using-divide-and-conquer-algorithm/": "Maximum Subarray Sum (Divide and Conquer)",
            },
        },
        "greedy-algorithms": {
            "pages": {
                "https://www.geeksforgeeks.org/greedy-algorithms/": "Greedy Algorithms Overview",
                "https://www.geeksforgeeks.org/activity-selection-problem-greedy-algo-1/": "Activity Selection Problem",
                "https://www.geeksforgeeks.org/huffman-coding-greedy-algo-3/": "Huffman Coding",
                "https://www.geeksforgeeks.org/fractional-knapsack-problem/": "Fractional Knapsack Problem",
                "https://www.geeksforgeeks.org/job-sequencing-problem/": "Job Sequencing Problem",
                "https://www.geeksforgeeks.org/minimum-number-of-platforms-required-for-a-railwaybus-station/": "Minimum Number of Platforms",
                "https://www.geeksforgeeks.org/prim-minimum-spanning-tree-mst/": "Prim's MST",
                "https://www.geeksforgeeks.org/kruskals-algorithm-simple-implementation-for-adjacency-matrix/": "Kruskal's Algorithm (Adjacency Matrix)",
                "https://www.geeksforgeeks.org/greedy-algorithm-to-find-minimum-number-of-coins/": "Minimum Number of Coins",
            },
        },
        "backtracking": {
            "pages": {
                "https://www.geeksforgeeks.org/backtracking-algorithms/": "Backtracking Algorithms Overview",
                "https://www.geeksforgeeks.org/n-queen-problem-backtracking-3/": "N-Queen Problem",
                "https://www.geeksforgeeks.org/sudoku-backtracking-7/": "Sudoku Solver",
                "https://www.geeksforgeeks.org/subset-sum-backtracking-4/": "Subset Sum (Backtracking)",
                "https://www.geeksforgeeks.org/write-a-c-program-to-print-all-permutations-of-a-given-string/": "Print All Permutations of a String",
                "https://www.geeksforgeeks.org/the-knights-tour-problem/": "The Knight's Tour Problem",
                "https://www.geeksforgeeks.org/rat-in-a-maze-problem-when-movement-in-all-possible-directions-is-allowed/": "Rat in a Maze Problem",
                "https://www.geeksforgeeks.org/m-coloring-problem/": "M-Coloring Problem",
                "https://www.geeksforgeeks.org/hamiltonian-cycle-backtracking-6/": "Hamiltonian Cycle (Backtracking)",
            },
        },
        "string-algorithms": {
            "pages": {
                "https://www.geeksforgeeks.org/string-data-structure/": "String Data Structure Overview",
                "https://www.geeksforgeeks.org/kmp-algorithm-for-pattern-searching/": "KMP Algorithm for Pattern Searching",
                "https://www.geeksforgeeks.org/rabin-karp-algorithm-for-pattern-searching/": "Rabin-Karp Algorithm",
                "https://www.geeksforgeeks.org/z-algorithm-linear-time-pattern-searching-algorithm/": "Z Algorithm",
                "https://www.geeksforgeeks.org/aho-corasick-algorithm-pattern-searching/": "Aho-Corasick Algorithm",
                "https://www.geeksforgeeks.org/suffix-array-set-1-introduction/": "Suffix Array Introduction",
                "https://www.geeksforgeeks.org/suffix-tree-application-1-substring-check/": "Suffix Tree Substring Check",
                "https://www.geeksforgeeks.org/manachers-algorithm-linear-time-longest-palindromic-substring-part-1/": "Manacher's Algorithm",
                "https://www.geeksforgeeks.org/longest-palindromic-substring/": "Longest Palindromic Substring",
                "https://www.geeksforgeeks.org/anagram-substring-search-or-search-for-all-permutations/": "Anagram Substring Search",
            },
        },
        "bit-manipulation": {
            "pages": {
                "https://www.geeksforgeeks.org/bit-manipulation-technique/": "Bit Manipulation Technique",
                "https://www.geeksforgeeks.org/bitwise-operators-in-c-cpp/": "Bitwise Operators in C/C++",
                "https://www.geeksforgeeks.org/bit-tricks-for-competitive-programming/": "Bit Tricks for Competitive Programming",
                "https://www.geeksforgeeks.org/find-the-element-that-appears-once/": "Find the Element That Appears Once",
                "https://www.geeksforgeeks.org/count-set-bits-in-an-integer/": "Count Set Bits in an Integer",
                "https://www.geeksforgeeks.org/power-of-two/": "Power of Two",
                "https://www.geeksforgeeks.org/position-of-rightmost-set-bit/": "Position of Rightmost Set Bit",
            },
        },
        "competitive-programming": {
            "pages": {
                "https://www.geeksforgeeks.org/competitive-programming-a-complete-guide/": "Competitive Programming Complete Guide",
                "https://www.geeksforgeeks.org/two-pointers-technique/": "Two Pointers Technique",
                "https://www.geeksforgeeks.org/window-sliding-technique/": "Window Sliding Technique",
                "https://www.geeksforgeeks.org/prefix-sum-array-implementation-and-applications-in-competitive-programming/": "Prefix Sum Array",
                "https://www.geeksforgeeks.org/binary-lifting-technique/": "Binary Lifting Technique",
                "https://www.geeksforgeeks.org/mos-algorithm-query-square-root-decomposition-set-1-introduction/": "Mo's Algorithm (Square Root Decomposition)",
                "https://www.geeksforgeeks.org/sqrt-square-root-decomposition-technique-set-1-introduction/": "Square Root Decomposition",
                "https://www.geeksforgeeks.org/heavy-light-decomposition/": "Heavy Light Decomposition",
                "https://www.geeksforgeeks.org/meet-in-the-middle/": "Meet in the Middle",
                "https://www.geeksforgeeks.org/fast-io-for-competitive-programming/": "Fast I/O for Competitive Programming",
                "https://www.geeksforgeeks.org/policy-based-data-structures-g/": "Policy Based Data Structures",
            },
        },
        "system-design": {
            "pages": {
                "https://www.geeksforgeeks.org/system-design-tutorial/": "System Design Tutorial",
                "https://www.geeksforgeeks.org/design-url-shortening-service-api/": "Design URL Shortening Service",
                "https://www.geeksforgeeks.org/design-twitter-a-system-design-interview-question/": "Design Twitter",
                "https://www.geeksforgeeks.org/design-instagram/": "Design Instagram",
                "https://www.geeksforgeeks.org/rate-limiting-system-design/": "Rate Limiting System Design",
                "https://www.geeksforgeeks.org/caching-system-design-concept-for-designing-a-system/": "Caching System Design",
                "https://www.geeksforgeeks.org/design-message-queue-system-design/": "Design Message Queue",
                "https://www.geeksforgeeks.org/design-search-engine/": "Design Search Engine",
                "https://www.geeksforgeeks.org/design-file-storage-system-dropbox/": "Design File Storage System (Dropbox)",
                "https://www.geeksforgeeks.org/design-notification-system-system-design/": "Design Notification System",
                "https://www.geeksforgeeks.org/design-a-chat-system/": "Design a Chat System",
                "https://www.geeksforgeeks.org/design-video-sharing-system/": "Design Video Sharing System",
                "https://www.geeksforgeeks.org/design-parking-lot-system/": "Design Parking Lot System",
                "https://www.geeksforgeeks.org/design-elevator-system/": "Design Elevator System",
                "https://www.geeksforgeeks.org/design-atm/": "Design ATM",
                "https://www.geeksforgeeks.org/system-design-of-uber-app-uber-system-architecture/": "System Design of Uber",
                "https://www.geeksforgeeks.org/design-scalable-system-like-instagram/": "Design Scalable System Like Instagram",
                "https://www.geeksforgeeks.org/what-is-load-balancer-system-design/": "What is Load Balancer",
                "https://www.geeksforgeeks.org/consistent-hashing/": "Consistent Hashing",
                "https://www.geeksforgeeks.org/database-sharding-a-system-design-concept/": "Database Sharding",
            },
        },
        "operating-systems": {
            "pages": {
                "https://www.geeksforgeeks.org/operating-systems/": "Operating Systems Overview",
                "https://www.geeksforgeeks.org/introduction-of-process-management/": "Introduction of Process Management",
                "https://www.geeksforgeeks.org/cpu-scheduling-in-operating-systems/": "CPU Scheduling in Operating Systems",
                "https://www.geeksforgeeks.org/program-for-fcfs-cpu-scheduling-set-1/": "FCFS CPU Scheduling",
                "https://www.geeksforgeeks.org/shortest-job-first-or-sjf-cpu-scheduling-non-preemptive-algorithm-using-segment-tree/": "Shortest Job First (SJF) Scheduling",
                "https://www.geeksforgeeks.org/program-for-round-robin-scheduling-for-the-same-arrival-time/": "Round Robin Scheduling",
                "https://www.geeksforgeeks.org/preemptive-priority-cpu-scheduling-algortithm/": "Preemptive Priority Scheduling",
                "https://www.geeksforgeeks.org/paging-in-operating-system/": "Paging in Operating System",
                "https://www.geeksforgeeks.org/segmentation-in-operating-system/": "Segmentation in Operating System",
                "https://www.geeksforgeeks.org/virtual-memory-in-operating-system/": "Virtual Memory in Operating System",
                "https://www.geeksforgeeks.org/page-replacement-algorithms-in-operating-systems/": "Page Replacement Algorithms",
                "https://www.geeksforgeeks.org/file-systems-in-operating-system/": "File Systems in Operating System",
                "https://www.geeksforgeeks.org/introduction-of-deadlock-in-operating-system/": "Introduction of Deadlock",
                "https://www.geeksforgeeks.org/deadlock-detection-algorithm/": "Deadlock Detection Algorithm",
                "https://www.geeksforgeeks.org/deadlock-prevention/": "Deadlock Prevention",
                "https://www.geeksforgeeks.org/mutex-vs-semaphore/": "Mutex vs Semaphore",
                "https://www.geeksforgeeks.org/monitors-in-process-synchronization/": "Monitors in Process Synchronization",
                "https://www.geeksforgeeks.org/difference-between-process-and-thread/": "Difference Between Process and Thread",
                "https://www.geeksforgeeks.org/inter-process-communication-ipc/": "Inter-Process Communication (IPC)",
                "https://www.geeksforgeeks.org/memory-management-in-operating-system/": "Memory Management in Operating System",
                "https://www.geeksforgeeks.org/bankers-algorithm-in-operating-system/": "Banker's Algorithm",
            },
        },
        "dbms": {
            "pages": {
                "https://www.geeksforgeeks.org/dbms/": "DBMS Overview",
                "https://www.geeksforgeeks.org/introduction-of-er-model/": "Introduction of ER Model",
                "https://www.geeksforgeeks.org/normal-forms-in-dbms/": "Normal Forms in DBMS",
                "https://www.geeksforgeeks.org/first-normal-form-1nf/": "First Normal Form (1NF)",
                "https://www.geeksforgeeks.org/second-normal-form-2nf/": "Second Normal Form (2NF)",
                "https://www.geeksforgeeks.org/third-normal-form-3nf/": "Third Normal Form (3NF)",
                "https://www.geeksforgeeks.org/boyce-codd-normal-form-bcnf/": "Boyce-Codd Normal Form (BCNF)",
                "https://www.geeksforgeeks.org/fourth-normal-form-4nf/": "Fourth Normal Form (4NF)",
                "https://www.geeksforgeeks.org/fifth-normal-form-5nf/": "Fifth Normal Form (5NF)",
                "https://www.geeksforgeeks.org/sql-tutorial/": "SQL Tutorial",
                "https://www.geeksforgeeks.org/sql-join-set-1-inner-left-right-and-full-joins/": "SQL JOINs",
                "https://www.geeksforgeeks.org/indexing-in-databases-set-1/": "Indexing in Databases",
                "https://www.geeksforgeeks.org/acid-properties-in-dbms/": "ACID Properties in DBMS",
                "https://www.geeksforgeeks.org/transaction-in-dbms/": "Transaction in DBMS",
                "https://www.geeksforgeeks.org/concurrency-control-in-dbms/": "Concurrency Control in DBMS",
                "https://www.geeksforgeeks.org/database-recovery-techniques-in-dbms/": "Database Recovery Techniques",
                "https://www.geeksforgeeks.org/introduction-to-nosql/": "Introduction to NoSQL",
                "https://www.geeksforgeeks.org/sql-ddl-dql-dml-dcl-tcl-commands/": "SQL DDL DQL DML DCL TCL Commands",
                "https://www.geeksforgeeks.org/aggregate-functions-in-sql/": "Aggregate Functions in SQL",
                "https://www.geeksforgeeks.org/sql-subquery/": "SQL Subquery",
                "https://www.geeksforgeeks.org/sql-views/": "SQL Views",
            },
        },
        "computer-networks": {
            "pages": {
                "https://www.geeksforgeeks.org/computer-network-tutorials/": "Computer Network Tutorials",
                "https://www.geeksforgeeks.org/layers-of-osi-model/": "Layers of OSI Model",
                "https://www.geeksforgeeks.org/tcp-ip-model/": "TCP/IP Model",
                "https://www.geeksforgeeks.org/difference-between-http-and-https/": "Difference Between HTTP and HTTPS",
                "https://www.geeksforgeeks.org/domain-name-system-dns-in-application-layer/": "Domain Name System (DNS)",
                "https://www.geeksforgeeks.org/dynamic-host-configuration-protocol-dhcp/": "Dynamic Host Configuration Protocol (DHCP)",
                "https://www.geeksforgeeks.org/how-address-resolution-protocol-arp-works/": "Address Resolution Protocol (ARP)",
                "https://www.geeksforgeeks.org/routing-information-protocol-rip/": "Routing Information Protocol (RIP)",
                "https://www.geeksforgeeks.org/open-shortest-path-first-ospf-protocol-fundamentals/": "OSPF Protocol Fundamentals",
                "https://www.geeksforgeeks.org/border-gateway-protocol-bgp/": "Border Gateway Protocol (BGP)",
                "https://www.geeksforgeeks.org/introduction-of-subnetting/": "Introduction of Subnetting",
                "https://www.geeksforgeeks.org/network-address-translation-nat/": "Network Address Translation (NAT)",
                "https://www.geeksforgeeks.org/introduction-of-firewall-in-computer-network/": "Introduction of Firewall",
                "https://www.geeksforgeeks.org/secure-socket-layer-ssl/": "Secure Socket Layer (SSL)",
                "https://www.geeksforgeeks.org/socket-programming-cc/": "Socket Programming in C/C++",
                "https://www.geeksforgeeks.org/rest-api-introduction/": "REST API Introduction",
                "https://www.geeksforgeeks.org/what-is-web-socket-and-how-it-is-different-from-the-http/": "WebSocket vs HTTP",
                "https://www.geeksforgeeks.org/types-of-network-topology/": "Types of Network Topology",
                "https://www.geeksforgeeks.org/difference-between-tcp-and-udp/": "Difference Between TCP and UDP",
                "https://www.geeksforgeeks.org/ipv4-vs-ipv6/": "IPv4 vs IPv6",
            },
        },
        "compiler-design": {
            "pages": {
                "https://www.geeksforgeeks.org/compiler-design-tutorials/": "Compiler Design Tutorials",
                "https://www.geeksforgeeks.org/introduction-of-lexical-analysis/": "Introduction of Lexical Analysis",
                "https://www.geeksforgeeks.org/classification-of-top-down-parsers/": "Classification of Top-Down Parsers",
                "https://www.geeksforgeeks.org/parsing-set-1-introduction-ambiguity-and-parsers/": "Parsing Introduction and Ambiguity",
                "https://www.geeksforgeeks.org/ll-parser/": "LL Parser",
                "https://www.geeksforgeeks.org/lr-parser/": "LR Parser",
                "https://www.geeksforgeeks.org/lalr-parser/": "LALR Parser",
                "https://www.geeksforgeeks.org/syntax-tree/": "Syntax Tree",
                "https://www.geeksforgeeks.org/semantic-analysis-in-compiler-design/": "Semantic Analysis",
                "https://www.geeksforgeeks.org/code-generation-in-compiler-design/": "Code Generation",
                "https://www.geeksforgeeks.org/code-optimization-in-compiler-design/": "Code Optimization",
                "https://www.geeksforgeeks.org/symbol-table-compiler/": "Symbol Table",
                "https://www.geeksforgeeks.org/intermediate-code-generation-in-compiler-design/": "Intermediate Code Generation",
            },
        },
        "theory-of-computation": {
            "pages": {
                "https://www.geeksforgeeks.org/theory-of-computation-automata-tutorials/": "Theory of Computation Tutorials",
                "https://www.geeksforgeeks.org/introduction-of-finite-automata/": "Introduction of Finite Automata",
                "https://www.geeksforgeeks.org/deterministic-finite-automaton-dfa/": "Deterministic Finite Automaton (DFA)",
                "https://www.geeksforgeeks.org/nondeterministic-finite-automaton-nfa/": "Nondeterministic Finite Automaton (NFA)",
                "https://www.geeksforgeeks.org/regular-expressions-regular-grammar-and-regular-languages/": "Regular Expressions and Grammar",
                "https://www.geeksforgeeks.org/context-free-grammar-cfg/": "Context-Free Grammar (CFG)",
                "https://www.geeksforgeeks.org/pushdown-automata-acceptance-by-final-state/": "Pushdown Automata",
                "https://www.geeksforgeeks.org/turing-machine-in-toc/": "Turing Machine",
                "https://www.geeksforgeeks.org/decidability/": "Decidability",
                "https://www.geeksforgeeks.org/undecidable-problems-in-theory-of-computation/": "Undecidable Problems",
                "https://www.geeksforgeeks.org/complexity-classes-p-np-conp-np-hard-and-np-complete/": "Complexity Classes (P, NP, NP-Hard, NP-Complete)",
                "https://www.geeksforgeeks.org/np-completeness-set-1/": "NP-Completeness",
                "https://www.geeksforgeeks.org/proof-that-hamiltonian-path-is-np-complete/": "Proof: Hamiltonian Path is NP-Complete",
            },
        },
        "oop": {
            "pages": {
                "https://www.geeksforgeeks.org/object-oriented-programming-oops-concept-in-java/": "OOP Concepts in Java",
                "https://www.geeksforgeeks.org/classes-objects-java/": "Classes and Objects in Java",
                "https://www.geeksforgeeks.org/inheritance-in-java/": "Inheritance in Java",
                "https://www.geeksforgeeks.org/polymorphism-in-java/": "Polymorphism in Java",
                "https://www.geeksforgeeks.org/abstraction-in-java-2/": "Abstraction in Java",
                "https://www.geeksforgeeks.org/encapsulation-in-java/": "Encapsulation in Java",
                "https://www.geeksforgeeks.org/solid-principle-in-programming-understand-with-real-life-examples/": "SOLID Principles",
                "https://www.geeksforgeeks.org/software-design-patterns/": "Software Design Patterns",
                "https://www.geeksforgeeks.org/singleton-design-pattern/": "Singleton Design Pattern",
                "https://www.geeksforgeeks.org/factory-method-design-pattern-in-java/": "Factory Method Design Pattern",
                "https://www.geeksforgeeks.org/observer-pattern-set-1-introduction/": "Observer Pattern Introduction",
                "https://www.geeksforgeeks.org/strategy-pattern-set-1/": "Strategy Pattern",
                "https://www.geeksforgeeks.org/adapter-pattern/": "Adapter Pattern",
                "https://www.geeksforgeeks.org/decorator-pattern-set-1-background/": "Decorator Pattern",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"geeksforgeeks-{source_key}" if source_key else "geeksforgeeks"
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
            for suffix in [' - GeeksforGeeks', ' | GeeksforGeeks']:
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
                        "category": f"geeksforgeeks-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(2.0)
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
            self.log.info(f"=== Scraping geeksforgeeks/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    GeeksForGeeksScraper(base, source_key).run()
