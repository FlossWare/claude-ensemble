#!/usr/bin/env python3
"""Redis documentation scraper.

Covers:
  - Redis data types (strings, lists, sets, sorted sets, hashes, streams, etc.)
  - Redis commands (by group)
  - Redis management (persistence, replication, sentinel, cluster, security)
  - Redis Stack (Search, JSON, TimeSeries, Bloom)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RedisScraper(BaseScraper):
    """Scrape Redis documentation from redis.io."""

    SOURCES = {
        "data-types": {
            "pages": {
                # Data types overview
                "https://redis.io/docs/latest/develop/data-types/": "Data Types Overview",
                "https://redis.io/docs/latest/develop/data-types/strings/": "Strings",
                "https://redis.io/docs/latest/develop/data-types/lists/": "Lists",
                "https://redis.io/docs/latest/develop/data-types/sets/": "Sets",
                "https://redis.io/docs/latest/develop/data-types/sorted-sets/": "Sorted Sets",
                "https://redis.io/docs/latest/develop/data-types/hashes/": "Hashes",
                "https://redis.io/docs/latest/develop/data-types/streams/": "Streams",
                "https://redis.io/docs/latest/develop/data-types/streams/tutorial/": "Streams Tutorial",
                "https://redis.io/docs/latest/develop/data-types/bitmaps/": "Bitmaps",
                "https://redis.io/docs/latest/develop/data-types/bitfields/": "Bitfields",
                "https://redis.io/docs/latest/develop/data-types/geospatial/": "Geospatial",
                # Probabilistic data structures
                "https://redis.io/docs/latest/develop/data-types/probabilistic/": "Probabilistic Overview",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/hyperloglog/": "HyperLogLog",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/bloom-filter/": "Bloom Filter",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/cuckoo-filter/": "Cuckoo Filter",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/count-min-sketch/": "Count-Min Sketch",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/top-k/": "Top-K",
                "https://redis.io/docs/latest/develop/data-types/probabilistic/t-digest/": "t-digest",
                # JSON
                "https://redis.io/docs/latest/develop/data-types/json/": "JSON",
                "https://redis.io/docs/latest/develop/data-types/json/path/": "JSON Path",
                # Time series
                "https://redis.io/docs/latest/develop/data-types/timeseries/": "Time Series",
                "https://redis.io/docs/latest/develop/data-types/timeseries/quickstart/": "Time Series Quickstart",
                "https://redis.io/docs/latest/develop/data-types/timeseries/configuration/": "Time Series Configuration",
                "https://redis.io/docs/latest/develop/data-types/timeseries/development/": "Time Series Development",
                # Getting started guides
                "https://redis.io/docs/latest/develop/get-started/": "Get Started",
                "https://redis.io/docs/latest/develop/get-started/data-store/": "Get Started Data Store",
                "https://redis.io/docs/latest/develop/get-started/document-database/": "Get Started Document Database",
                "https://redis.io/docs/latest/develop/get-started/vector-database/": "Get Started Vector Database",
                # Connect
                "https://redis.io/docs/latest/develop/connect/": "Connect Overview",
                # Interact
                "https://redis.io/docs/latest/develop/interact/transactions/": "Transactions Guide",
                "https://redis.io/docs/latest/develop/interact/pubsub/": "Pub/Sub Guide",
                "https://redis.io/docs/latest/develop/interact/pipelining/": "Pipelining",
                "https://redis.io/docs/latest/develop/interact/keyspace-notifications/": "Keyspace Notifications",
                # Programmability
                "https://redis.io/docs/latest/develop/interact/programmability/": "Programmability Overview",
                "https://redis.io/docs/latest/develop/interact/programmability/eval-intro/": "EVAL Introduction",
                "https://redis.io/docs/latest/develop/interact/programmability/functions-intro/": "Functions Introduction",
                "https://redis.io/docs/latest/develop/interact/programmability/triggers-and-functions/": "Triggers and Functions",
                "https://redis.io/docs/latest/develop/interact/programmability/lua-api/": "Lua API",
            },
        },
        "commands": {
            "pages": {
                # --- String commands ---
                "https://redis.io/docs/latest/commands/set/": "SET",
                "https://redis.io/docs/latest/commands/get/": "GET",
                "https://redis.io/docs/latest/commands/getset/": "GETSET",
                "https://redis.io/docs/latest/commands/mset/": "MSET",
                "https://redis.io/docs/latest/commands/mget/": "MGET",
                "https://redis.io/docs/latest/commands/setnx/": "SETNX",
                "https://redis.io/docs/latest/commands/setex/": "SETEX",
                "https://redis.io/docs/latest/commands/psetex/": "PSETEX",
                "https://redis.io/docs/latest/commands/incr/": "INCR",
                "https://redis.io/docs/latest/commands/incrby/": "INCRBY",
                "https://redis.io/docs/latest/commands/incrbyfloat/": "INCRBYFLOAT",
                "https://redis.io/docs/latest/commands/decr/": "DECR",
                "https://redis.io/docs/latest/commands/decrby/": "DECRBY",
                "https://redis.io/docs/latest/commands/append/": "APPEND",
                "https://redis.io/docs/latest/commands/strlen/": "STRLEN",
                "https://redis.io/docs/latest/commands/getrange/": "GETRANGE",
                "https://redis.io/docs/latest/commands/setrange/": "SETRANGE",
                "https://redis.io/docs/latest/commands/getdel/": "GETDEL",
                "https://redis.io/docs/latest/commands/getex/": "GETEX",
                "https://redis.io/docs/latest/commands/lcs/": "LCS",
                "https://redis.io/docs/latest/commands/msetnx/": "MSETNX",
                "https://redis.io/docs/latest/commands/substr/": "SUBSTR",
                # --- List commands ---
                "https://redis.io/docs/latest/commands/lpush/": "LPUSH",
                "https://redis.io/docs/latest/commands/rpush/": "RPUSH",
                "https://redis.io/docs/latest/commands/lpop/": "LPOP",
                "https://redis.io/docs/latest/commands/rpop/": "RPOP",
                "https://redis.io/docs/latest/commands/llen/": "LLEN",
                "https://redis.io/docs/latest/commands/lrange/": "LRANGE",
                "https://redis.io/docs/latest/commands/lindex/": "LINDEX",
                "https://redis.io/docs/latest/commands/lset/": "LSET",
                "https://redis.io/docs/latest/commands/linsert/": "LINSERT",
                "https://redis.io/docs/latest/commands/lrem/": "LREM",
                "https://redis.io/docs/latest/commands/ltrim/": "LTRIM",
                "https://redis.io/docs/latest/commands/rpoplpush/": "RPOPLPUSH",
                "https://redis.io/docs/latest/commands/lmove/": "LMOVE",
                "https://redis.io/docs/latest/commands/lpos/": "LPOS",
                "https://redis.io/docs/latest/commands/lmpop/": "LMPOP",
                "https://redis.io/docs/latest/commands/blpop/": "BLPOP",
                "https://redis.io/docs/latest/commands/brpop/": "BRPOP",
                "https://redis.io/docs/latest/commands/blmove/": "BLMOVE",
                "https://redis.io/docs/latest/commands/brpoplpush/": "BRPOPLPUSH",
                "https://redis.io/docs/latest/commands/blmpop/": "BLMPOP",
                # --- Set commands ---
                "https://redis.io/docs/latest/commands/sadd/": "SADD",
                "https://redis.io/docs/latest/commands/srem/": "SREM",
                "https://redis.io/docs/latest/commands/smembers/": "SMEMBERS",
                "https://redis.io/docs/latest/commands/sismember/": "SISMEMBER",
                "https://redis.io/docs/latest/commands/smismember/": "SMISMEMBER",
                "https://redis.io/docs/latest/commands/scard/": "SCARD",
                "https://redis.io/docs/latest/commands/spop/": "SPOP",
                "https://redis.io/docs/latest/commands/srandmember/": "SRANDMEMBER",
                "https://redis.io/docs/latest/commands/sinter/": "SINTER",
                "https://redis.io/docs/latest/commands/sinterstore/": "SINTERSTORE",
                "https://redis.io/docs/latest/commands/sintercard/": "SINTERCARD",
                "https://redis.io/docs/latest/commands/sunion/": "SUNION",
                "https://redis.io/docs/latest/commands/sunionstore/": "SUNIONSTORE",
                "https://redis.io/docs/latest/commands/sdiff/": "SDIFF",
                "https://redis.io/docs/latest/commands/sdiffstore/": "SDIFFSTORE",
                "https://redis.io/docs/latest/commands/smove/": "SMOVE",
                # --- Sorted set commands ---
                "https://redis.io/docs/latest/commands/zadd/": "ZADD",
                "https://redis.io/docs/latest/commands/zrem/": "ZREM",
                "https://redis.io/docs/latest/commands/zscore/": "ZSCORE",
                "https://redis.io/docs/latest/commands/zrank/": "ZRANK",
                "https://redis.io/docs/latest/commands/zrevrank/": "ZREVRANK",
                "https://redis.io/docs/latest/commands/zrange/": "ZRANGE",
                "https://redis.io/docs/latest/commands/zrevrange/": "ZREVRANGE",
                "https://redis.io/docs/latest/commands/zrangebyscore/": "ZRANGEBYSCORE",
                "https://redis.io/docs/latest/commands/zrevrangebyscore/": "ZREVRANGEBYSCORE",
                "https://redis.io/docs/latest/commands/zrangebylex/": "ZRANGEBYLEX",
                "https://redis.io/docs/latest/commands/zcount/": "ZCOUNT",
                "https://redis.io/docs/latest/commands/zlexcount/": "ZLEXCOUNT",
                "https://redis.io/docs/latest/commands/zcard/": "ZCARD",
                "https://redis.io/docs/latest/commands/zincrby/": "ZINCRBY",
                "https://redis.io/docs/latest/commands/zpopmin/": "ZPOPMIN",
                "https://redis.io/docs/latest/commands/zpopmax/": "ZPOPMAX",
                "https://redis.io/docs/latest/commands/bzpopmin/": "BZPOPMIN",
                "https://redis.io/docs/latest/commands/bzpopmax/": "BZPOPMAX",
                "https://redis.io/docs/latest/commands/zrandmember/": "ZRANDMEMBER",
                "https://redis.io/docs/latest/commands/zrangestore/": "ZRANGESTORE",
                "https://redis.io/docs/latest/commands/zmscore/": "ZMSCORE",
                "https://redis.io/docs/latest/commands/zinter/": "ZINTER",
                "https://redis.io/docs/latest/commands/zinterstore/": "ZINTERSTORE",
                "https://redis.io/docs/latest/commands/zintercard/": "ZINTERCARD",
                "https://redis.io/docs/latest/commands/zunion/": "ZUNION",
                "https://redis.io/docs/latest/commands/zunionstore/": "ZUNIONSTORE",
                "https://redis.io/docs/latest/commands/zdiff/": "ZDIFF",
                "https://redis.io/docs/latest/commands/zdiffstore/": "ZDIFFSTORE",
                "https://redis.io/docs/latest/commands/zmpop/": "ZMPOP",
                "https://redis.io/docs/latest/commands/bzmpop/": "BZMPOP",
                # --- Hash commands ---
                "https://redis.io/docs/latest/commands/hset/": "HSET",
                "https://redis.io/docs/latest/commands/hget/": "HGET",
                "https://redis.io/docs/latest/commands/hmset/": "HMSET",
                "https://redis.io/docs/latest/commands/hmget/": "HMGET",
                "https://redis.io/docs/latest/commands/hdel/": "HDEL",
                "https://redis.io/docs/latest/commands/hexists/": "HEXISTS",
                "https://redis.io/docs/latest/commands/hlen/": "HLEN",
                "https://redis.io/docs/latest/commands/hkeys/": "HKEYS",
                "https://redis.io/docs/latest/commands/hvals/": "HVALS",
                "https://redis.io/docs/latest/commands/hgetall/": "HGETALL",
                "https://redis.io/docs/latest/commands/hincrby/": "HINCRBY",
                "https://redis.io/docs/latest/commands/hincrbyfloat/": "HINCRBYFLOAT",
                "https://redis.io/docs/latest/commands/hsetnx/": "HSETNX",
                "https://redis.io/docs/latest/commands/hrandfield/": "HRANDFIELD",
                "https://redis.io/docs/latest/commands/hscan/": "HSCAN",
                # --- Key commands ---
                "https://redis.io/docs/latest/commands/del/": "DEL",
                "https://redis.io/docs/latest/commands/exists/": "EXISTS",
                "https://redis.io/docs/latest/commands/expire/": "EXPIRE",
                "https://redis.io/docs/latest/commands/expireat/": "EXPIREAT",
                "https://redis.io/docs/latest/commands/expiretime/": "EXPIRETIME",
                "https://redis.io/docs/latest/commands/ttl/": "TTL",
                "https://redis.io/docs/latest/commands/pttl/": "PTTL",
                "https://redis.io/docs/latest/commands/persist/": "PERSIST",
                "https://redis.io/docs/latest/commands/type/": "TYPE",
                "https://redis.io/docs/latest/commands/rename/": "RENAME",
                "https://redis.io/docs/latest/commands/renamenx/": "RENAMENX",
                "https://redis.io/docs/latest/commands/keys/": "KEYS",
                "https://redis.io/docs/latest/commands/scan/": "SCAN",
                "https://redis.io/docs/latest/commands/randomkey/": "RANDOMKEY",
                "https://redis.io/docs/latest/commands/dump/": "DUMP",
                "https://redis.io/docs/latest/commands/restore/": "RESTORE",
                "https://redis.io/docs/latest/commands/object/": "OBJECT",
                "https://redis.io/docs/latest/commands/touch/": "TOUCH",
                "https://redis.io/docs/latest/commands/unlink/": "UNLINK",
                "https://redis.io/docs/latest/commands/wait/": "WAIT",
                "https://redis.io/docs/latest/commands/copy/": "COPY",
                "https://redis.io/docs/latest/commands/sort/": "SORT",
                "https://redis.io/docs/latest/commands/sort_ro/": "SORT_RO",
                # --- Server commands ---
                "https://redis.io/docs/latest/commands/info/": "INFO",
                "https://redis.io/docs/latest/commands/config-set/": "CONFIG SET",
                "https://redis.io/docs/latest/commands/config-get/": "CONFIG GET",
                "https://redis.io/docs/latest/commands/config-resetstat/": "CONFIG RESETSTAT",
                "https://redis.io/docs/latest/commands/config-rewrite/": "CONFIG REWRITE",
                "https://redis.io/docs/latest/commands/dbsize/": "DBSIZE",
                "https://redis.io/docs/latest/commands/flushdb/": "FLUSHDB",
                "https://redis.io/docs/latest/commands/flushall/": "FLUSHALL",
                "https://redis.io/docs/latest/commands/save/": "SAVE",
                "https://redis.io/docs/latest/commands/bgsave/": "BGSAVE",
                "https://redis.io/docs/latest/commands/bgrewriteaof/": "BGREWRITEAOF",
                "https://redis.io/docs/latest/commands/lastsave/": "LASTSAVE",
                "https://redis.io/docs/latest/commands/time/": "TIME",
                "https://redis.io/docs/latest/commands/slowlog/": "SLOWLOG",
                "https://redis.io/docs/latest/commands/debug/": "DEBUG",
                "https://redis.io/docs/latest/commands/memory-usage/": "MEMORY USAGE",
                "https://redis.io/docs/latest/commands/memory-doctor/": "MEMORY DOCTOR",
                "https://redis.io/docs/latest/commands/client-list/": "CLIENT LIST",
                "https://redis.io/docs/latest/commands/client-setname/": "CLIENT SETNAME",
                "https://redis.io/docs/latest/commands/client-getname/": "CLIENT GETNAME",
                "https://redis.io/docs/latest/commands/client-id/": "CLIENT ID",
                "https://redis.io/docs/latest/commands/client-kill/": "CLIENT KILL",
                "https://redis.io/docs/latest/commands/client-pause/": "CLIENT PAUSE",
                "https://redis.io/docs/latest/commands/client-unpause/": "CLIENT UNPAUSE",
                "https://redis.io/docs/latest/commands/client-no-evict/": "CLIENT NO-EVICT",
                "https://redis.io/docs/latest/commands/command/": "COMMAND",
                "https://redis.io/docs/latest/commands/command-count/": "COMMAND COUNT",
                "https://redis.io/docs/latest/commands/command-info/": "COMMAND INFO",
                "https://redis.io/docs/latest/commands/command-docs/": "COMMAND DOCS",
                "https://redis.io/docs/latest/commands/command-list/": "COMMAND LIST",
                "https://redis.io/docs/latest/commands/acl-list/": "ACL LIST",
                "https://redis.io/docs/latest/commands/acl-setuser/": "ACL SETUSER",
                "https://redis.io/docs/latest/commands/acl-deluser/": "ACL DELUSER",
                "https://redis.io/docs/latest/commands/acl-getuser/": "ACL GETUSER",
                "https://redis.io/docs/latest/commands/acl-whoami/": "ACL WHOAMI",
                "https://redis.io/docs/latest/commands/acl-log/": "ACL LOG",
                "https://redis.io/docs/latest/commands/acl-cat/": "ACL CAT",
                "https://redis.io/docs/latest/commands/acl-genpass/": "ACL GENPASS",
                "https://redis.io/docs/latest/commands/acl-load/": "ACL LOAD",
                "https://redis.io/docs/latest/commands/acl-save/": "ACL SAVE",
                "https://redis.io/docs/latest/commands/module-load/": "MODULE LOAD",
                "https://redis.io/docs/latest/commands/module-list/": "MODULE LIST",
                "https://redis.io/docs/latest/commands/module-unload/": "MODULE UNLOAD",
                "https://redis.io/docs/latest/commands/swapdb/": "SWAPDB",
                "https://redis.io/docs/latest/commands/shutdown/": "SHUTDOWN",
                "https://redis.io/docs/latest/commands/replicaof/": "REPLICAOF",
                "https://redis.io/docs/latest/commands/failover/": "FAILOVER",
                "https://redis.io/docs/latest/commands/cluster-info/": "CLUSTER INFO",
                "https://redis.io/docs/latest/commands/cluster-nodes/": "CLUSTER NODES",
                "https://redis.io/docs/latest/commands/cluster-meet/": "CLUSTER MEET",
                "https://redis.io/docs/latest/commands/cluster-addslots/": "CLUSTER ADDSLOTS",
                "https://redis.io/docs/latest/commands/cluster-delslots/": "CLUSTER DELSLOTS",
                "https://redis.io/docs/latest/commands/cluster-setslot/": "CLUSTER SETSLOT",
                "https://redis.io/docs/latest/commands/cluster-replicate/": "CLUSTER REPLICATE",
                "https://redis.io/docs/latest/commands/cluster-failover/": "CLUSTER FAILOVER",
                "https://redis.io/docs/latest/commands/cluster-reset/": "CLUSTER RESET",
                "https://redis.io/docs/latest/commands/cluster-slots/": "CLUSTER SLOTS",
                "https://redis.io/docs/latest/commands/cluster-shards/": "CLUSTER SHARDS",
                "https://redis.io/docs/latest/commands/cluster-myid/": "CLUSTER MYID",
                # --- Stream commands ---
                "https://redis.io/docs/latest/commands/xadd/": "XADD",
                "https://redis.io/docs/latest/commands/xread/": "XREAD",
                "https://redis.io/docs/latest/commands/xrange/": "XRANGE",
                "https://redis.io/docs/latest/commands/xrevrange/": "XREVRANGE",
                "https://redis.io/docs/latest/commands/xlen/": "XLEN",
                "https://redis.io/docs/latest/commands/xtrim/": "XTRIM",
                "https://redis.io/docs/latest/commands/xdel/": "XDEL",
                "https://redis.io/docs/latest/commands/xinfo/": "XINFO",
                "https://redis.io/docs/latest/commands/xgroup-create/": "XGROUP CREATE",
                "https://redis.io/docs/latest/commands/xgroup-destroy/": "XGROUP DESTROY",
                "https://redis.io/docs/latest/commands/xgroup-setid/": "XGROUP SETID",
                "https://redis.io/docs/latest/commands/xgroup-delconsumer/": "XGROUP DELCONSUMER",
                "https://redis.io/docs/latest/commands/xreadgroup/": "XREADGROUP",
                "https://redis.io/docs/latest/commands/xack/": "XACK",
                "https://redis.io/docs/latest/commands/xclaim/": "XCLAIM",
                "https://redis.io/docs/latest/commands/xautoclaim/": "XAUTOCLAIM",
                "https://redis.io/docs/latest/commands/xpending/": "XPENDING",
                # --- Pub/Sub commands ---
                "https://redis.io/docs/latest/commands/subscribe/": "SUBSCRIBE",
                "https://redis.io/docs/latest/commands/unsubscribe/": "UNSUBSCRIBE",
                "https://redis.io/docs/latest/commands/publish/": "PUBLISH",
                "https://redis.io/docs/latest/commands/psubscribe/": "PSUBSCRIBE",
                "https://redis.io/docs/latest/commands/punsubscribe/": "PUNSUBSCRIBE",
                "https://redis.io/docs/latest/commands/pubsub/": "PUBSUB",
                # --- Scripting commands ---
                "https://redis.io/docs/latest/commands/eval/": "EVAL",
                "https://redis.io/docs/latest/commands/evalsha/": "EVALSHA",
                "https://redis.io/docs/latest/commands/evalro/": "EVALRO",
                "https://redis.io/docs/latest/commands/script-load/": "SCRIPT LOAD",
                "https://redis.io/docs/latest/commands/script-exists/": "SCRIPT EXISTS",
                "https://redis.io/docs/latest/commands/script-flush/": "SCRIPT FLUSH",
                "https://redis.io/docs/latest/commands/script-kill/": "SCRIPT KILL",
                "https://redis.io/docs/latest/commands/function-load/": "FUNCTION LOAD",
                "https://redis.io/docs/latest/commands/function-delete/": "FUNCTION DELETE",
                "https://redis.io/docs/latest/commands/function-list/": "FUNCTION LIST",
                "https://redis.io/docs/latest/commands/function-dump/": "FUNCTION DUMP",
                "https://redis.io/docs/latest/commands/function-restore/": "FUNCTION RESTORE",
                "https://redis.io/docs/latest/commands/function-stats/": "FUNCTION STATS",
                "https://redis.io/docs/latest/commands/fcall/": "FCALL",
                "https://redis.io/docs/latest/commands/fcall_ro/": "FCALL_RO",
                # --- Transaction commands ---
                "https://redis.io/docs/latest/commands/multi/": "MULTI",
                "https://redis.io/docs/latest/commands/exec/": "EXEC",
                "https://redis.io/docs/latest/commands/discard/": "DISCARD",
                "https://redis.io/docs/latest/commands/watch/": "WATCH",
                "https://redis.io/docs/latest/commands/unwatch/": "UNWATCH",
                # --- Geo commands ---
                "https://redis.io/docs/latest/commands/geoadd/": "GEOADD",
                "https://redis.io/docs/latest/commands/geodist/": "GEODIST",
                "https://redis.io/docs/latest/commands/geohash/": "GEOHASH",
                "https://redis.io/docs/latest/commands/geopos/": "GEOPOS",
                "https://redis.io/docs/latest/commands/georadius/": "GEORADIUS",
                "https://redis.io/docs/latest/commands/georadiusbymember/": "GEORADIUSBYMEMBER",
                "https://redis.io/docs/latest/commands/geosearch/": "GEOSEARCH",
                "https://redis.io/docs/latest/commands/geosearchstore/": "GEOSEARCHSTORE",
                # --- HyperLogLog commands ---
                "https://redis.io/docs/latest/commands/pfadd/": "PFADD",
                "https://redis.io/docs/latest/commands/pfcount/": "PFCOUNT",
                "https://redis.io/docs/latest/commands/pfmerge/": "PFMERGE",
                "https://redis.io/docs/latest/commands/pfdebug/": "PFDEBUG",
                # --- Connection commands ---
                "https://redis.io/docs/latest/commands/auth/": "AUTH",
                "https://redis.io/docs/latest/commands/ping/": "PING",
                "https://redis.io/docs/latest/commands/echo/": "ECHO",
                "https://redis.io/docs/latest/commands/select/": "SELECT",
                "https://redis.io/docs/latest/commands/quit/": "QUIT",
                "https://redis.io/docs/latest/commands/reset/": "RESET",
                "https://redis.io/docs/latest/commands/hello/": "HELLO",
                "https://redis.io/docs/latest/commands/client/": "CLIENT",
            },
        },
        "management": {
            "pages": {
                # Management overview
                "https://redis.io/docs/latest/operate/oss_and_stack/management/": "Management Overview",
                # Installation
                "https://redis.io/docs/latest/operate/oss_and_stack/install/": "Installation Overview",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/": "Install Redis",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-linux/": "Install Redis on Linux",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-mac-os/": "Install Redis on macOS",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-on-windows/": "Install Redis on Windows",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/install-redis-from-source/": "Install Redis from Source",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/": "Install Redis Stack",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/docker/": "Install Redis Stack Docker",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/linux/": "Install Redis Stack Linux",
                "https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/mac-os/": "Install Redis Stack macOS",
                # Persistence
                "https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/": "Persistence",
                # Replication
                "https://redis.io/docs/latest/operate/oss_and_stack/management/replication/": "Replication",
                # Sentinel
                "https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/": "Sentinel",
                # Cluster
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/": "Cluster Specification",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/": "Scaling with Cluster",
                # Security
                "https://redis.io/docs/latest/operate/oss_and_stack/management/security/": "Security Overview",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/": "Access Control Lists",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/security/encryption/": "Encryption",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/security/tls/": "TLS Support",
                # Configuration
                "https://redis.io/docs/latest/operate/oss_and_stack/management/config/": "Configuration",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/config-file/": "Configuration File",
                # Optimization
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/": "Optimization Overview",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/": "Memory Optimization",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/": "Latency",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency-monitor/": "Latency Monitor",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/benchmarks/": "Benchmarks",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/cpu-profiling/": "CPU Profiling",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/data-optimization/": "Data Optimization",
                # Administration
                "https://redis.io/docs/latest/operate/oss_and_stack/management/admin/": "Administration",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/cli/": "Redis CLI",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/debugging/": "Debugging",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/troubleshooting/": "Troubleshooting",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/diagnostics/": "Diagnostics",
                "https://redis.io/docs/latest/operate/oss_and_stack/management/upgrade/": "Upgrading Redis",
                # Reference
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/": "Operate Reference Overview",
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/internals/": "Redis Internals",
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/signals/": "Signal Handling",
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/clients-handling/": "Client Handling",
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/modules-api-ref/": "Modules API Reference",
                "https://redis.io/docs/latest/operate/oss_and_stack/reference/arm/": "ARM Support",
                # Redis on Kubernetes
                "https://redis.io/docs/latest/operate/kubernetes/": "Redis on Kubernetes",
                "https://redis.io/docs/latest/operate/kubernetes/deployment/": "Kubernetes Deployment",
                "https://redis.io/docs/latest/operate/kubernetes/architecture/": "Kubernetes Architecture",
                # Redis Cloud
                "https://redis.io/docs/latest/operate/rc/": "Redis Cloud Overview",
                "https://redis.io/docs/latest/operate/rc/databases/": "Redis Cloud Databases",
                "https://redis.io/docs/latest/operate/rc/security/": "Redis Cloud Security",
                "https://redis.io/docs/latest/operate/rc/api/": "Redis Cloud API",
                # Redis Software
                "https://redis.io/docs/latest/operate/rs/": "Redis Software Overview",
                "https://redis.io/docs/latest/operate/rs/databases/": "Redis Software Databases",
                "https://redis.io/docs/latest/operate/rs/clusters/": "Redis Software Clusters",
                "https://redis.io/docs/latest/operate/rs/security/": "Redis Software Security",
                "https://redis.io/docs/latest/operate/rs/references/": "Redis Software References",
            },
        },
        "clients": {
            "pages": {
                # Client overview
                "https://redis.io/docs/latest/develop/clients/": "Client Libraries Overview",
                # Java
                "https://redis.io/docs/latest/develop/clients/jedis/": "Jedis (Java)",
                "https://redis.io/docs/latest/develop/clients/jedis/connect/": "Jedis Connect",
                "https://redis.io/docs/latest/develop/clients/lettuce/": "Lettuce (Java)",
                "https://redis.io/docs/latest/develop/clients/lettuce/connect/": "Lettuce Connect",
                # Python
                "https://redis.io/docs/latest/develop/clients/redis-py/": "redis-py (Python)",
                "https://redis.io/docs/latest/develop/clients/redis-py/connect/": "redis-py Connect",
                # Node.js
                "https://redis.io/docs/latest/develop/clients/nodejs/": "node-redis (Node.js)",
                "https://redis.io/docs/latest/develop/clients/nodejs/connect/": "node-redis Connect",
                # Go
                "https://redis.io/docs/latest/develop/clients/go/": "go-redis (Go)",
                "https://redis.io/docs/latest/develop/clients/go/connect/": "go-redis Connect",
                # .NET
                "https://redis.io/docs/latest/develop/clients/dotnet/": ".NET Client",
                "https://redis.io/docs/latest/develop/clients/dotnet/connect/": ".NET Connect",
                # PHP
                "https://redis.io/docs/latest/develop/clients/php/": "PHP Client",
                "https://redis.io/docs/latest/develop/clients/php/connect/": "PHP Connect",
                # Rust
                "https://redis.io/docs/latest/develop/clients/rust/": "Rust Client",
                "https://redis.io/docs/latest/develop/clients/rust/connect/": "Rust Connect",
                # Ruby
                "https://redis.io/docs/latest/develop/clients/ruby/": "Ruby Client",
                "https://redis.io/docs/latest/develop/clients/ruby/connect/": "Ruby Connect",
                # C
                "https://redis.io/docs/latest/develop/clients/hiredis/": "hiredis (C)",
                # CLI
                "https://redis.io/docs/latest/develop/tools/cli/": "Redis CLI Tool",
                "https://redis.io/docs/latest/develop/tools/insight/": "Redis Insight",
            },
        },
        "stack": {
            "pages": {
                # Search and Query (RediSearch)
                "https://redis.io/docs/latest/develop/interact/search-and-query/": "Search and Query Overview",
                "https://redis.io/docs/latest/develop/interact/search-and-query/indexing/": "Search Indexing",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/": "Query Syntax",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/full-text/": "Full-Text Search",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/range/": "Range Queries",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/geo-spatial/": "Geo-Spatial Queries",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/aggregation/": "Aggregation",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/vector-search/": "Vector Search",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/exact-match/": "Exact Match",
                "https://redis.io/docs/latest/develop/interact/search-and-query/query/combined/": "Combined Queries",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/": "Search Advanced Concepts",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/vectors/": "Vector Similarity",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/dialects/": "Query Dialects",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/stemming/": "Stemming",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/scoring/": "Scoring",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/tags/": "Tag Queries",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/stopwords/": "Stopwords",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/aggregations/": "Aggregation Pipeline",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/autocomplete/": "Autocomplete",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/escaping/": "Query Escaping",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/highlight/": "Search Highlight",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/phonetic/": "Phonetic Matching",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/spellcheck/": "Spellcheck",
                "https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/synonyms/": "Synonyms",
                "https://redis.io/docs/latest/develop/interact/search-and-query/indexing/schema-definition/": "Schema Definition",
                # JSON (RedisJSON)
                "https://redis.io/docs/latest/develop/data-types/json/path/": "JSON Path Syntax",
                # Probabilistic (Bloom, Cuckoo, etc.)
                "https://redis.io/docs/latest/develop/data-types/probabilistic/configuration/": "Probabilistic Config",
                # Time Series (RedisTimeSeries)
                "https://redis.io/docs/latest/develop/data-types/timeseries/configuration/": "TimeSeries Config",
            },
        },
        "reference": {
            "pages": {
                # Protocol and internals
                "https://redis.io/docs/latest/develop/reference/protocol-spec/": "Protocol Specification (RESP)",
                "https://redis.io/docs/latest/develop/reference/patterns/": "Patterns",
                "https://redis.io/docs/latest/develop/reference/eviction/": "Key Eviction",
                "https://redis.io/docs/latest/develop/reference/signals/": "Signals",
                "https://redis.io/docs/latest/develop/reference/notifications/": "Keyspace Notifications Reference",
                "https://redis.io/docs/latest/develop/reference/key-specs/": "Key Specifications",
                "https://redis.io/docs/latest/develop/reference/modules-api/": "Modules API",
                "https://redis.io/docs/latest/develop/reference/cluster-spec/": "Cluster Specification",
                "https://redis.io/docs/latest/develop/reference/sentinel-clients/": "Sentinel Clients",
                "https://redis.io/docs/latest/develop/reference/arm/": "ARM Support",
                # Use patterns
                "https://redis.io/docs/latest/develop/use/patterns/indexes/": "Secondary Indexes",
                "https://redis.io/docs/latest/develop/use/patterns/bulk-loading/": "Bulk Loading",
                "https://redis.io/docs/latest/develop/use/patterns/distributed-locks/": "Distributed Locks",
                # Clients patterns
                "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/": "Redlock Algorithm",
                "https://redis.io/docs/latest/develop/clients/patterns/": "Client Patterns",
                # About
                "https://redis.io/docs/latest/develop/reference/": "Reference Overview",
                "https://redis.io/docs/latest/develop/reference/optimization/": "Performance Optimization",
                "https://redis.io/docs/latest/about/": "About Redis",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"redis-{source_key}" if source_key else "redis"
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
            for suffix in [' | Redis', ' - Redis', ' | Docs']:
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
                        "category": f"redis-{source_key}",
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
            self.log.info(f"=== Scraping redis/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RedisScraper(base, source_key).run()
