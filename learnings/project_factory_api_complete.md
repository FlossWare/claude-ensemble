---
name: factory-api-complete
description: Factory-based instance creation API completed May 2026
metadata: 
  node_type: memory
  type: project
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

Completed major refactoring from string-based service lookup to factory-based instance creation API (May 15, 2026).

**Why:** String-based IDs were error-prone and didn't support dynamic instance creation. New API works like `new Foo()` instead of string lookup.

**How to apply:** 
- Server: `JRemoteServer.builder().registerFactory(UserService.class, UserServiceImpl.class).build()`
- Client: `UserService user = client.create(UserService.class)`
- Supports constructor arguments: `client.create(OrderService.class, "arg1", 123)`
- Instance lifecycle: explicit `destroy()` or auto-cleanup on `close()`
- All tests updated (75 total), README.md fully rewritten
- Old string-based API completely removed (no backward compatibility needed)
