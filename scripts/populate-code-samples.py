#!/usr/bin/env python3
"""
Populate ChromaDB with sample code learning data for demonstration
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pathlib import Path
import json


def populate_sample_data():
    """Populate ChromaDB with sample Rust and other language data"""

    db_path = Path('~/.claude/knowledge/chromadb').expanduser()
    db_path.mkdir(parents=True, exist_ok=True)

    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path=str(db_path),
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=False
        )
    )

    # Create embedding function
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='all-MiniLM-L6-v2'
    )

    # Create NL collection
    nl_collection = client.get_or_create_collection(
        name='code-learning-nl',
        embedding_function=embedding_fn,
        metadata={"description": "Natural language code descriptions"}
    )

    # Create code collection
    code_collection = client.get_or_create_collection(
        name='code-learning-code',
        embedding_function=embedding_fn,
        metadata={"description": "Code snippets and patterns"}
    )

    # Sample NL descriptions
    nl_docs = [
        {
            'id': 'rust-ownership-1',
            'text': 'Rust ownership system prevents data races and memory leaks through compile-time checks. Each value has a single owner, and ownership can be transferred or borrowed.',
            'metadata': {
                'language': 'rust',
                'topic': 'ownership',
                'difficulty': 'intermediate',
                'ast_type': 'concept'
            }
        },
        {
            'id': 'rust-borrowing-1',
            'text': 'Rust borrowing allows references to data without taking ownership. Mutable borrows are exclusive while immutable borrows can coexist.',
            'metadata': {
                'language': 'rust',
                'topic': 'borrowing',
                'difficulty': 'intermediate',
                'ast_type': 'concept'
            }
        },
        {
            'id': 'rust-error-handling-1',
            'text': 'Rust uses Result<T, E> for recoverable errors and panic! for unrecoverable errors. The ? operator propagates errors up the call stack.',
            'metadata': {
                'language': 'rust',
                'topic': 'error-handling',
                'difficulty': 'beginner',
                'ast_type': 'pattern'
            }
        },
        {
            'id': 'rust-traits-1',
            'text': 'Rust traits define shared behavior across types. Traits can have default implementations and are used for polymorphism.',
            'metadata': {
                'language': 'rust',
                'topic': 'traits',
                'difficulty': 'intermediate',
                'ast_type': 'concept'
            }
        },
        {
            'id': 'python-async-1',
            'text': 'Python async/await enables concurrent I/O operations. The asyncio event loop manages coroutines and tasks.',
            'metadata': {
                'language': 'python',
                'topic': 'async',
                'difficulty': 'intermediate',
                'ast_type': 'pattern'
            }
        },
        {
            'id': 'javascript-promises-1',
            'text': 'JavaScript promises represent asynchronous operations. Promise.all() executes multiple promises in parallel.',
            'metadata': {
                'language': 'javascript',
                'topic': 'async',
                'difficulty': 'beginner',
                'ast_type': 'pattern'
            }
        },
        {
            'id': 'rust-iterators-1',
            'text': 'Rust iterators are lazy and zero-cost abstractions. Methods like map(), filter(), and collect() enable functional-style data processing.',
            'metadata': {
                'language': 'rust',
                'topic': 'iterators',
                'difficulty': 'intermediate',
                'ast_type': 'pattern'
            }
        },
        {
            'id': 'rust-lifetimes-1',
            'text': 'Rust lifetimes specify how long references are valid. Lifetime annotations help the compiler verify reference validity.',
            'metadata': {
                'language': 'rust',
                'topic': 'lifetimes',
                'difficulty': 'advanced',
                'ast_type': 'concept'
            }
        }
    ]

    # Sample code snippets
    code_docs = [
        {
            'id': 'rust-ownership-code-1',
            'text': '''fn main() {
    let s1 = String::from("hello");
    let s2 = s1; // s1 is moved to s2
    // println!("{}", s1); // This would fail - s1 is no longer valid
    println!("{}", s2);
}''',
            'metadata': {
                'language': 'rust',
                'topic': 'ownership',
                'ast_type': 'function',
                'difficulty': 'beginner'
            }
        },
        {
            'id': 'rust-borrowing-code-1',
            'text': '''fn calculate_length(s: &String) -> usize {
    s.len() // Borrowed reference, no ownership transfer
}

fn main() {
    let s1 = String::from("hello");
    let len = calculate_length(&s1);
    println!("Length of '{}' is {}", s1, len);
}''',
            'metadata': {
                'language': 'rust',
                'topic': 'borrowing',
                'ast_type': 'function',
                'difficulty': 'beginner'
            }
        },
        {
            'id': 'rust-result-code-1',
            'text': '''use std::fs::File;
use std::io::Read;

fn read_file(path: &str) -> Result<String, std::io::Error> {
    let mut file = File::open(path)?;
    let mut contents = String::new();
    file.read_to_string(&mut contents)?;
    Ok(contents)
}''',
            'metadata': {
                'language': 'rust',
                'topic': 'error-handling',
                'ast_type': 'function',
                'difficulty': 'intermediate'
            }
        },
        {
            'id': 'rust-trait-code-1',
            'text': '''trait Summary {
    fn summarize(&self) -> String;
}

struct Article {
    title: String,
    content: String,
}

impl Summary for Article {
    fn summarize(&self) -> String {
        format!("{}: {}", self.title, self.content)
    }
}''',
            'metadata': {
                'language': 'rust',
                'topic': 'traits',
                'ast_type': 'trait',
                'difficulty': 'intermediate'
            }
        },
        {
            'id': 'rust-iterator-code-1',
            'text': '''fn main() {
    let numbers = vec![1, 2, 3, 4, 5];
    let doubled: Vec<i32> = numbers
        .iter()
        .map(|x| x * 2)
        .filter(|x| x > &5)
        .collect();
    println!("{:?}", doubled);
}''',
            'metadata': {
                'language': 'rust',
                'topic': 'iterators',
                'ast_type': 'function',
                'difficulty': 'intermediate'
            }
        },
        {
            'id': 'python-async-code-1',
            'text': '''import asyncio

async def fetch_data(url):
    await asyncio.sleep(1)
    return f"Data from {url}"

async def main():
    results = await asyncio.gather(
        fetch_data("api1"),
        fetch_data("api2"),
        fetch_data("api3")
    )
    print(results)

asyncio.run(main())''',
            'metadata': {
                'language': 'python',
                'topic': 'async',
                'ast_type': 'function',
                'difficulty': 'intermediate'
            }
        }
    ]

    # Add NL documents
    print(f"Adding {len(nl_docs)} NL documents...")
    nl_collection.add(
        documents=[doc['text'] for doc in nl_docs],
        metadatas=[doc['metadata'] for doc in nl_docs],
        ids=[doc['id'] for doc in nl_docs]
    )

    # Add code documents
    print(f"Adding {len(code_docs)} code documents...")
    code_collection.add(
        documents=[doc['text'] for doc in code_docs],
        metadatas=[doc['metadata'] for doc in code_docs],
        ids=[doc['id'] for doc in code_docs]
    )

    print(f"\nPopulated ChromaDB:")
    print(f"  NL collection: {nl_collection.count()} documents")
    print(f"  Code collection: {code_collection.count()} documents")


if __name__ == '__main__':
    populate_sample_data()
