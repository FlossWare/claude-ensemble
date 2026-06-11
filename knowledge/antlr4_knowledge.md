# ANTLR4 Repository: Complete Architecture Analysis

## Project Overview
ANTLR (Another Language Recognition Tool) v4 is a widely-used parser generator framework that enables developers to define context-free grammars in `.g4` files and automatically generate parsers, lexers, and tree visitors/listeners in multiple programming languages (Java, Python, C++, C#, JavaScript, Go, etc.).

**Repository:** https://github.com/antlr/antlr4
**Primary Language:** Java
**Build Tool:** Maven
**License:** BSD 3-Clause

## Directory Structure

```
antlr4/
├── tool/                          # ANTLR grammar compiler & code generator
│   ├── src/org/antlr/v4/
│   │   ├── Tool.java              # Entry point
│   │   ├── codegen/               # Code generation pipeline
│   │   ├── parse/                 # Grammar parsing (ANTLR self-parsing)
│   │   ├── semantics/             # Semantic analysis
│   │   ├── analysis/              # Grammar analysis
│   │   └── automata/              # ATN construction
│   └── test/
│
├── runtime/                        # Target language runtimes
│   └── Java/
│       └── src/org/antlr/v4/runtime/
│           ├── Parser.java        # Parser base class
│           ├── Lexer.java         # Lexer base class
│           ├── Recognizer.java    # Generic recognizer base
│           ├── atn/               # Augmented Transition Network
│           ├── dfa/               # Deterministic Finite Automaton
│           ├── tree/              # Parse tree structures
│           │   ├── ParseTree.java
│           │   ├── ParseTreeListener.java
│           │   ├── ParseTreeVisitor.java
│           │   └── ParseTreeWalker.java
│           ├── misc/              # Utilities (IntervalSet, IntegerStack)
│           └── error/             # Error handling
│
├── runtime-testsuite/             # Runtime validation tests
├── tool-testsuite/                # Tool and generation tests
├── antlr4-maven-plugin/           # Maven integration
├── doc/                           # Documentation
└── pom.xml                        # Maven build configuration
```

## Core Architecture: 7 Key Systems

### 1. GRAMMAR COMPILATION PIPELINE

**Flow:**
```
.g4 Grammar File
  ↓ [ToolANTLRLexer/Parser] - Self-hosted parsing
Grammar AST
  ↓ [GrammarTransformPipeline] - Normalize & validate
Transformed AST
  ↓ [SemanticPipeline] - Symbol resolution, type checking
Annotated AST
  ↓ [AnalysisPipeline] - Conflict detection, LL analysis
Analyzed Grammar
  ↓ [ParserATNFactory/LexerATNFactory] - State machine generation
ATN (Augmented Transition Network)
  ↓ [ATNSerializer] - Compact binary representation
Serialized ATN
  ↓ [CodeGenPipeline] - Template-based code generation
Target Language Source Code (.java, .py, etc.)
```

**Key Classes:**
- `Tool` - CLI entry point, coordinates all pipelines
- `CodeGenPipeline` - Orchestrates code generation phases
- `CodeGenerator` - Uses StringTemplate v4 for target language templates
- `GrammarTransformPipeline` - Grammar normalization
- `SemanticPipeline` - Validates grammar semantics
- `AnalysisPipeline` - Detects ambiguities and conflicts
- `ParserATNFactory` - Converts grammar rules → ATN
- `LexerATNFactory` - Converts lexer rules → ATN

### 2. RUNTIME RECOGNIZER HIERARCHY

**Generic Architecture:**
```java
Recognizer<Symbol, ATNInterpreter>  // Generic base
  ├── Parser extends Recognizer<Token, ParserATNSimulator>
  └── Lexer extends Recognizer<Integer, LexerATNSimulator>
```

**Recognizer (Base Class)**
- Maintains vocabulary and rule names
- Caches token type maps (WeakHashMap for memory efficiency)
- Manages error listeners (thread-safe CopyOnWriteArrayList)
- Provides ATN access and serialization
- Generic design enables multi-language target support

**Parser (Concrete Subclass)**
```java
protected TokenStream _input;              // Token buffer
protected ParserRuleContext _ctx;          // Current rule context (stack)
protected IntegerStack _precedenceStack;   // For precedence parsing
protected ANTLRErrorStrategy _errHandler;  // Error recovery strategy
protected List<ParseTreeListener> _parseListeners;
protected boolean _buildParseTrees;        // Enable/disable tree building
```

**Key Methods:**
- `match(int ttype)` - Consume expected token
- `matchWildcard()` - Match any token
- `sempred(...)` - Semantic predicate evaluation
- `precpred(...)` - Precedence comparison
- `getRuleIndex(String ruleName)` - Rule lookup

### 3. AUGMENTED TRANSITION NETWORK (ATN) SYSTEM

**ATN Concepts:**
- Unified state machine representation for both parsers and lexers
- Supports epsilon transitions, semantic predicates, actions
- Serialized compactly for distribution with generated code
- Interpreted at runtime for flexible parsing

**Core Classes:**

**ATN** - Main network structure
```java
List<ATNState> states;                    // All states
List<DecisionState> decisionToState;      // Rule alternatives & blocks
RuleStartState[] ruleToStartState;        // Entry points
RuleStopState[] ruleToStopState;          // Exit points
Map<String, TokensStartState> modeNameToStartState;  // Lexer modes
int[] ruleToTokenType;                    // Lexer rule → token type
LexerAction[] lexerActions;               // Lexer semantic actions
```

**ATNState Hierarchy:**
```
ATNState (base)
  ├── RuleStartState     - Entry to rule, no incoming transitions
  ├── RuleStopState      - Exit from rule
  ├── DecisionState      - Point of non-determinism
  │   ├── StarLoopEntryState
  │   ├── StarLoopbackState
  │   ├── PlusLoopbackState
  │   └── (Other loop variants)
  ├── BlockStartState    - (a|b) blocks
  ├── TokensStartState   - Lexer mode entry
  └── (Various others)
```

**Transitions (Edges):**
```
Transition (base)
  ├── EpsilonTransition      - No input consumed (ε)
  ├── RangeTransition        - [a-z]
  ├── SetTransition          - {a,b,c}
  ├── AtomTransition         - Single token/char
  ├── RuleTransition         - Invoke subrule
  ├── PredicateTransition    - Semantic predicate {p}?
  ├── ActionTransition       - Side effect
  └── WildcardTransition     - Any token/char
```

**ATN Simulation:**
- `ParserATNSimulator` - Interprets ATN during parsing
- `LexerATNSimulator` - Lexer version
- Both support:
  - Predictive parsing (lookahead)
  - Adaptive prediction (SLL then LL)
  - Conflict detection
  - Semantic predicate evaluation

### 4. DETERMINISTIC FINITE AUTOMATON (DFA) CACHING

**Purpose:** Optimize ATN interpretation through memoization

**DFA Structure:**
```java
class DFAState {
  int stateNumber;
  ATNConfigSet configs;           // Underlying ATN configs
  Map<Integer, DFAState> edges;   // Transition map: symbol → state
  boolean isAcceptState;
  int prediction;                 // Memoized prediction (if determined)
  SemanticContext semanticContext;// Semantic predicate context
}

class DFA {
  int decision;                   // Which decision point
  DFAState s0;                    // Start state
  Map<Integer, DFAState> states;  // All reachable states
  Set<ATNConfigSet> precedenceGraphs;
}
```

**Lazy Construction:**
- DFA states created on-demand during parsing
- First parse builds DFA states incrementally
- Subsequent parses reuse memoized states
- Dramatic performance improvement for repeated parsing

### 5. PARSE TREE ARCHITECTURE

**Tree Node Types:**
```
ParseTree (interface)
  ├── RuleNode
  │   └── ParserRuleContext
  │       ├── symbol - Usually null for context
  │       ├── exception - Parse errors
  │       ├── children - Child nodes
  │       ├── parser - Backref to parser
  │       ├── invokingState - Parser state when rule entered
  │       └── start/stop tokens
  │
  ├── TerminalNode
  │   └── TerminalNodeImpl
  │       └── symbol - Token
  │
  └── ErrorNode
      └── ErrorNodeImpl
          └── symbol - Error token
```

**Traversal Pattern: Listener (Event-Driven)**
```java
interface ParseTreeListener {
  void visitTerminal(TerminalNode node);
  void visitErrorNode(ErrorNode node);
  void enterEveryRule(ParserRuleContext ctx);
  void exitEveryRule(ParserRuleContext ctx);
}

class ParseTreeWalker {
  void walk(ParseTreeListener listener, ParseTree t) {
    // Depth-first, left-to-right traversal
    // Fires enter/exit events
  }
}
```

**Traversal Pattern: Visitor (Return Values)**
```java
interface ParseTreeVisitor<T> {
  T visit(ParseTree tree);
  T visitChildren(RuleNode node);
  T visitTerminal(TerminalNode node);
  T visitErrorNode(ErrorNode node);
}

abstract class AbstractParseTreeVisitor<T> implements ParseTreeVisitor<T> {
  // Provides default implementations
  // Subclasses override specific rule visit methods
  // Generated code: visitProgram(), visitStatement(), etc.
}
```

**Code Generation for Trees:**
Generated parser creates grammar-specific visitor/listener:
```java
interface ProgramVisitor<T> extends ParseTreeVisitor<T> {
  T visitProgram(ProgramContext ctx);
  T visitStatement(StatementContext ctx);
  // ... one method per rule
}

class ProgramBaseVisitor<T> extends AbstractParseTreeVisitor<T> 
  implements ProgramVisitor<T> {
  // Default implementations
}
```

### 6. LEXER & TOKEN SYSTEMS

**Token Production:**
```
Input Stream (CharStream)
  ↓ [Lexer] - Recognizes tokens using ATN
TokenSource (interface)
  ↓ [TokenStream] - Buffers tokens
Token Array
  ├── Token.type - Token type ID
  ├── Token.text - Token text
  ├── Token.line - Line number
  ├── Token.column - Column offset
  ├── Token.start - Input stream index
  └── Token.stop - Input stream end index
```

**Token Stream Implementations:**
- `BufferedTokenStream` - Full input buffering
- `UnbufferedTokenStream` - Single-token lookahead
- `TokenStreamRewriter` - Modify tokens dynamically

**Lexer Modes (Context-Sensitive Lexing):**
```java
// Example: MODE names for different context lexing
lexer grammar MyLexer;

tokens { REGULAR }
mode STRING_MODE;
STRING_CONTENT: ~'"' -> mode(DEFAULT_MODE);
mode DEFAULT_MODE;
STRING: '"' -> mode(STRING_MODE);
```

ATN supports:
- Multiple lexer modes (each with TokensStartState)
- Mode transitions via actions
- Context-aware token production

### 7. ERROR HANDLING & RECOVERY

**Error Strategy Interface:**
```java
interface ANTLRErrorStrategy {
  void reset(Parser recognizer);
  Token recoverInline(Parser recognizer) throws RecognitionException;
  void recover(Parser recognizer, RecognitionException e);
  void sync(Parser recognizer) throws RecognitionException;
  boolean sempred(Parser recognizer, int ruleIndex, int predIndex);
  void reportError(Parser recognizer, RecognitionException e);
}
```

**Default Error Strategy:**
- **Single token deletion** - Skip unexpected token
- **Single token insertion** - Assume missing token
- **Token matching with recovery** - Continue parsing
- **Synchronization** - Recover to decision point
- Uses follow set analysis for smart recovery

**Error Listeners:**
```java
interface ANTLRErrorListener {
  void syntaxError(Recognizer<?,?> recognizer,
                   Object offendingSymbol,
                   int line, int charPositionInLine,
                   String msg,
                   RecognitionException e);
  void reportAmbiguity(...);
  void reportAttemptingFullContext(...);
  void reportContextSensitivity(...);
}
```

**Implementations:**
- `ConsoleErrorListener` - Print to stderr
- `DiagnosticErrorListener` - Profiling data
- `BaseErrorListener` - Custom subclass base
- `ProxyErrorListener` - Decorator pattern

**Semantic Predicates:**
```java
// Grammar: a {p}? b
// Generated code:
if (!sempred(_localctx, ruleIdx, predIdx)) 
  throw new FailedPredicateException(this, "p");
```

## Key Design Patterns

### Pattern 1: Interpreter
- **ATNSimulator** interprets ATN states and transitions at runtime
- No compilation to bytecode; flexible grammar evaluation
- Enables features like semantic predicates

### Pattern 2: Visitor & Listener
- **Two traversal strategies** for tree processing
- Decouples grammar from semantics
- Generated code implements both patterns

### Pattern 3: Factory
- **ParserFactory** creates parser-specific code generators
- **ATNFactory** creates state machine structures
- **CodeGeneratorExtension** enables plugins

### Pattern 4: Strategy
- **ANTLRErrorStrategy** pluggable error recovery
- **PredictionMode** (SLL, LL, LL_EXACT_AMBIG_DETECTION)
- **DFA caching strategies**

### Pattern 5: Decorator
- **ProxyErrorListener** wraps error listeners
- Adds cross-cutting concerns

### Pattern 6: Template Method
- **AbstractParseTreeVisitor** provides default implementation
- Subclasses override rule-specific visit methods

### Pattern 7: Caching/Memoization
- **DFA states** memoized for performance
- **Token/rule maps** cached with WeakHashMap (GC-friendly)
- **Lazy initialization** of DFA states on-demand

## Code Generation Templates

Generated parser includes:

1. **Grammar-specific rules:**
   ```java
   public ExprContext expr() throws RecognitionException { ... }
   ```

2. **Tree node classes:**
   ```java
   static class ExprContext extends ParserRuleContext { ... }
   ```

3. **Listener interface:**
   ```java
   interface MyGrammarListener extends ParseTreeListener {
     void enterExpr(ExprContext ctx);
     void exitExpr(ExprContext ctx);
   }
   ```

4. **Visitor interface:**
   ```java
   interface MyGrammarVisitor<T> extends ParseTreeVisitor<T> {
     T visitExpr(ExprContext ctx);
   }
   ```

5. **Base visitor:**
   ```java
   abstract class MyGrammarBaseVisitor<T> 
     extends AbstractParseTreeVisitor<T>
     implements MyGrammarVisitor<T> { ... }
   ```

## Performance Optimizations

1. **DFA Memoization** - Avoids recomputing prediction states
2. **Lazy DFA Construction** - Build states on-demand
3. **WeakHashMap Caching** - Token/rule maps GC-friendly
4. **SLL Prediction Mode** - Fast deterministic path
5. **Unbuffered Streams** - Minimal memory for large inputs
6. **Semantic Predicate Optimization** - Eliminate unnecessary evaluation

## Multi-Language Support

Runtime targets:
- **Java** - Full implementation
- **Python** - Complete with visitor/listener
- **C++** - Modern C++11 implementation
- **C#** - .NET compatible
- **JavaScript/TypeScript** - Node.js and browser
- **Go** - Native Go implementation
- **Swift** - iOS/macOS support
- **PHP** - Web language support

Each runtime provides equivalent to Java runtime:
- Recognizer, Parser, Lexer base classes
- ATN interpreter
- Token stream and handling
- Error strategy and listeners
- Parse tree with visitor/listener patterns

## Summary Statistics

- **~100+ Java classes** in runtime alone
- **~200+ classes** in tool/compiler
- **7 major design patterns** employed
- **Multi-target code generation** for 8+ languages
- **Self-hosting** - ANTLR parses ANTLR grammars
- **Semantic predicate support** for context-sensitive parsing
- **Adaptive prediction** - SLL with LL fallback

