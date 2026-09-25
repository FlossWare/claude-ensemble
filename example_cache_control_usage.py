#!/usr/bin/env python3
"""
Example Usage: Claude API cache_control integration

This script demonstrates practical applications of cache_control:
1. Red Hat project documentation caching
2. Multi-query sessions with cost tracking
3. Integration with existing API patterns

Run with:
    export ANTHROPIC_API_KEY='your-key'
    python3 example_cache_control_usage.py
"""

import os
import sys
from cache_control import PromptCacheControl


# ===========================================================================
# Example 1: Red Hat Memory + Docs Caching
# ===========================================================================

def example_1_red_hat_caching():
    """Cache Red Hat project memory + docs, answer multiple questions"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Red Hat Memory + Docs Caching")
    print("="*80)
    print("\nScenario: Team asks multiple questions about claude-global-skills project")
    print("Cache: User memory + RH documentation (remains the same)")
    print("Dynamic: Each question is different\n")

    # Static content (cached)
    memory = """
    # Project Context
    Repository: claude-global-skills
    Purpose: Red Hat fleet orchestration and model routing
    Status: Active development

    Recent work:
    - Implemented fleet executor with parallel task distribution
    - Added PostgreSQL integration for result storage
    - Working on prompt caching for cost optimization

    Known issues:
    - AWX NetworkPolicy restricts GitLab pod communication
    - Sumo Logic API requires special cookie handling
    """

    docs = """
    # Red Hat Development Practices

    Git Workflow:
    - Always create worktrees for branch work
    - Ask before pushing to remote
    - Never force-push main or published branches

    Deployment:
    - starting_at_qa: begins in QA environment
    - only_qa: remains in QA without production deployment
    - Email format: hyperlinks + Jira integration

    Team Availability:
    - EST timezone: csanders, loleary, grgardne
    - IST timezone: ypant, rghandi, vmhaskar
    """

    system_prompt = "You are a Red Hat development assistant helping the team with technical questions."

    # Questions (dynamic, changes each time)
    questions = [
        "What are the main issues preventing AWX connectivity?",
        "How should we approach the Sumo Logic API auth problem?",
        "Summarize the git workflow best practices in 2 sentences.",
    ]

    cache = PromptCacheControl()
    metrics_list = []

    for i, question in enumerate(questions, 1):
        print(f"\n--- Question {i}/3 ---")
        print(f"Q: {question}")

        # Restructure prompt: cacheable content first, query last
        messages = cache.restructure_prompt(
            memory=memory,
            documentation=docs,
            system_prompt=system_prompt,
            user_query=question
        )

        response, metrics = cache.call_with_cache(
            messages=messages,
            cache_eligible_indices=[0, 1, 2],  # Cache memory, docs, system prompt
            model="claude-3-5-sonnet-20241022",
            max_tokens=300
        )

        metrics_list.append(metrics)
        print(f"\nA: {response[:150]}...")
        print(f"   Cache: {'✓ HIT' if metrics.is_cache_hit else '✗ MISS'} | Cost: ${metrics.cost_with_cache:.6f}")

    # Summary
    print("\n--- Summary ---")
    cache.print_comparison(metrics_list)


# ===========================================================================
# Example 2: Large Document Context
# ===========================================================================

def example_2_large_document_caching():
    """Cache a large technical document, answer multiple questions about it"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Large Document Context Caching")
    print("="*80)
    print("\nScenario: Cache a large RFC/spec, answer multiple questions")
    print("Typical use: FAQ, architecture docs, specifications\n")

    # Simulate a large document (in practice, this could be 50KB+)
    large_doc = """
    # CPSEARCH-9479: UXE Integration Architecture

    ## Overview
    Implement integration architecture diagrams in XE Compass per AP-ADR0003.

    ## Components
    1. Query Analyzer: Processes user search intent
    2. Index Router: Routes queries to appropriate Solr indices
    3. Result Aggregator: Combines results from multiple indices
    4. Cache Layer: Caches frequent queries

    ## Keyset Pagination
    Implementation uses Solr cursorMark for efficient pagination.
    Bug: AND vs OR logic inversion in filter application
    Status: In review, fix in next PR

    ## Timeline
    Phase 1 (Sep): Architecture and diagrams
    Phase 2 (Oct): Implementation and testing
    Phase 3 (Nov): QA and refinement
    Phase 4 (Dec): Production deployment

    ## Risks
    - Solr cluster availability during high load
    - Pagination performance with large result sets
    - Cache invalidation across distributed system

    ## Success Criteria
    - All integration tests pass
    - Performance: <100ms 95th percentile latency
    - Uptime: 99.9% availability
    """ * 3  # Repeat to simulate larger document

    cache = PromptCacheControl()

    # Three related questions
    questions = [
        "What are the main components?",
        "Explain the keyset pagination issue",
        "What's the timeline?",
    ]

    print(f"Document size: {len(large_doc):,} characters")
    print(f"Questions to answer: {len(questions)}\n")

    metrics_list = []

    for i, question in enumerate(questions, 1):
        print(f"\n--- Question {i}/{len(questions)} ---")
        print(f"Q: {question}")

        messages = [
            {"role": "user", "content": f"[CACHED DOCUMENT]\n{large_doc}"},
            {"role": "user", "content": f"Based on the document above: {question}"}
        ]

        response, metrics = cache.call_with_cache(
            messages=messages,
            cache_eligible_indices=[0],  # Only cache the document
            model="claude-3-5-sonnet-20241022",
            max_tokens=250
        )

        metrics_list.append(metrics)
        print(f"\nA: {response[:120]}...")
        print(f"   Cache: {'✓ HIT' if metrics.is_cache_hit else '✗ MISS'} | Saved: ${metrics.savings:.6f}")

    print("\n--- Overall Statistics ---")
    total_cost_without = sum(m.cost_without_cache for m in metrics_list)
    total_cost_with = sum(m.cost_with_cache for m in metrics_list)
    total_savings = total_cost_without - total_cost_with

    print(f"Total cost without cache: ${total_cost_without:.6f}")
    print(f"Total cost with cache: ${total_cost_with:.6f}")
    print(f"Total savings: ${total_savings:.6f} ({(total_savings/total_cost_without*100):.1f}%)")


# ===========================================================================
# Example 3: Interactive Session with Cache Reuse
# ===========================================================================

def example_3_interactive_session():
    """Simulate an interactive Q&A session reusing cache"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Interactive Q&A Session")
    print("="*80)
    print("\nScenario: User has context and asks follow-up questions")
    print("Cache reuse: Memory/docs cached once, reused for all follow-ups\n")

    memory = """
    User is exploring cache control implementation.
    They've read the documentation and run initial tests.
    Now asking follow-up questions.
    """

    context = """
    Cache Control Facts:
    - Cache miss (creation): tokens cost 1.25x normal
    - Cache hit (read): tokens cost 0.1x normal
    - Cache TTL: 5 minutes of inactivity
    - Break-even: typically 3-5 requests
    - Best for: large context + repeated queries
    """

    cache = PromptCacheControl()

    # Simulate follow-up questions
    follow_ups = [
        "Why do cache creation tokens cost more?",
        "How do I integrate cache_control into my API?",
        "What happens if the cache expires?",
    ]

    print("Initial context cached, now processing follow-up questions...\n")

    metrics_list = []

    for i, question in enumerate(follow_ups, 1):
        print(f"\nQ{i}: {question}")

        messages = cache.restructure_prompt(
            memory=memory,
            documentation="",  # Not using docs this time
            system_prompt=context,
            user_query=question
        )

        response, metrics = cache.call_with_cache(
            messages=messages,
            cache_eligible_indices=[0, 2],  # Cache memory and system (context)
            model="claude-3-5-sonnet-20241022",
            max_tokens=200
        )

        metrics_list.append(metrics)
        print(f"A: {response[:100]}...")

    print("\n--- Session Summary ---")
    cache_hits = sum(1 for m in metrics_list if m.is_cache_hit)
    total_saved = sum(m.savings for m in metrics_list)

    print(f"Total requests: {len(metrics_list)}")
    print(f"Cache hits: {cache_hits}/{len(metrics_list)}")
    print(f"Total cost: ${sum(m.cost_with_cache for m in metrics_list):.6f}")
    print(f"Total savings: ${total_saved:.6f}")


# ===========================================================================
# Example 4: Cost-Benefit Analysis
# ===========================================================================

def example_4_cost_analysis():
    """Show concrete cost analysis for cache vs non-cache scenarios"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Cost-Benefit Analysis")
    print("="*80)

    cache = PromptCacheControl()

    scenarios = [
        {
            "name": "Single Query (No Savings)",
            "num_requests": 1,
            "context_tokens": 2000,
            "query_tokens": 100,
        },
        {
            "name": "3 Identical Queries",
            "num_requests": 3,
            "context_tokens": 2000,
            "query_tokens": 100,
        },
        {
            "name": "10 Different Queries",
            "num_requests": 10,
            "context_tokens": 2000,
            "query_tokens": 100,
        },
        {
            "name": "Large Doc + Many Queries",
            "num_requests": 20,
            "context_tokens": 10000,
            "query_tokens": 200,
        },
    ]

    print("\nEstimated costs for different scenarios (Sonnet 3.5):\n")
    print(f"{'Scenario':<30} {'Without Cache':<15} {'With Cache':<15} {'Savings':<12} {'Savings %':<10}")
    print("-" * 82)

    for scenario in scenarios:
        name = scenario["name"]
        n = scenario["num_requests"]
        ctx = scenario["context_tokens"]
        q = scenario["query_tokens"]

        # Without cache: all requests pay full price
        cost_without = (n * (ctx + q)) * 0.003 / 1000

        # With cache: first request creates cache, rest use cache
        # First: context (cache creation @1.25x) + query (normal) + output
        # Rest: context (cache read @0.1x) + query (normal) + output
        cost_first = (ctx * 0.00375 + q * 0.003) / 1000
        cost_rest = ((ctx * 0.0003 + q * 0.003) / 1000) * (n - 1)
        cost_with = cost_first + cost_rest

        savings = cost_without - cost_with
        savings_pct = (savings / cost_without * 100) if cost_without > 0 else 0

        print(f"{name:<30} ${cost_without:<14.6f} ${cost_with:<14.6f} ${savings:<11.6f} {savings_pct:<9.1f}%")

    print("\nKey Insights:")
    print("  • Single query: No benefit (cache creation costs more)")
    print("  • 3+ queries: Start seeing savings (5-10%)")
    print("  • 10+ queries: Significant savings (30-40%)")
    print("  • Large context + many queries: Best ROI (50-70%+)")


# ===========================================================================
# Main
# ===========================================================================

def main():
    """Run all examples"""
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Set with: export ANTHROPIC_API_KEY='your-key'")
        return False

    try:
        # Run examples
        example_1_red_hat_caching()
        example_2_large_document_caching()
        example_3_interactive_session()
        example_4_cost_analysis()

        print("\n" + "="*80)
        print("All examples completed successfully!")
        print("="*80)
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
