#!/bin/bash
# Test Counterfactual Reasoning System with various what-if scenarios

echo "=================================================================="
echo "COUNTERFACTUAL REASONING SYSTEM - SCENARIO ANALYSIS"
echo "=================================================================="
echo ""

SCENARIOS=(
    # Low risk - configuration
    "What if we increase connection pool size from 10 to 50?"
    "What if we enable debug logging in development?"
    "What if we cache API responses for 5 minutes?"

    # Medium risk - code changes
    "What if we add rate limiting to all public endpoints?"
    "What if we implement request retries with exponential backoff?"
    "What if we refactor database queries to use async?"

    # High risk - architecture
    "What if we switch from REST to GraphQL?"
    "What if we migrate session storage from Redis to PostgreSQL?"
    "What if we upgrade Django from 3.2 to 5.0?"

    # Critical risk - breaking changes
    "What if we remove support for API v1 used by 40% of clients?"
    "What if we change user ID format from integer to UUID?"
    "What if we disable HTTP and enforce HTTPS only in production?"

    # Version upgrades
    "What if we upgrade Python from 3.9 to 3.13?"
    "What if we upgrade Node.js from 18 to 22?"

    # Data changes
    "What if we add foreign key constraint to 100M row table?"
    "What if we delete unused columns from production database?"

    # Security changes
    "What if we require 2FA for all users?"
    "What if we rotate all production API keys?"
)

for scenario in "${SCENARIOS[@]}"; do
    echo "=================================================================="
    echo "SCENARIO: $scenario"
    echo "=================================================================="

    result=$(python3 "$(dirname "$0")/predict_counterfactual.py" "$scenario" 2>/dev/null)

    impact=$(echo "$result" | jq -r '.impact_severity' 2>/dev/null)
    success=$(echo "$result" | jq -r '.success_probability' 2>/dev/null)
    risk=$(echo "$result" | jq -r '.risk_score' 2>/dev/null)
    recommendation=$(echo "$result" | jq -r '.recommendation' 2>/dev/null)

    if [ $? -eq 0 ]; then
        echo "Impact:         $impact"
        echo "Success:        $(printf "%.0f%%" $(echo "$success * 100" | bc))"
        echo "Risk Score:     $(printf "%.0f%%" $(echo "$risk * 100" | bc))"
        echo "Recommendation: $recommendation"
    else
        echo "ERROR: Failed to predict scenario"
    fi

    echo ""
done

echo "=================================================================="
echo "ANALYSIS COMPLETE"
echo "=================================================================="
