#!/usr/bin/env node
/**
 * Knowledge System CLI - Command-line tool for managing knowledge storage
 *
 * Usage:
 *   # Store knowledge
 *   knowledge-cli.js store --content "..." --source "..." --type "..."
 *
 *   # Search knowledge
 *   knowledge-cli.js search "query" [--limit 10] [--type web_synthesis]
 *
 *   # Get stats
 *   knowledge-cli.js stats
 *
 *   # Get provenance
 *   knowledge-cli.js provenance <entry_id>
 */

import { getKnowledgeSystem, isAvailable } from '../shared/knowledge-system-adapter.js';

function printUsage() {
  console.log(`
Knowledge System CLI

Usage:
  knowledge-cli.js store --content "..." --source "..." [--type "..."] [--metadata "{}"]
  knowledge-cli.js search "query" [--limit 10] [--type <source_type>] [--min-similarity 0.5]
  knowledge-cli.js stats
  knowledge-cli.js provenance <entry_id>

Examples:
  # Store knowledge
  knowledge-cli.js store --content "PostgreSQL is fast" --source "manual" --type "documentation"

  # Search
  knowledge-cli.js search "vector database" --limit 5

  # Stats
  knowledge-cli.js stats

  # Provenance
  knowledge-cli.js provenance 123
  `);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    printUsage();
    process.exit(0);
  }

  if (!isAvailable()) {
    console.error('❌ Knowledge system not available');
    console.error('   Check PostgreSQL connection and Python dependencies');
    process.exit(1);
  }

  const ks = getKnowledgeSystem();
  const command = args[0];

  try {
    if (command === 'store') {
      // Parse args
      let content, source, source_type = 'manual', metadata = {};

      for (let i = 1; i < args.length; i += 2) {
        const flag = args[i];
        const value = args[i + 1];

        if (flag === '--content') content = value;
        else if (flag === '--source') source = value;
        else if (flag === '--type') source_type = value;
        else if (flag === '--metadata') metadata = JSON.parse(value);
      }

      if (!content || !source) {
        console.error('❌ --content and --source are required');
        process.exit(1);
      }

      const entryId = await ks.storeKnowledge({
        content,
        source,
        source_type,
        metadata,
        actor: 'cli',
      });

      console.log(`✅ Stored entry ${entryId}`);
    } else if (command === 'search') {
      const query = args[1];
      if (!query) {
        console.error('❌ Query is required');
        process.exit(1);
      }

      const options = {};
      for (let i = 2; i < args.length; i += 2) {
        const flag = args[i];
        const value = args[i + 1];

        if (flag === '--limit') options.limit = parseInt(value);
        else if (flag === '--type') options.source_type = value;
        else if (flag === '--min-similarity') options.min_similarity = parseFloat(value);
      }

      const results = await ks.semanticSearch(query, options);

      console.log(`\nFound ${results.length} results:\n`);
      for (const r of results) {
        console.log(`[${r.id}] ${r.source_type} (similarity: ${r.similarity.toFixed(3)})`);
        console.log(`  Source: ${r.source}`);
        console.log(`  Content: ${r.content.substring(0, 150)}...`);
        if (r.metadata && Object.keys(r.metadata).length > 0) {
          console.log(`  Metadata:`, JSON.stringify(r.metadata, null, 2));
        }
        console.log('');
      }
    } else if (command === 'stats') {
      const stats = await ks.getStats();

      console.log('\nKnowledge System Statistics:\n');
      console.log(`Total entries: ${stats.total_entries}`);
      console.log('\nBy source type:');
      for (const [type, count] of Object.entries(stats.by_source_type)) {
        console.log(`  ${type}: ${count}`);
      }
    } else if (command === 'provenance') {
      const entryId = parseInt(args[1]);
      if (isNaN(entryId)) {
        console.error('❌ Entry ID must be a number');
        process.exit(1);
      }

      const provenance = await ks.getProvenance(entryId);

      console.log(`\nProvenance for entry ${entryId}:\n`);
      for (const p of provenance) {
        console.log(`[${p.timestamp}] ${p.action} by ${p.actor}`);
        if (p.details && Object.keys(p.details).length > 0) {
          console.log(`  Details:`, JSON.stringify(p.details, null, 2));
        }
      }
    } else {
      console.error(`❌ Unknown command: ${command}`);
      printUsage();
      process.exit(1);
    }
  } catch (err) {
    console.error(`❌ Error: ${err.message}`);
    process.exit(1);
  }
}

main();
