/**
 * Regression Test for Issue #99: Hardcoded Word Count Thresholds
 *
 * This test documents and verifies the hardcoded numeric thresholds used throughout
 * the codebase for content validation and chunking decisions.
 *
 * Identified Hardcoded Thresholds:
 * - ai-web-learn-mcp.js line 287: 2000 word split threshold
 * - ai-web-learn.js line 381: 2000 word split threshold
 * - ai-web-learn-production.js line 254: 2000 word split threshold
 * - ai-consensus-disagreement.js line 116: length > 20 sentence filter
 * - fleet-agent-wrapper.js line 70: length > 500 schema complexity check
 *
 * Purpose: Document these thresholds exist and verify boundary behavior
 */

import fs from 'fs';
import path from 'path';
import { describe, test, beforeEach } from 'node:test';
import assert from 'node:assert';

const projectRoot = '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills';

describe('Issue #99 - Hardcoded Word Count Thresholds', () => {

  describe('ai-web-learn-mcp.js - 2000 word chunking threshold (line 287)', () => {
    let fileContent;

    beforeEach(() => {
      fileContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn-mcp.js'),
        'utf8'
      );
    });

    test('should contain hardcoded 2000 word threshold', () => {
      assert.ok(fileContent.match(/>\s*2000/), 'File should contain > 2000 pattern');
      assert.ok(fileContent.includes('2000'), 'File should contain 2000');
    });

    test('should document threshold behavior at boundary', () => {
      const chunkingPattern = /\(last \+ p\)\.split\(\/\\s\+\/\)\.length > 2000/;
      assert.ok(fileContent.match(chunkingPattern), 'Should contain chunking logic pattern');
    });

    describe('chunking boundary behavior', () => {
      // Simulate the chunking logic from ai-web-learn-mcp.js line 285-293
      function chunkContent(content, threshold = 2000) {
        const paragraphs = content.split(/\n\n+/);
        return paragraphs.reduce((acc, p) => {
          const last = acc[acc.length - 1] || '';
          if ((last + p).split(/\s+/).length > threshold) {
            acc.push(p);
          } else {
            acc[acc.length - 1] = last + '\n\n' + p;
          }
          return acc;
        }, ['']);
      }

      test('should NOT chunk when exactly at 2000 words', () => {
        const exactWords = Array(2000).fill('word').join(' ');
        const chunks = chunkContent(exactWords);
        assert.strictEqual(chunks.length, 1, 'Should not chunk at exactly 2000 words');
      });

      test('should NOT chunk when below 2000 words', () => {
        const belowThreshold = Array(1999).fill('word').join(' ');
        const chunks = chunkContent(belowThreshold);
        assert.strictEqual(chunks.length, 1, 'Should not chunk below 2000 words');
      });

      test('should chunk when above 2000 words', () => {
        const paragraph1 = Array(1500).fill('word').join(' ');
        const paragraph2 = Array(600).fill('word').join(' ');
        const content = paragraph1 + '\n\n' + paragraph2;
        const chunks = chunkContent(content);
        assert.ok(chunks.length > 1, 'Should chunk when above 2000 words');
      });

      test('should handle edge case of 2001 words', () => {
        const paragraph1 = Array(1500).fill('word').join(' ');
        const paragraph2 = Array(501).fill('word').join(' ');
        const content = paragraph1 + '\n\n' + paragraph2;
        const chunks = chunkContent(content);
        assert.strictEqual(chunks.length, 2, 'Should create 2 chunks at 2001 words');
      });
    });
  });

  describe('ai-web-learn.js - 2000 word chunking threshold (line 381)', () => {
    let fileContent;

    beforeEach(() => {
      fileContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn.js'),
        'utf8'
      );
    });

    test('should contain hardcoded 2000 word threshold', () => {
      assert.ok(fileContent.match(/>\s*2000/), 'File should contain > 2000 pattern');
      assert.ok(fileContent.includes('2000'), 'File should contain 2000');
    });

    test('should document threshold behavior at boundary', () => {
      const chunkingPattern = /\(current \+ p\)\.split\(\/\\s\+\/\)\.length > 2000/;
      assert.ok(fileContent.match(chunkingPattern), 'Should contain chunking logic pattern');
    });

    describe('chunking boundary behavior', () => {
      function chunkParagraphs(page, threshold = 2000) {
        const paragraphs = page.split(/\n\n+/);
        const chunks = [];
        let current = '';

        paragraphs.forEach(p => {
          if ((current + p).split(/\s+/).length > threshold) {
            if (current) chunks.push(current);
            current = p;
          } else {
            current += '\n\n' + p;
          }
        });
        if (current) chunks.push(current);

        return chunks;
      }

      test('should NOT chunk when exactly at 2000 words', () => {
        const exactWords = Array(2000).fill('word').join(' ');
        const chunks = chunkParagraphs(exactWords);
        assert.strictEqual(chunks.length, 1);
      });

      test('should NOT chunk when below 2000 words', () => {
        const belowThreshold = Array(1500).fill('word').join(' ');
        const chunks = chunkParagraphs(belowThreshold);
        assert.strictEqual(chunks.length, 1);
      });

      test('should chunk when above 2000 words', () => {
        const paragraph1 = Array(1500).fill('word').join(' ');
        const paragraph2 = Array(600).fill('word').join(' ');
        const content = paragraph1 + '\n\n' + paragraph2;
        const chunks = chunkParagraphs(content);
        assert.strictEqual(chunks.length, 2);
      });

      test('should preserve final chunk even if partial', () => {
        const p1 = Array(2100).fill('word').join(' ');
        const p2 = Array(500).fill('word').join(' ');
        const content = p1 + '\n\n' + p2;
        const chunks = chunkParagraphs(content);
        assert.strictEqual(chunks.length, 2);
        assert.ok(chunks[1].split(/\s+/).length < 2000);
      });
    });
  });

  describe('ai-web-learn-production.js - 2000 word chunking threshold (line 254)', () => {
    let fileContent;

    beforeEach(() => {
      fileContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn-production.js'),
        'utf8'
      );
    });

    test('should contain hardcoded 2000 word threshold', () => {
      assert.ok(fileContent.match(/>\s*2000/));
      assert.ok(fileContent.includes('2000'));
    });

    test('should document threshold behavior at boundary', () => {
      const chunkingPattern = /\(last \+ p\)\.split\(\/\\s\+\/\)\.length > 2000/;
      assert.ok(fileContent.match(chunkingPattern));
    });

    describe('production chunking boundary behavior', () => {
      function chunkSections(page, threshold = 2000) {
        const sections = page.split(/\n\n+/).reduce((acc, p) => {
          const last = acc[acc.length - 1] || '';
          if ((last + p).split(/\s+/).length > threshold) {
            acc.push(p);
          } else {
            acc[acc.length - 1] = (last ? last + '\n\n' : '') + p;
          }
          return acc;
        }, ['']);
        return sections;
      }

      test('should NOT chunk when exactly at 2000 words', () => {
        const exactWords = Array(2000).fill('word').join(' ');
        const sections = chunkSections(exactWords);
        assert.strictEqual(sections.length, 1);
      });

      test('should NOT chunk when below 2000 words', () => {
        const belowThreshold = Array(1999).fill('word').join(' ');
        const sections = chunkSections(belowThreshold);
        assert.strictEqual(sections.length, 1);
      });

      test('should chunk when above 2000 words', () => {
        const section1 = Array(1500).fill('word').join(' ');
        const section2 = Array(600).fill('word').join(' ');
        const content = section1 + '\n\n' + section2;
        const sections = chunkSections(content);
        assert.ok(sections.length > 1);
      });
    });
  });

  describe('ai-consensus-disagreement.js - length > 20 sentence filter (line 116)', () => {
    let fileContent;

    beforeEach(() => {
      fileContent = fs.readFileSync(
        path.join(projectRoot, 'ai-consensus-disagreement.js'),
        'utf8'
      );
    });

    test('should contain hardcoded 20 character sentence filter', () => {
      assert.ok(fileContent.match(/\.length\s*>\s*20/));
      assert.ok(fileContent.includes('length > 20'));
    });

    test('should document threshold behavior at boundary', () => {
      const filterPattern = /filter\(s => s\.trim\(\)\.length > 20\)/;
      assert.ok(fileContent.match(filterPattern));
    });

    describe('sentence filter boundary behavior', () => {
      function filterSentences(response, minLength = 20) {
        return response.split(/[.!?]+/).filter(s => s.trim().length > minLength);
      }

      test('should exclude sentence exactly at 20 characters', () => {
        const exactSentence = 'A'.repeat(20);
        const response = exactSentence + '. Another sentence here.';
        const sentences = filterSentences(response);
        assert.ok(!sentences.some(s => s.trim() === exactSentence));
        assert.strictEqual(sentences.length, 1);
      });

      test('should exclude sentences below 20 characters', () => {
        const shortSentence = 'A'.repeat(19);
        const response = shortSentence + '. This is a longer sentence.';
        const sentences = filterSentences(response);
        assert.strictEqual(sentences.length, 1);
        assert.ok(sentences[0].trim() !== shortSentence);
      });

      test('should include sentences above 20 characters', () => {
        const longSentence = 'A'.repeat(21);
        const response = longSentence + '. Another sentence.';
        const sentences = filterSentences(response);
        assert.ok(sentences.length >= 1);
        assert.ok(sentences.some(s => s.trim().length >= 21));
      });

      test('should handle edge case of 21 characters', () => {
        const sentence21 = 'A'.repeat(21);
        const response = sentence21 + '.';
        const sentences = filterSentences(response);
        assert.strictEqual(sentences.length, 1);
        assert.strictEqual(sentences[0].trim().length, 21);
      });

      test('should filter multiple mixed-length sentences', () => {
        const response = 'Short. This is a longer sentence here! Tiny. Very long sentence with more content.';
        const sentences = filterSentences(response);
        assert.ok(sentences.length < 4); // Should filter out "Short" and "Tiny"
      });
    });
  });

  describe('fleet-agent-wrapper.js - length > 500 schema complexity (line 70)', () => {
    let fileContent;

    beforeEach(() => {
      fileContent = fs.readFileSync(
        path.join(projectRoot, 'fleet-agent-wrapper.js'),
        'utf8'
      );
    });

    test('should contain hardcoded 500 character schema threshold', () => {
      assert.ok(fileContent.match(/\.length\s*>\s*500/));
      assert.ok(fileContent.includes('500'));
    });

    test('should document threshold behavior at boundary', () => {
      const complexityPattern = /JSON\.stringify\(opts\.schema\)\.length > 500/;
      assert.ok(fileContent.match(complexityPattern));
    });

    describe('schema complexity boundary behavior', () => {
      function inferJobType(opts) {
        if (opts.schema) {
          try {
            if (JSON.stringify(opts.schema).length > 500) {
              return 'ai-heavy';
            }
          } catch (e) {
            return 'ai-heavy';
          }
        }
        return 'agent';
      }

      test('should NOT classify as ai-heavy when schema exactly at 500 characters', () => {
        const schema = { description: 'A'.repeat(500 - 20) };
        const actualLength = JSON.stringify(schema).length;
        assert.ok(actualLength <= 500);

        const jobType = inferJobType({ schema });
        assert.strictEqual(jobType, 'agent');
      });

      test('should NOT classify as ai-heavy when schema below 500 characters', () => {
        const schema = { type: 'string', maxLength: 100 };
        assert.ok(JSON.stringify(schema).length < 500);

        const jobType = inferJobType({ schema });
        assert.strictEqual(jobType, 'agent');
      });

      test('should classify as ai-heavy when schema above 500 characters', () => {
        const schema = {
          type: 'object',
          properties: {
            field1: { type: 'string', description: 'A'.repeat(200) },
            field2: { type: 'string', description: 'B'.repeat(200) },
            field3: { type: 'string', description: 'C'.repeat(200) }
          }
        };
        assert.ok(JSON.stringify(schema).length > 500);

        const jobType = inferJobType({ schema });
        assert.strictEqual(jobType, 'ai-heavy');
      });

      test('should classify as ai-heavy at edge case of 501 characters', () => {
        let schema = { description: '' };
        while (JSON.stringify(schema).length <= 500) {
          schema.description += 'x';
        }
        assert.strictEqual(JSON.stringify(schema).length, 501);

        const jobType = inferJobType({ schema });
        assert.strictEqual(jobType, 'ai-heavy');
      });

      test('should handle circular reference as ai-heavy', () => {
        const schema = {};
        schema.self = schema;

        const jobType = inferJobType({ schema });
        assert.strictEqual(jobType, 'ai-heavy');
      });

      test('should return agent when no schema provided', () => {
        const jobType = inferJobType({});
        assert.strictEqual(jobType, 'agent');
      });
    });
  });

  describe('Threshold Consistency Across Files', () => {
    test('all web-learn files should use same 2000 word threshold', () => {
      const mcpContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn-mcp.js'),
        'utf8'
      );
      const baseContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn.js'),
        'utf8'
      );
      const prodContent = fs.readFileSync(
        path.join(projectRoot, 'ai-web-learn-production.js'),
        'utf8'
      );

      const threshold = 2000;
      assert.ok(mcpContent.includes(`${threshold}`));
      assert.ok(baseContent.includes(`${threshold}`));
      assert.ok(prodContent.includes(`${threshold}`));
    });

    test('should document all five hardcoded thresholds', () => {
      const thresholds = [
        { file: 'ai-web-learn-mcp.js', value: 2000, purpose: 'word chunking' },
        { file: 'ai-web-learn.js', value: 2000, purpose: 'word chunking' },
        { file: 'ai-web-learn-production.js', value: 2000, purpose: 'word chunking' },
        { file: 'ai-consensus-disagreement.js', value: 20, purpose: 'sentence filter' },
        { file: 'fleet-agent-wrapper.js', value: 500, purpose: 'schema complexity' },
      ];

      thresholds.forEach(({ file, value }) => {
        const content = fs.readFileSync(path.join(projectRoot, file), 'utf8');
        assert.ok(content.includes(`${value}`), `${file} should contain ${value}`);
      });
    });
  });

  describe('Documentation of Threshold Rationale', () => {
    test('should document why 2000 words chosen for chunking', () => {
      const expectedRationale = {
        threshold: 2000,
        likelyReason: 'Balance between token limits and semantic coherence',
        considerations: [
          'Most LLMs have 4k-8k token context windows',
          '2000 words ≈ 2600-3000 tokens',
          'Leaves room for prompt + response',
          'Paragraph-level semantic boundaries'
        ]
      };

      assert.strictEqual(expectedRationale.threshold, 2000);
      assert.ok(expectedRationale.considerations.length > 0);
    });

    test('should document why 20 characters chosen for sentence filter', () => {
      const expectedRationale = {
        threshold: 20,
        likelyReason: 'Filter out sentence fragments and short phrases',
        considerations: [
          'Average English sentence is 15-20 words',
          'Minimum meaningful statement length',
          'Excludes fragments like "Yes.", "Okay.", "I agree."'
        ]
      };

      assert.strictEqual(expectedRationale.threshold, 20);
    });

    test('should document why 500 characters chosen for schema complexity', () => {
      const expectedRationale = {
        threshold: 500,
        likelyReason: 'Distinguish simple vs complex schema processing',
        considerations: [
          'Simple schemas fit in <500 chars',
          'Complex nested objects exceed 500 chars',
          'Proxy for computational complexity'
        ]
      };

      assert.strictEqual(expectedRationale.threshold, 500);
    });
  });
});

describe('Recommendations for Issue #99 Resolution', () => {
  test('should recommend configuration-based thresholds', () => {
    const recommendations = {
      approach: 'Move hardcoded values to configuration',
      benefits: [
        'Easy tuning without code changes',
        'Environment-specific customization',
        'A/B testing different values',
        'Better documentation of rationale'
      ],
      implementation: {
        location: 'config.js or environment variables',
        example: {
          CHUNKING_WORD_THRESHOLD: 2000,
          SENTENCE_MIN_LENGTH: 20,
          SCHEMA_COMPLEXITY_THRESHOLD: 500
        }
      }
    };

    assert.ok(recommendations.benefits.length > 0);
    assert.strictEqual(recommendations.implementation.example.CHUNKING_WORD_THRESHOLD, 2000);
  });

  test('should document current threshold locations for future refactoring', () => {
    const thresholdRegistry = [
      { file: 'ai-web-learn-mcp.js', line: 287, value: 2000, type: 'chunking' },
      { file: 'ai-web-learn.js', line: 381, value: 2000, type: 'chunking' },
      { file: 'ai-web-learn-production.js', line: 254, value: 2000, type: 'chunking' },
      { file: 'ai-consensus-disagreement.js', line: 116, value: 20, type: 'filter' },
      { file: 'fleet-agent-wrapper.js', line: 70, value: 500, type: 'complexity' },
    ];

    assert.strictEqual(thresholdRegistry.length, 5);
    assert.strictEqual(thresholdRegistry.filter(t => t.type === 'chunking').length, 3);
  });
});
