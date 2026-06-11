---
name: haskell
description: "Haskell pure functional language - lazy evaluation, Hindley-Milner types, monads, GHC, STM"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 941c18ed-6047-4a54-b8ec-32b15a9a92d1
---

# Haskell Programming Language

**Research Date:** 2026-06-11  
**Sources:** Official Haskell documentation, GHC User's Guide, academic papers  
**Verification:** 104 agent calls, 12 high-confidence findings through 3-vote adversarial validation  
**Code Analysis:** GHC runtime system (15 critical C/Haskell files analyzed)

## What is Haskell?

Haskell is a **pure lazy functional programming language** designed by committee starting at the FPCA meeting in September 1987 in Portland, Oregon.

**Key Decision:** Committee chose to create a new standard language rather than standardizing an existing one like Miranda.

## Core Features

### 1. Lazy Evaluation

**Call-by-need mechanism:**
- Expressions evaluated only when necessary
- Results shared to avoid duplicate computation
- Creates thunks (unevaluated expressions) on heap

**Performance trade-offs:**
- Conditional branching disrupts pipelined processors
- Unpredictable memory usage patterns
- Cache misses from indirection
- GHC uses strictness analysis to mitigate costs

**Implementation (from GHC source):**
```c
// Thunk representation (rts/include/rts/storage/Closures.h)
typedef struct StgThunk_ {
    StgThunkHeader  header;  // Contains indirectee field
    struct StgClosure_ *payload[];
} StgThunk;

// Update protocol: thunk → BLACKHOLE → indirection
// Lazy blackholing: only blackhole when thread yields
```

### 2. Type System - Extended Hindley-Milner

**Automatic type inference:**
- No type annotations required
- Infers most general (principal) type uniquely
- Polymorphism restricted to let-bound variables (not lambda parameters)

**Why restriction matters:**
```haskell
-- Works: let-binding generalized
let f = \x -> x in (f True, f 3)  -- OK

-- Fails: lambda-bound must be monomorphic  
(\f -> (f True, f 3)) (\x -> x)   -- Type error
```

**Type classes:**
- Provide systematic overloading
- Require modified algorithm W for qualified types
- Enable ad-hoc polymorphism while maintaining inference

### 3. GHC Compiler

**Optimization levels:**
- **-O/-O1:** Good quality code without long compile times
- **-O2:** Every non-dangerous optimization, 15-30% runtime improvement

**Demand analysis:**
- Combines strictness analysis (evaluated at least once) + usage analysis (at most once)
- Enables call-by-value for strict arguments
- Pass unboxed parameters
- Avoids thunk allocation overhead

**Common Subexpression Elimination (CSE):**
- GHC does NOT perform full CSE
- Reasons: (1) causes space leaks, (2) replaces strict calls with lazy thunks
- Only "opportunistic CSE" to avoid changing strictness/laziness

### 4. Software Transactional Memory (STM)

**Key advantage: Composability**
- Small transactions compose into larger transactions
- Abstractions don't expose internal safety mechanisms
- Built-in primitives: \`atomically\`, \`retry\`, \`orElse\`

**Implementation (from GHC source):**
```c
// TVar locking via CAS (rts/STM.c)
static StgClosure *lock_tvar(Capability *cap, StgTRecHeader *trec, StgTVar *s) {
  do {
    result = ACQUIRE_LOAD(&s->current_value);
    info = GET_INFO(UNTAG_CLOSURE(result));
  } while (info == &stg_TREC_HEADER_info);  // Spin if locked
  
  // CAS to acquire lock
  while (cas((void *) &s->current_value, (StgWord)result, (StgWord)trec) 
         != (StgWord)result);
  return result;
}

// Transaction log stores expected/new values per TVar
// Validation: lock all written TVars, check all read TVars match expected
```

### 5. IO Monad

**Encapsulation of side effects:**
- Pure functions: cannot perform I/O
- IO monad: encapsulates impure actions
- Type system enforces separation

**Pattern:**
```haskell
main :: IO ()
main = do
    putStrLn "Enter name:"
    name <- getLine
    putStrLn ("Hello, " ++ name)
```

## GHC Runtime System Architecture

### Green Thread Scheduler

**Thread State Object (TSO):**
```c
typedef struct StgTSO_ {
    StgHeader               header;
    struct StgTSO_*         _link;      // Run queue linkage
    struct StgStack_       *stackobj;   // Separate stack object
    StgWord32               why_blocked; // BlockedOnSTM, BlockedOnMVar...
    struct StgTRecHeader_ * trec;       // STM transaction record
} StgTSO;
```

**Scheduling:**
- Round-robin with capability-local run queues
- Work stealing from idle capabilities
- Separate stacks (not inline with TSO)

### Garbage Collection

**Generational copying collector:**
- Parallel GC with per-thread workspaces
- Stop-the-world synchronization
- Parallel evacuation: CAS on info pointer to claim ownership
- Card marking for old-gen mutable arrays

**Evacuation pattern:**
```c
// Atomic CAS to claim copy ownership
new_info = cas(&src->header.info, (W_)info, MK_FORWARDING_PTR(to));
if (new_info != info) {
    return evacuate(p);  // Lost race, follow forwarding pointer
}
```

## Performance Characteristics

**Challenges:**
- Thunks require heap allocation
- Indirection causes cache misses
- Unpredictable memory patterns
- Branch misprediction from lazy evaluation

**Optimizations:**
- Strictness annotations (\`!\` bang patterns)
- UNPACK pragmas for strict fields
- Manual forcing with \`seq\` or \`deepseq\`
- GHC demand analysis eliminates unnecessary thunks

## Major Use Cases

1. **Pandoc** - Universal document converter
2. **Xmonad** - Tiling window manager
3. **Financial systems** - Type safety for correctness
4. **Compilers** - GHC itself, PureScript compiler
5. **Web servers** - Yesod, Servant frameworks

## Comparison to Other Functional Languages

| Feature | Haskell | OCaml | Scala |
|---------|---------|-------|-------|
| Evaluation | Lazy (default) | Strict (default) | Strict (default) |
| Purity | Pure (enforced) | Impure (mixed) | Impure (mixed) |
| Type System | HM + type classes | HM + objects | Nominal + subtyping |
| Concurrency | STM, green threads | Multicore OCaml 5 | JVM threads, Akka actors |
| Compiler | GHC | OCaml native | Scalac → JVM bytecode |

## Caveats

- Lazy evaluation creates performance unpredictability
- Learning curve steep due to pure functional + lazy + advanced types
- Ecosystem smaller than mainstream languages
- Debugging harder with thunks and lazy evaluation
- Not ideal for real-time systems (GC pauses, unpredictable evaluation)

**Sources:** Official Haskell documentation (haskell.org), GHC User's Guide (ghc.gitlab.haskell.org), Simon Peyton Jones retrospective paper, GHC source code analysis (rts/STM.c, rts/Schedule.c, rts/storage/Closures.h).
