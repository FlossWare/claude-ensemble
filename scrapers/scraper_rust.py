#!/usr/bin/env python3
"""Rust documentation scraper.

Covers:
  - The Rust Book (doc.rust-lang.org/book/)
  - Rust by Example (doc.rust-lang.org/rust-by-example/)
  - The Rust Reference (doc.rust-lang.org/reference/)
  - Standard Library (doc.rust-lang.org/std/)
  - The Cargo Book (doc.rust-lang.org/cargo/)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RustScraper(BaseScraper):
    """Scrape Rust documentation from doc.rust-lang.org."""

    SOURCES = {
        "book": {
            "pages": {
                # The Rust Programming Language - all 20 chapters + appendices
                "https://doc.rust-lang.org/book/": "The Rust Programming Language",
                "https://doc.rust-lang.org/book/title-page.html": "The Rust Book - Title Page",
                "https://doc.rust-lang.org/book/foreword.html": "Foreword",
                "https://doc.rust-lang.org/book/ch00-00-introduction.html": "Introduction",
                # Ch 1: Getting Started
                "https://doc.rust-lang.org/book/ch01-00-getting-started.html": "Getting Started",
                "https://doc.rust-lang.org/book/ch01-01-installation.html": "Installation",
                "https://doc.rust-lang.org/book/ch01-02-hello-world.html": "Hello, World!",
                "https://doc.rust-lang.org/book/ch01-03-hello-cargo.html": "Hello, Cargo!",
                # Ch 2: Programming a Guessing Game
                "https://doc.rust-lang.org/book/ch02-00-guessing-game-tutorial.html": "Programming a Guessing Game",
                # Ch 3: Common Programming Concepts
                "https://doc.rust-lang.org/book/ch03-00-common-programming-concepts.html": "Common Programming Concepts",
                "https://doc.rust-lang.org/book/ch03-01-variables-and-mutability.html": "Variables and Mutability",
                "https://doc.rust-lang.org/book/ch03-02-data-types.html": "Data Types",
                "https://doc.rust-lang.org/book/ch03-03-how-functions-work.html": "Functions",
                "https://doc.rust-lang.org/book/ch03-04-comments.html": "Comments",
                "https://doc.rust-lang.org/book/ch03-05-control-flow.html": "Control Flow",
                # Ch 4: Understanding Ownership
                "https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html": "Understanding Ownership",
                "https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html": "What Is Ownership?",
                "https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html": "References and Borrowing",
                "https://doc.rust-lang.org/book/ch04-03-slices.html": "The Slice Type",
                # Ch 5: Using Structs
                "https://doc.rust-lang.org/book/ch05-00-structs.html": "Using Structs to Structure Related Data",
                "https://doc.rust-lang.org/book/ch05-01-defining-structs.html": "Defining and Instantiating Structs",
                "https://doc.rust-lang.org/book/ch05-02-example-structs.html": "An Example Program Using Structs",
                "https://doc.rust-lang.org/book/ch05-03-method-syntax.html": "Method Syntax",
                # Ch 6: Enums and Pattern Matching
                "https://doc.rust-lang.org/book/ch06-00-enums.html": "Enums and Pattern Matching",
                "https://doc.rust-lang.org/book/ch06-01-defining-an-enum.html": "Defining an Enum",
                "https://doc.rust-lang.org/book/ch06-02-match.html": "The match Control Flow Construct",
                "https://doc.rust-lang.org/book/ch06-03-if-let.html": "Concise Control Flow with if let",
                # Ch 7: Managing Growing Projects
                "https://doc.rust-lang.org/book/ch07-00-managing-growing-projects-with-packages-crates-and-modules.html": "Managing Growing Projects with Packages, Crates, and Modules",
                "https://doc.rust-lang.org/book/ch07-01-packages-and-crates.html": "Packages and Crates",
                "https://doc.rust-lang.org/book/ch07-02-defining-modules-to-control-scope-and-privacy.html": "Defining Modules to Control Scope and Privacy",
                "https://doc.rust-lang.org/book/ch07-03-paths-for-referring-to-an-item-in-the-module-tree.html": "Paths for Referring to an Item in the Module Tree",
                "https://doc.rust-lang.org/book/ch07-04-bringing-paths-into-scope-with-the-use-keyword.html": "Bringing Paths into Scope with the use Keyword",
                "https://doc.rust-lang.org/book/ch07-05-separating-modules-into-different-files.html": "Separating Modules into Different Files",
                # Ch 8: Common Collections
                "https://doc.rust-lang.org/book/ch08-00-common-collections.html": "Common Collections",
                "https://doc.rust-lang.org/book/ch08-01-vectors.html": "Storing Lists of Values with Vectors",
                "https://doc.rust-lang.org/book/ch08-02-strings.html": "Storing UTF-8 Encoded Text with Strings",
                "https://doc.rust-lang.org/book/ch08-03-hash-maps.html": "Storing Keys with Associated Values in Hash Maps",
                # Ch 9: Error Handling
                "https://doc.rust-lang.org/book/ch09-00-error-handling.html": "Error Handling",
                "https://doc.rust-lang.org/book/ch09-01-unrecoverable-errors-with-panic.html": "Unrecoverable Errors with panic!",
                "https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html": "Recoverable Errors with Result",
                "https://doc.rust-lang.org/book/ch09-03-to-panic-or-not-to-panic.html": "To panic! or Not to panic!",
                # Ch 10: Generic Types, Traits, and Lifetimes
                "https://doc.rust-lang.org/book/ch10-00-generics.html": "Generic Types, Traits, and Lifetimes",
                "https://doc.rust-lang.org/book/ch10-01-syntax.html": "Generic Data Types",
                "https://doc.rust-lang.org/book/ch10-02-traits.html": "Traits: Defining Shared Behavior",
                "https://doc.rust-lang.org/book/ch10-03-lifetime-syntax.html": "Validating References with Lifetimes",
                # Ch 11: Writing Automated Tests
                "https://doc.rust-lang.org/book/ch11-00-testing.html": "Writing Automated Tests",
                "https://doc.rust-lang.org/book/ch11-01-writing-tests.html": "How to Write Tests",
                "https://doc.rust-lang.org/book/ch11-02-running-tests.html": "Controlling How Tests Are Run",
                "https://doc.rust-lang.org/book/ch11-03-test-organization.html": "Test Organization",
                # Ch 12: An I/O Project
                "https://doc.rust-lang.org/book/ch12-00-an-io-project.html": "An I/O Project: Building a Command Line Program",
                "https://doc.rust-lang.org/book/ch12-01-accepting-command-line-arguments.html": "Accepting Command Line Arguments",
                "https://doc.rust-lang.org/book/ch12-02-reading-a-file.html": "Reading a File",
                "https://doc.rust-lang.org/book/ch12-03-improving-error-handling-and-modularity.html": "Refactoring to Improve Modularity and Error Handling",
                "https://doc.rust-lang.org/book/ch12-04-testing-the-librarys-functionality.html": "Developing the Library's Functionality with TDD",
                "https://doc.rust-lang.org/book/ch12-05-working-with-environment-variables.html": "Working with Environment Variables",
                "https://doc.rust-lang.org/book/ch12-06-writing-to-stderr-instead-of-stdout.html": "Writing Error Messages to Standard Error",
                # Ch 13: Functional Language Features
                "https://doc.rust-lang.org/book/ch13-00-functional-features.html": "Functional Language Features: Iterators and Closures",
                "https://doc.rust-lang.org/book/ch13-01-closures.html": "Closures: Anonymous Functions that Capture Their Environment",
                "https://doc.rust-lang.org/book/ch13-02-iterators.html": "Processing a Series of Items with Iterators",
                "https://doc.rust-lang.org/book/ch13-03-improving-our-io-project.html": "Improving Our I/O Project",
                "https://doc.rust-lang.org/book/ch13-04-performance.html": "Comparing Performance: Loops vs. Iterators",
                # Ch 14: More about Cargo and Crates.io
                "https://doc.rust-lang.org/book/ch14-00-more-about-cargo.html": "More About Cargo and Crates.io",
                "https://doc.rust-lang.org/book/ch14-01-release-profiles.html": "Customizing Builds with Release Profiles",
                "https://doc.rust-lang.org/book/ch14-02-publishing-to-crates-io.html": "Publishing a Crate to Crates.io",
                "https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html": "Cargo Workspaces",
                "https://doc.rust-lang.org/book/ch14-04-installing-binaries.html": "Installing Binaries with cargo install",
                "https://doc.rust-lang.org/book/ch14-05-extending-cargo.html": "Extending Cargo with Custom Commands",
                # Ch 15: Smart Pointers
                "https://doc.rust-lang.org/book/ch15-00-smart-pointers.html": "Smart Pointers",
                "https://doc.rust-lang.org/book/ch15-01-box.html": "Using Box<T> to Point to Data on the Heap",
                "https://doc.rust-lang.org/book/ch15-02-deref.html": "Treating Smart Pointers Like Regular References with the Deref Trait",
                "https://doc.rust-lang.org/book/ch15-03-drop.html": "Running Code on Cleanup with the Drop Trait",
                "https://doc.rust-lang.org/book/ch15-04-rc.html": "Rc<T>, the Reference Counted Smart Pointer",
                "https://doc.rust-lang.org/book/ch15-05-interior-mutability.html": "RefCell<T> and the Interior Mutability Pattern",
                "https://doc.rust-lang.org/book/ch15-06-reference-cycles.html": "Reference Cycles Can Leak Memory",
                # Ch 16: Fearless Concurrency
                "https://doc.rust-lang.org/book/ch16-00-concurrency.html": "Fearless Concurrency",
                "https://doc.rust-lang.org/book/ch16-01-threads.html": "Using Threads to Run Code Simultaneously",
                "https://doc.rust-lang.org/book/ch16-02-message-passing.html": "Using Message Passing to Transfer Data Between Threads",
                "https://doc.rust-lang.org/book/ch16-03-shared-state.html": "Shared-State Concurrency",
                "https://doc.rust-lang.org/book/ch16-04-extensible-concurrency-sync-and-send.html": "Extensible Concurrency with the Sync and Send Traits",
                # Ch 17: OOP Features
                "https://doc.rust-lang.org/book/ch17-00-oop.html": "Object-Oriented Programming Features of Rust",
                "https://doc.rust-lang.org/book/ch17-01-what-is-oo.html": "Characteristics of Object-Oriented Languages",
                "https://doc.rust-lang.org/book/ch17-02-trait-objects.html": "Using Trait Objects That Allow for Values of Different Types",
                "https://doc.rust-lang.org/book/ch17-03-oo-design-patterns.html": "Implementing an Object-Oriented Design Pattern",
                # Ch 18: Patterns and Matching
                "https://doc.rust-lang.org/book/ch18-00-patterns.html": "Patterns and Matching",
                "https://doc.rust-lang.org/book/ch18-01-all-the-places-for-patterns.html": "All the Places Patterns Can Be Used",
                "https://doc.rust-lang.org/book/ch18-02-refutability.html": "Refutability: Whether a Pattern Might Fail to Match",
                "https://doc.rust-lang.org/book/ch18-03-pattern-syntax.html": "Pattern Syntax",
                # Ch 19: Advanced Features
                "https://doc.rust-lang.org/book/ch19-00-advanced-features.html": "Advanced Features",
                "https://doc.rust-lang.org/book/ch19-01-unsafe-rust.html": "Unsafe Rust",
                "https://doc.rust-lang.org/book/ch19-03-advanced-traits.html": "Advanced Traits",
                "https://doc.rust-lang.org/book/ch19-04-advanced-types.html": "Advanced Types",
                "https://doc.rust-lang.org/book/ch19-05-advanced-functions-and-closures.html": "Advanced Functions and Closures",
                "https://doc.rust-lang.org/book/ch19-06-macros.html": "Macros",
                # Ch 20: Final Project
                "https://doc.rust-lang.org/book/ch20-00-final-project-a-web-server.html": "Final Project: Building a Multithreaded Web Server",
                "https://doc.rust-lang.org/book/ch20-01-single-threaded.html": "Building a Single-Threaded Web Server",
                "https://doc.rust-lang.org/book/ch20-02-multithreaded.html": "Turning Our Single-Threaded Server into a Multithreaded Server",
                "https://doc.rust-lang.org/book/ch20-03-graceful-shutdown-and-cleanup.html": "Graceful Shutdown and Cleanup",
                # Appendices
                "https://doc.rust-lang.org/book/appendix-00.html": "Appendix",
                "https://doc.rust-lang.org/book/appendix-01-keywords.html": "Appendix A: Keywords",
                "https://doc.rust-lang.org/book/appendix-02-operators.html": "Appendix B: Operators and Symbols",
                "https://doc.rust-lang.org/book/appendix-03-derivable-traits.html": "Appendix C: Derivable Traits",
                "https://doc.rust-lang.org/book/appendix-04-useful-development-tools.html": "Appendix D: Useful Development Tools",
                "https://doc.rust-lang.org/book/appendix-05-editions.html": "Appendix E: Editions",
                "https://doc.rust-lang.org/book/appendix-06-translation.html": "Appendix F: Translations of the Book",
                "https://doc.rust-lang.org/book/appendix-07-nightly-rust.html": "Appendix G: How Rust is Made and Nightly Rust",
            },
        },
        "by-example": {
            "pages": {
                # Rust by Example - major sections
                "https://doc.rust-lang.org/rust-by-example/": "Rust by Example",
                "https://doc.rust-lang.org/rust-by-example/hello.html": "Hello World",
                "https://doc.rust-lang.org/rust-by-example/hello/comment.html": "Comments",
                "https://doc.rust-lang.org/rust-by-example/hello/print.html": "Formatted Print",
                "https://doc.rust-lang.org/rust-by-example/hello/print/fmt.html": "Formatting",
                "https://doc.rust-lang.org/rust-by-example/primitives.html": "Primitives",
                "https://doc.rust-lang.org/rust-by-example/primitives/literals.html": "Literals and Operators",
                "https://doc.rust-lang.org/rust-by-example/primitives/tuples.html": "Tuples",
                "https://doc.rust-lang.org/rust-by-example/primitives/array.html": "Arrays and Slices",
                "https://doc.rust-lang.org/rust-by-example/custom_types.html": "Custom Types",
                "https://doc.rust-lang.org/rust-by-example/custom_types/structs.html": "Structures",
                "https://doc.rust-lang.org/rust-by-example/custom_types/enum.html": "Enums",
                "https://doc.rust-lang.org/rust-by-example/custom_types/constants.html": "Constants",
                "https://doc.rust-lang.org/rust-by-example/variable_bindings.html": "Variable Bindings",
                "https://doc.rust-lang.org/rust-by-example/variable_bindings/mut.html": "Mutability",
                "https://doc.rust-lang.org/rust-by-example/variable_bindings/scope.html": "Scope and Shadowing",
                "https://doc.rust-lang.org/rust-by-example/types.html": "Types",
                "https://doc.rust-lang.org/rust-by-example/types/cast.html": "Casting",
                "https://doc.rust-lang.org/rust-by-example/types/literals.html": "Literals",
                "https://doc.rust-lang.org/rust-by-example/types/inference.html": "Inference",
                "https://doc.rust-lang.org/rust-by-example/types/alias.html": "Aliasing",
                "https://doc.rust-lang.org/rust-by-example/conversion.html": "Conversion",
                "https://doc.rust-lang.org/rust-by-example/conversion/from_into.html": "From and Into",
                "https://doc.rust-lang.org/rust-by-example/conversion/try_from_try_into.html": "TryFrom and TryInto",
                "https://doc.rust-lang.org/rust-by-example/conversion/string.html": "To and from Strings",
                "https://doc.rust-lang.org/rust-by-example/expression.html": "Expressions",
                "https://doc.rust-lang.org/rust-by-example/flow_control.html": "Flow of Control",
                "https://doc.rust-lang.org/rust-by-example/flow_control/if_else.html": "if/else",
                "https://doc.rust-lang.org/rust-by-example/flow_control/loop.html": "loop",
                "https://doc.rust-lang.org/rust-by-example/flow_control/while.html": "while",
                "https://doc.rust-lang.org/rust-by-example/flow_control/for.html": "for and range",
                "https://doc.rust-lang.org/rust-by-example/flow_control/match.html": "match",
                "https://doc.rust-lang.org/rust-by-example/flow_control/if_let.html": "if let",
                "https://doc.rust-lang.org/rust-by-example/flow_control/while_let.html": "while let",
                "https://doc.rust-lang.org/rust-by-example/fn.html": "Functions",
                "https://doc.rust-lang.org/rust-by-example/fn/methods.html": "Methods",
                "https://doc.rust-lang.org/rust-by-example/fn/closures.html": "Closures",
                "https://doc.rust-lang.org/rust-by-example/fn/hof.html": "Higher Order Functions",
                "https://doc.rust-lang.org/rust-by-example/fn/diverging.html": "Diverging Functions",
                "https://doc.rust-lang.org/rust-by-example/mod.html": "Modules",
                "https://doc.rust-lang.org/rust-by-example/mod/visibility.html": "Visibility",
                "https://doc.rust-lang.org/rust-by-example/mod/struct_visibility.html": "Struct Visibility",
                "https://doc.rust-lang.org/rust-by-example/mod/use.html": "The use Declaration",
                "https://doc.rust-lang.org/rust-by-example/mod/super.html": "super and self",
                "https://doc.rust-lang.org/rust-by-example/crates.html": "Crates",
                "https://doc.rust-lang.org/rust-by-example/crates/lib.html": "Creating a Library",
                "https://doc.rust-lang.org/rust-by-example/crates/using_lib.html": "Using a Library",
                "https://doc.rust-lang.org/rust-by-example/cargo.html": "Cargo",
                "https://doc.rust-lang.org/rust-by-example/cargo/deps.html": "Dependencies",
                "https://doc.rust-lang.org/rust-by-example/cargo/conventions.html": "Conventions",
                "https://doc.rust-lang.org/rust-by-example/cargo/test.html": "Tests",
                "https://doc.rust-lang.org/rust-by-example/cargo/build_scripts.html": "Build Scripts",
                "https://doc.rust-lang.org/rust-by-example/attribute.html": "Attributes",
                "https://doc.rust-lang.org/rust-by-example/attribute/cfg.html": "cfg",
                "https://doc.rust-lang.org/rust-by-example/generics.html": "Generics",
                "https://doc.rust-lang.org/rust-by-example/generics/gen_fn.html": "Functions",
                "https://doc.rust-lang.org/rust-by-example/generics/impl.html": "Implementation",
                "https://doc.rust-lang.org/rust-by-example/generics/gen_trait.html": "Traits",
                "https://doc.rust-lang.org/rust-by-example/generics/bounds.html": "Bounds",
                "https://doc.rust-lang.org/rust-by-example/generics/where.html": "Where Clauses",
                "https://doc.rust-lang.org/rust-by-example/generics/assoc_items.html": "Associated Items",
                "https://doc.rust-lang.org/rust-by-example/generics/phantom.html": "Phantom Type Parameters",
                "https://doc.rust-lang.org/rust-by-example/scope.html": "Scoping Rules",
                "https://doc.rust-lang.org/rust-by-example/scope/borrow.html": "Borrowing",
                "https://doc.rust-lang.org/rust-by-example/scope/lifetime.html": "Lifetimes",
                "https://doc.rust-lang.org/rust-by-example/scope/move.html": "Ownership and Moves",
                "https://doc.rust-lang.org/rust-by-example/trait.html": "Traits",
                "https://doc.rust-lang.org/rust-by-example/trait/derive.html": "Derive",
                "https://doc.rust-lang.org/rust-by-example/trait/dyn.html": "Returning Traits with dyn",
                "https://doc.rust-lang.org/rust-by-example/trait/ops.html": "Operator Overloading",
                "https://doc.rust-lang.org/rust-by-example/trait/drop.html": "Drop",
                "https://doc.rust-lang.org/rust-by-example/trait/iter.html": "Iterators",
                "https://doc.rust-lang.org/rust-by-example/trait/impl_trait.html": "impl Trait",
                "https://doc.rust-lang.org/rust-by-example/trait/clone.html": "Clone",
                "https://doc.rust-lang.org/rust-by-example/trait/supertraits.html": "Supertraits",
                "https://doc.rust-lang.org/rust-by-example/trait/disambiguating.html": "Disambiguating Overlapping Traits",
                "https://doc.rust-lang.org/rust-by-example/macros.html": "macro_rules!",
                "https://doc.rust-lang.org/rust-by-example/macros/syntax.html": "Syntax",
                "https://doc.rust-lang.org/rust-by-example/macros/designators.html": "Designators",
                "https://doc.rust-lang.org/rust-by-example/macros/overload.html": "Overload",
                "https://doc.rust-lang.org/rust-by-example/macros/repeat.html": "Repeat",
                "https://doc.rust-lang.org/rust-by-example/macros/dry.html": "DRY (Don't Repeat Yourself)",
                "https://doc.rust-lang.org/rust-by-example/macros/variadics.html": "Variadic Interfaces",
                "https://doc.rust-lang.org/rust-by-example/error.html": "Error Handling",
                "https://doc.rust-lang.org/rust-by-example/error/option_unwrap.html": "Option & unwrap",
                "https://doc.rust-lang.org/rust-by-example/error/result.html": "Result",
                "https://doc.rust-lang.org/rust-by-example/error/multiple_error_types.html": "Multiple Error Types",
                "https://doc.rust-lang.org/rust-by-example/error/iter_result.html": "Iterating over Results",
                "https://doc.rust-lang.org/rust-by-example/std_misc.html": "Std Misc",
                "https://doc.rust-lang.org/rust-by-example/std_misc/threads.html": "Threads",
                "https://doc.rust-lang.org/rust-by-example/std_misc/channels.html": "Channels",
                "https://doc.rust-lang.org/rust-by-example/std_misc/path.html": "Path",
                "https://doc.rust-lang.org/rust-by-example/std_misc/file.html": "File I/O",
                "https://doc.rust-lang.org/rust-by-example/std_misc/process.html": "Child Processes",
                "https://doc.rust-lang.org/rust-by-example/std_misc/arg.html": "Program Arguments",
                "https://doc.rust-lang.org/rust-by-example/std_misc/ffi.html": "Foreign Function Interface",
                "https://doc.rust-lang.org/rust-by-example/testing.html": "Testing",
                "https://doc.rust-lang.org/rust-by-example/testing/unit_testing.html": "Unit Testing",
                "https://doc.rust-lang.org/rust-by-example/testing/doc_testing.html": "Documentation Testing",
                "https://doc.rust-lang.org/rust-by-example/testing/integration_testing.html": "Integration Testing",
                "https://doc.rust-lang.org/rust-by-example/testing/dev_dependencies.html": "Dev Dependencies",
                "https://doc.rust-lang.org/rust-by-example/unsafe.html": "Unsafe Operations",
                "https://doc.rust-lang.org/rust-by-example/unsafe/asm.html": "Inline Assembly",
                "https://doc.rust-lang.org/rust-by-example/compatibility.html": "Compatibility",
                "https://doc.rust-lang.org/rust-by-example/compatibility/raw_identifiers.html": "Raw Identifiers",
                "https://doc.rust-lang.org/rust-by-example/meta.html": "Meta",
                "https://doc.rust-lang.org/rust-by-example/meta/doc.html": "Documentation",
                "https://doc.rust-lang.org/rust-by-example/meta/playground.html": "Playground",
            },
        },
        "reference": {
            "pages": {
                # The Rust Reference
                "https://doc.rust-lang.org/reference/": "The Rust Reference",
                "https://doc.rust-lang.org/reference/introduction.html": "Introduction",
                # Lexical structure
                "https://doc.rust-lang.org/reference/notation.html": "Notation",
                "https://doc.rust-lang.org/reference/input-format.html": "Input Format",
                "https://doc.rust-lang.org/reference/keywords.html": "Keywords",
                "https://doc.rust-lang.org/reference/identifiers.html": "Identifiers",
                "https://doc.rust-lang.org/reference/comments.html": "Comments",
                "https://doc.rust-lang.org/reference/whitespace.html": "Whitespace",
                "https://doc.rust-lang.org/reference/tokens.html": "Tokens",
                # Macros
                "https://doc.rust-lang.org/reference/macros.html": "Macros",
                "https://doc.rust-lang.org/reference/macros-by-example.html": "Macros By Example",
                "https://doc.rust-lang.org/reference/procedural-macros.html": "Procedural Macros",
                # Items
                "https://doc.rust-lang.org/reference/items.html": "Items",
                "https://doc.rust-lang.org/reference/items/modules.html": "Modules",
                "https://doc.rust-lang.org/reference/items/extern-crates.html": "Extern Crate Declarations",
                "https://doc.rust-lang.org/reference/items/use-declarations.html": "Use Declarations",
                "https://doc.rust-lang.org/reference/items/functions.html": "Functions",
                "https://doc.rust-lang.org/reference/items/type-aliases.html": "Type Aliases",
                "https://doc.rust-lang.org/reference/items/structs.html": "Structs",
                "https://doc.rust-lang.org/reference/items/enumerations.html": "Enumerations",
                "https://doc.rust-lang.org/reference/items/unions.html": "Unions",
                "https://doc.rust-lang.org/reference/items/constant-items.html": "Constant Items",
                "https://doc.rust-lang.org/reference/items/static-items.html": "Static Items",
                "https://doc.rust-lang.org/reference/items/traits.html": "Traits",
                "https://doc.rust-lang.org/reference/items/implementations.html": "Implementations",
                "https://doc.rust-lang.org/reference/items/external-blocks.html": "External Blocks",
                "https://doc.rust-lang.org/reference/items/associated-items.html": "Associated Items",
                # Statements and expressions
                "https://doc.rust-lang.org/reference/statements.html": "Statements",
                "https://doc.rust-lang.org/reference/expressions.html": "Expressions",
                "https://doc.rust-lang.org/reference/expressions/literal-expr.html": "Literal Expressions",
                "https://doc.rust-lang.org/reference/expressions/path-expr.html": "Path Expressions",
                "https://doc.rust-lang.org/reference/expressions/block-expr.html": "Block Expressions",
                "https://doc.rust-lang.org/reference/expressions/operator-expr.html": "Operator Expressions",
                "https://doc.rust-lang.org/reference/expressions/grouped-expr.html": "Grouped Expressions",
                "https://doc.rust-lang.org/reference/expressions/array-expr.html": "Array and Index Expressions",
                "https://doc.rust-lang.org/reference/expressions/tuple-expr.html": "Tuple and Tuple Indexing Expressions",
                "https://doc.rust-lang.org/reference/expressions/struct-expr.html": "Struct Expressions",
                "https://doc.rust-lang.org/reference/expressions/call-expr.html": "Call Expressions",
                "https://doc.rust-lang.org/reference/expressions/method-call-expr.html": "Method Call Expressions",
                "https://doc.rust-lang.org/reference/expressions/field-expr.html": "Field Access Expressions",
                "https://doc.rust-lang.org/reference/expressions/closure-expr.html": "Closure Expressions",
                "https://doc.rust-lang.org/reference/expressions/loop-expr.html": "Loop Expressions",
                "https://doc.rust-lang.org/reference/expressions/range-expr.html": "Range Expressions",
                "https://doc.rust-lang.org/reference/expressions/if-expr.html": "If and If Let Expressions",
                "https://doc.rust-lang.org/reference/expressions/match-expr.html": "Match Expressions",
                "https://doc.rust-lang.org/reference/expressions/return-expr.html": "Return Expressions",
                "https://doc.rust-lang.org/reference/expressions/await-expr.html": "Await Expressions",
                # Type system
                "https://doc.rust-lang.org/reference/types.html": "Types",
                "https://doc.rust-lang.org/reference/types/boolean.html": "Boolean Type",
                "https://doc.rust-lang.org/reference/types/numeric.html": "Numeric Types",
                "https://doc.rust-lang.org/reference/types/textual.html": "Textual Types",
                "https://doc.rust-lang.org/reference/types/never.html": "Never Type",
                "https://doc.rust-lang.org/reference/types/tuple.html": "Tuple Types",
                "https://doc.rust-lang.org/reference/types/array.html": "Array Types",
                "https://doc.rust-lang.org/reference/types/slice.html": "Slice Types",
                "https://doc.rust-lang.org/reference/types/struct.html": "Struct Types",
                "https://doc.rust-lang.org/reference/types/enum.html": "Enumerated Types",
                "https://doc.rust-lang.org/reference/types/union.html": "Union Types",
                "https://doc.rust-lang.org/reference/types/function-item.html": "Function Item Types",
                "https://doc.rust-lang.org/reference/types/function-pointer.html": "Function Pointer Types",
                "https://doc.rust-lang.org/reference/types/closure.html": "Closure Types",
                "https://doc.rust-lang.org/reference/types/pointer.html": "Pointer Types",
                "https://doc.rust-lang.org/reference/types/trait-object.html": "Trait Object Types",
                "https://doc.rust-lang.org/reference/types/impl-trait.html": "Impl Trait Types",
                # Patterns
                "https://doc.rust-lang.org/reference/patterns.html": "Patterns",
                # Trait system
                "https://doc.rust-lang.org/reference/special-types-and-traits.html": "Special Types and Traits",
                "https://doc.rust-lang.org/reference/type-coercions.html": "Type Coercions",
                "https://doc.rust-lang.org/reference/type-layout.html": "Type Layout",
                # Memory model
                "https://doc.rust-lang.org/reference/memory-model.html": "Memory Model",
                "https://doc.rust-lang.org/reference/memory-allocation-and-lifetime.html": "Memory Allocation and Lifetime",
                "https://doc.rust-lang.org/reference/variables.html": "Variables",
                "https://doc.rust-lang.org/reference/destructors.html": "Destructors",
                # Linkage
                "https://doc.rust-lang.org/reference/linkage.html": "Linkage",
                # Runtime
                "https://doc.rust-lang.org/reference/runtime.html": "Runtime",
                "https://doc.rust-lang.org/reference/abi.html": "Application Binary Interface",
                # Appendices
                "https://doc.rust-lang.org/reference/influences.html": "Influences",
                "https://doc.rust-lang.org/reference/glossary.html": "Glossary",
                # Attributes
                "https://doc.rust-lang.org/reference/attributes.html": "Attributes",
                "https://doc.rust-lang.org/reference/attributes/derive.html": "Derive Attributes",
                "https://doc.rust-lang.org/reference/attributes/diagnostics.html": "Diagnostic Attributes",
                "https://doc.rust-lang.org/reference/attributes/codegen.html": "Code Generation Attributes",
                "https://doc.rust-lang.org/reference/attributes/limits.html": "Limits",
                "https://doc.rust-lang.org/reference/attributes/testing.html": "Testing Attributes",
                "https://doc.rust-lang.org/reference/attributes/type_system.html": "Type System Attributes",
                "https://doc.rust-lang.org/reference/conditional-compilation.html": "Conditional Compilation",
                # Names and paths
                "https://doc.rust-lang.org/reference/names.html": "Names",
                "https://doc.rust-lang.org/reference/names/namespaces.html": "Namespaces",
                "https://doc.rust-lang.org/reference/names/scopes.html": "Scopes",
                "https://doc.rust-lang.org/reference/names/preludes.html": "Preludes",
                "https://doc.rust-lang.org/reference/paths.html": "Paths",
                "https://doc.rust-lang.org/reference/visibility-and-privacy.html": "Visibility and Privacy",
                # Unsafe
                "https://doc.rust-lang.org/reference/unsafety.html": "Unsafety",
                "https://doc.rust-lang.org/reference/unsafe-keyword.html": "The unsafe Keyword",
                "https://doc.rust-lang.org/reference/behavior-considered-undefined.html": "Behavior Considered Undefined",
                "https://doc.rust-lang.org/reference/behavior-not-considered-unsafe.html": "Behavior Not Considered Unsafe",
                # Crates and source files
                "https://doc.rust-lang.org/reference/crates-and-source-files.html": "Crates and Source Files",
            },
        },
        "std": {
            "pages": {
                # Standard library key modules
                "https://doc.rust-lang.org/std/": "The Rust Standard Library",
                "https://doc.rust-lang.org/std/option/index.html": "std::option",
                "https://doc.rust-lang.org/std/option/enum.Option.html": "Option Enum",
                "https://doc.rust-lang.org/std/result/index.html": "std::result",
                "https://doc.rust-lang.org/std/result/enum.Result.html": "Result Enum",
                "https://doc.rust-lang.org/std/vec/index.html": "std::vec",
                "https://doc.rust-lang.org/std/vec/struct.Vec.html": "Vec Struct",
                "https://doc.rust-lang.org/std/string/index.html": "std::string",
                "https://doc.rust-lang.org/std/string/struct.String.html": "String Struct",
                "https://doc.rust-lang.org/std/collections/index.html": "std::collections",
                "https://doc.rust-lang.org/std/collections/struct.HashMap.html": "HashMap",
                "https://doc.rust-lang.org/std/collections/struct.HashSet.html": "HashSet",
                "https://doc.rust-lang.org/std/collections/struct.BTreeMap.html": "BTreeMap",
                "https://doc.rust-lang.org/std/collections/struct.VecDeque.html": "VecDeque",
                "https://doc.rust-lang.org/std/collections/struct.LinkedList.html": "LinkedList",
                "https://doc.rust-lang.org/std/collections/struct.BinaryHeap.html": "BinaryHeap",
                "https://doc.rust-lang.org/std/io/index.html": "std::io",
                "https://doc.rust-lang.org/std/io/trait.Read.html": "io::Read Trait",
                "https://doc.rust-lang.org/std/io/trait.Write.html": "io::Write Trait",
                "https://doc.rust-lang.org/std/io/struct.BufReader.html": "io::BufReader",
                "https://doc.rust-lang.org/std/io/struct.BufWriter.html": "io::BufWriter",
                "https://doc.rust-lang.org/std/fs/index.html": "std::fs",
                "https://doc.rust-lang.org/std/fs/struct.File.html": "fs::File",
                "https://doc.rust-lang.org/std/net/index.html": "std::net",
                "https://doc.rust-lang.org/std/net/struct.TcpListener.html": "net::TcpListener",
                "https://doc.rust-lang.org/std/net/struct.TcpStream.html": "net::TcpStream",
                "https://doc.rust-lang.org/std/net/struct.UdpSocket.html": "net::UdpSocket",
                "https://doc.rust-lang.org/std/thread/index.html": "std::thread",
                "https://doc.rust-lang.org/std/thread/fn.spawn.html": "thread::spawn",
                "https://doc.rust-lang.org/std/sync/index.html": "std::sync",
                "https://doc.rust-lang.org/std/sync/struct.Mutex.html": "sync::Mutex",
                "https://doc.rust-lang.org/std/sync/struct.RwLock.html": "sync::RwLock",
                "https://doc.rust-lang.org/std/sync/struct.Arc.html": "sync::Arc",
                "https://doc.rust-lang.org/std/sync/mpsc/index.html": "sync::mpsc",
                "https://doc.rust-lang.org/std/process/index.html": "std::process",
                "https://doc.rust-lang.org/std/process/struct.Command.html": "process::Command",
                "https://doc.rust-lang.org/std/env/index.html": "std::env",
                "https://doc.rust-lang.org/std/path/index.html": "std::path",
                "https://doc.rust-lang.org/std/path/struct.PathBuf.html": "path::PathBuf",
                "https://doc.rust-lang.org/std/path/struct.Path.html": "path::Path",
                "https://doc.rust-lang.org/std/time/index.html": "std::time",
                "https://doc.rust-lang.org/std/time/struct.Duration.html": "time::Duration",
                "https://doc.rust-lang.org/std/time/struct.Instant.html": "time::Instant",
                "https://doc.rust-lang.org/std/fmt/index.html": "std::fmt",
                "https://doc.rust-lang.org/std/fmt/trait.Display.html": "fmt::Display Trait",
                "https://doc.rust-lang.org/std/fmt/trait.Debug.html": "fmt::Debug Trait",
                "https://doc.rust-lang.org/std/iter/index.html": "std::iter",
                "https://doc.rust-lang.org/std/iter/trait.Iterator.html": "iter::Iterator Trait",
                "https://doc.rust-lang.org/std/iter/trait.IntoIterator.html": "iter::IntoIterator Trait",
                "https://doc.rust-lang.org/std/convert/index.html": "std::convert",
                "https://doc.rust-lang.org/std/convert/trait.From.html": "convert::From Trait",
                "https://doc.rust-lang.org/std/convert/trait.Into.html": "convert::Into Trait",
                "https://doc.rust-lang.org/std/convert/trait.TryFrom.html": "convert::TryFrom Trait",
                "https://doc.rust-lang.org/std/ops/index.html": "std::ops",
                "https://doc.rust-lang.org/std/cmp/index.html": "std::cmp",
                "https://doc.rust-lang.org/std/cmp/trait.Ord.html": "cmp::Ord Trait",
                "https://doc.rust-lang.org/std/cmp/trait.PartialOrd.html": "cmp::PartialOrd Trait",
                "https://doc.rust-lang.org/std/hash/index.html": "std::hash",
                "https://doc.rust-lang.org/std/marker/index.html": "std::marker",
                "https://doc.rust-lang.org/std/marker/trait.Send.html": "marker::Send Trait",
                "https://doc.rust-lang.org/std/marker/trait.Sync.html": "marker::Sync Trait",
                "https://doc.rust-lang.org/std/marker/trait.Copy.html": "marker::Copy Trait",
                "https://doc.rust-lang.org/std/marker/struct.PhantomData.html": "marker::PhantomData",
                "https://doc.rust-lang.org/std/any/index.html": "std::any",
                "https://doc.rust-lang.org/std/cell/index.html": "std::cell",
                "https://doc.rust-lang.org/std/cell/struct.Cell.html": "cell::Cell",
                "https://doc.rust-lang.org/std/cell/struct.RefCell.html": "cell::RefCell",
                "https://doc.rust-lang.org/std/rc/index.html": "std::rc",
                "https://doc.rust-lang.org/std/rc/struct.Rc.html": "rc::Rc",
                "https://doc.rust-lang.org/std/pin/index.html": "std::pin",
                "https://doc.rust-lang.org/std/pin/struct.Pin.html": "pin::Pin",
                "https://doc.rust-lang.org/std/future/index.html": "std::future",
                "https://doc.rust-lang.org/std/future/trait.Future.html": "future::Future Trait",
                "https://doc.rust-lang.org/std/task/index.html": "std::task",
            },
        },
        "cargo": {
            "pages": {
                # The Cargo Book
                "https://doc.rust-lang.org/cargo/": "The Cargo Book",
                "https://doc.rust-lang.org/cargo/getting-started/index.html": "Getting Started",
                "https://doc.rust-lang.org/cargo/getting-started/installation.html": "Installation",
                "https://doc.rust-lang.org/cargo/getting-started/first-steps.html": "First Steps with Cargo",
                # Guide
                "https://doc.rust-lang.org/cargo/guide/index.html": "Cargo Guide",
                "https://doc.rust-lang.org/cargo/guide/why-cargo-exists.html": "Why Cargo Exists",
                "https://doc.rust-lang.org/cargo/guide/creating-a-new-project.html": "Creating a New Project",
                "https://doc.rust-lang.org/cargo/guide/working-on-an-existing-project.html": "Working on an Existing Cargo Project",
                "https://doc.rust-lang.org/cargo/guide/dependencies.html": "Dependencies",
                "https://doc.rust-lang.org/cargo/guide/project-layout.html": "Package Layout",
                "https://doc.rust-lang.org/cargo/guide/cargo-toml-vs-cargo-lock.html": "Cargo.toml vs Cargo.lock",
                "https://doc.rust-lang.org/cargo/guide/tests.html": "Tests",
                "https://doc.rust-lang.org/cargo/guide/continuous-integration.html": "Continuous Integration",
                "https://doc.rust-lang.org/cargo/guide/cargo-home.html": "Cargo Home",
                "https://doc.rust-lang.org/cargo/guide/build-cache.html": "Build Cache",
                # Reference
                "https://doc.rust-lang.org/cargo/reference/index.html": "Cargo Reference",
                "https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html": "Specifying Dependencies",
                "https://doc.rust-lang.org/cargo/reference/manifest.html": "The Manifest Format",
                "https://doc.rust-lang.org/cargo/reference/cargo-targets.html": "Cargo Targets",
                "https://doc.rust-lang.org/cargo/reference/workspaces.html": "Workspaces",
                "https://doc.rust-lang.org/cargo/reference/features.html": "Features",
                "https://doc.rust-lang.org/cargo/reference/profiles.html": "Profiles",
                "https://doc.rust-lang.org/cargo/reference/config.html": "Configuration",
                "https://doc.rust-lang.org/cargo/reference/environment-variables.html": "Environment Variables",
                "https://doc.rust-lang.org/cargo/reference/build-scripts.html": "Build Scripts",
                "https://doc.rust-lang.org/cargo/reference/publishing.html": "Publishing on crates.io",
                "https://doc.rust-lang.org/cargo/reference/registries.html": "Registries",
                "https://doc.rust-lang.org/cargo/reference/overriding-dependencies.html": "Overriding Dependencies",
                "https://doc.rust-lang.org/cargo/reference/resolver.html": "Dependency Resolution",
                "https://doc.rust-lang.org/cargo/reference/semver.html": "SemVer Compatibility",
                # Commands
                "https://doc.rust-lang.org/cargo/commands/index.html": "Cargo Commands",
                "https://doc.rust-lang.org/cargo/commands/cargo-build.html": "cargo build",
                "https://doc.rust-lang.org/cargo/commands/cargo-run.html": "cargo run",
                "https://doc.rust-lang.org/cargo/commands/cargo-test.html": "cargo test",
                "https://doc.rust-lang.org/cargo/commands/cargo-bench.html": "cargo bench",
                "https://doc.rust-lang.org/cargo/commands/cargo-doc.html": "cargo doc",
                "https://doc.rust-lang.org/cargo/commands/cargo-clean.html": "cargo clean",
                "https://doc.rust-lang.org/cargo/commands/cargo-check.html": "cargo check",
                "https://doc.rust-lang.org/cargo/commands/cargo-clippy.html": "cargo clippy",
                "https://doc.rust-lang.org/cargo/commands/cargo-fix.html": "cargo fix",
                "https://doc.rust-lang.org/cargo/commands/cargo-new.html": "cargo new",
                "https://doc.rust-lang.org/cargo/commands/cargo-init.html": "cargo init",
                "https://doc.rust-lang.org/cargo/commands/cargo-add.html": "cargo add",
                "https://doc.rust-lang.org/cargo/commands/cargo-remove.html": "cargo remove",
                "https://doc.rust-lang.org/cargo/commands/cargo-publish.html": "cargo publish",
                "https://doc.rust-lang.org/cargo/commands/cargo-install.html": "cargo install",
                "https://doc.rust-lang.org/cargo/commands/cargo-update.html": "cargo update",
                "https://doc.rust-lang.org/cargo/commands/cargo-search.html": "cargo search",
                "https://doc.rust-lang.org/cargo/commands/cargo-tree.html": "cargo tree",
                "https://doc.rust-lang.org/cargo/commands/cargo-vendor.html": "cargo vendor",
                # FAQ and appendix
                "https://doc.rust-lang.org/cargo/faq.html": "Cargo FAQ",
                "https://doc.rust-lang.org/cargo/appendix/glossary.html": "Cargo Glossary",
                "https://doc.rust-lang.org/cargo/appendix/git-authentication.html": "Git Authentication",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"rust-{source_key}" if source_key else "rust"
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
            for suffix in [
                ' - The Rust Programming Language',
                ' - Rust By Example',
                ' - The Rust Reference',
                ' - The Cargo Book',
            ]:
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
                        "category": "rust-docs",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.0)

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
            self.log.info(f"=== Scraping rust/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RustScraper(base, source_key).run()
