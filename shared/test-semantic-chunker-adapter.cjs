#!/usr/bin/env node
/**
 * Test Semantic Chunker Adapter (Node.js integration)
 */

const { chunkText, analyzeText } = require('./semantic-chunker-adapter.cjs');

async function testBasicChunking() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 1: Basic Chunking');
  console.log('='.repeat(80));

  const text = `
This is the first paragraph about machine learning and AI systems.
It discusses various concepts and techniques used in modern AI.

This is the second paragraph. It talks about neural networks and
their applications in natural language processing.

def process_data(input_file):
    data = read_file(input_file)
    cleaned = clean_data(data)
    return cleaned

def clean_data(data):
    data = data.dropna()
    return data
`;

  try {
    const chunks = chunkText(text, {
      minChunkSize: 100,
      maxChunkSize: 300,
      overlapSize: 50
    });

    console.log(`✓ Created ${chunks.length} chunks`);
    for (const chunk of chunks) {
      console.log(`  Chunk ${chunk.index}: ${chunk.char_count} chars, ` +
                  `type=${chunk.chunk_type}, has_code=${chunk.has_code}`);
    }

    if (chunks.length === 0) {
      console.error('✗ FAIL: No chunks created');
      return false;
    }

    console.log('✓ Basic chunking test PASSED');
    return true;

  } catch (error) {
    console.error('✗ FAIL:', error.message);
    return false;
  }
}

async function testCodeDetection() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 2: Code Detection');
  console.log('='.repeat(80));

  const codeText = `
def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
`;

  const textSample = `
This is a regular paragraph of text.
It does not contain any code.
Just normal English sentences.
`;

  try {
    const codeAnalysis = analyzeText(codeText);
    console.log(`Code sample: is_code=${codeAnalysis.is_code}, language=${codeAnalysis.language}`);

    const textAnalysis = analyzeText(textSample);
    console.log(`Text sample: is_code=${textAnalysis.is_code}, language=${textAnalysis.language}`);

    if (!codeAnalysis.is_code) {
      console.error('✗ FAIL: Code not detected');
      return false;
    }

    if (textAnalysis.is_code) {
      console.error('✗ FAIL: Text incorrectly detected as code');
      return false;
    }

    console.log('✓ Code detection test PASSED');
    return true;

  } catch (error) {
    console.error('✗ FAIL:', error.message);
    return false;
  }
}

async function testLargeText() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 3: Large Text Chunking');
  console.log('='.repeat(80));

  // Create ~3000 char text
  const largeText = 'Paragraph about AI and machine learning. '.repeat(70);

  try {
    console.log(`  Text size: ${largeText.length} chars`);

    const chunks = chunkText(largeText, {
      minChunkSize: 500,
      maxChunkSize: 1000,
      overlapSize: 100
    });

    console.log(`✓ Created ${chunks.length} chunks from large text`);

    // Verify overlap
    for (let i = 0; i < chunks.length - 1; i++) {
      if (chunks[i].overlap_suffix) {
        console.log(`  Chunk ${i} has overlap: ${chunks[i].overlap_suffix.length} chars`);
      }
    }

    if (chunks.length === 0) {
      console.error('✗ FAIL: No chunks created from large text');
      return false;
    }

    console.log('✓ Large text test PASSED');
    return true;

  } catch (error) {
    console.error('✗ FAIL:', error.message);
    return false;
  }
}

async function testWorkflowIntegration() {
  console.log('\n' + '='.repeat(80));
  console.log('TEST 4: Workflow Integration Example');
  console.log('='.repeat(80));

  // Simulate how a workflow would use the adapter
  const documentContent = `
# Machine Learning Guide

Machine learning is a subset of artificial intelligence that enables systems
to learn and improve from experience without being explicitly programmed.

## Types of ML

1. Supervised Learning - learning from labeled data
2. Unsupervised Learning - finding patterns in unlabeled data
3. Reinforcement Learning - learning through trial and error

## Example Code

Here's a simple example:

def train_model(data, labels):
    model = create_model()
    model.fit(data, labels)
    return model

def predict(model, new_data):
    return model.predict(new_data)
`;

  try {
    // Chunk the document
    const chunks = chunkText(documentContent, {
      minChunkSize: 200,
      maxChunkSize: 600,
      overlapSize: 50
    });

    console.log(`✓ Workflow would process ${chunks.length} chunks`);

    // Simulate processing each chunk
    for (const chunk of chunks) {
      console.log(`  Processing chunk ${chunk.index}:`);
      console.log(`    - Type: ${chunk.chunk_type}`);
      console.log(`    - Has code: ${chunk.has_code}`);
      if (chunk.language) {
        console.log(`    - Language: ${chunk.language}`);
      }
    }

    console.log('✓ Workflow integration test PASSED');
    return true;

  } catch (error) {
    console.error('✗ FAIL:', error.message);
    return false;
  }
}

async function main() {
  console.log('\n' + '='.repeat(80));
  console.log('SEMANTIC CHUNKER ADAPTER TESTS (Node.js)');
  console.log('='.repeat(80));

  const results = [];

  // Run tests
  results.push(['Basic Chunking', await testBasicChunking()]);
  results.push(['Code Detection', await testCodeDetection()]);
  results.push(['Large Text', await testLargeText()]);
  results.push(['Workflow Integration', await testWorkflowIntegration()]);

  // Summary
  console.log('\n' + '='.repeat(80));
  console.log('TEST SUMMARY');
  console.log('='.repeat(80));

  const passed = results.filter(([_, result]) => result).length;
  const total = results.length;

  for (const [testName, result] of results) {
    const status = result ? '✓ PASS' : '✗ FAIL';
    console.log(`  ${status}: ${testName}`);
  }

  console.log('\n' + '='.repeat(80));
  console.log(`RESULTS: ${passed}/${total} tests passed`);
  console.log('='.repeat(80));

  process.exit(passed === total ? 0 : 1);
}

main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
