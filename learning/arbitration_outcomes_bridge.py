#!/usr/bin/env python3
"""
Arbitration Outcomes → Thompson Learning Bridge

Reads arbitration cost/outcome data from Memory Service and provides
Thompson with feedback signals for autonomous model selection optimization.

This bridges:
  Memory Service (arbitration records) → Thompson (model performance priors)

Enables Thompson to answer:
  "Which models succeed on code reviews?"
  "What's the cost-quality tradeoff for security audits?"
  "Should I use Sonnet or Opus for this task scope?"
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import sys
import json
import logging
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

# REST endpoint for ensemble_server (Memory Service access via REST boundary)
ENSEMBLE_SERVER_URL = "http://127.0.0.1:8080"


class ArbitrationOutcomesBridge:
    """Read arbitration outcomes from Memory Service, generate Thompson signals"""

    def __init__(self, memory_client=None, thompson_client=None):
        """Initialize with optional client overrides for testing"""
        self.memory_client = memory_client
        self.thompson_client = thompson_client
        self.ensemble_server_url = ENSEMBLE_SERVER_URL

        if not self.thompson_client:
            try:
                from shared.thompson_client import ThompsonClient
                self.thompson_client = ThompsonClient()
            except Exception as e:
                logger.warning(f"Thompson client unavailable: {e}")

    def read_arbitration_outcomes(self, days: int = 7) -> List[Dict[str, Any]]:
        """Query Memory Service for recent arbitration records via REST endpoint.

        Returns list of arbitration outcome dicts with fields:
          - task_name, task_type, outcome, confidence
          - routing_strategy, routing_confidence
          - total_tokens, total_cost
          - phases (list with per-phase metrics)
        """
        try:
            # Call ensemble_server REST endpoint for semantic search
            # (REST boundary: ensemble_server routes to Memory Service)
            query = f"arbitration outcomes success inconclusive failed"
            url = f"{self.ensemble_server_url}/memory/search"

            response = requests.post(
                url,
                json={"query": query, "limit": 100},
                timeout=5.0
            )
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])

            outcomes = []
            for result in results:
                # Parse memory document to extract structured data
                # result['content'] contains markdown from arbitration record
                outcome = self._parse_arbitration_record(result.get('content', ''))
                if outcome:
                    outcomes.append(outcome)

            logger.info(f"Read {len(outcomes)} arbitration outcomes from Memory Service (REST)")
            return outcomes

        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying Memory Service (REST): {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading arbitration outcomes: {e}")
            return []

    def _parse_arbitration_record(self, memory_doc: str) -> Optional[Dict[str, Any]]:
        """Parse markdown arbitration record into structured outcome.

        Extracts from memory document (e.g., from _build_memory_document()):
          # Arbitration: <task_name>
          **Type:** <task_type>
          **Outcome:** success/inconclusive/failed
          **Confidence:** 85%
          ...
        """
        try:
            outcome = {}

            # Extract task name
            if "# Arbitration:" in memory_doc:
                task_line = [l for l in memory_doc.split('\n') if l.startswith('# Arbitration:')][0]
                outcome['task_name'] = task_line.replace('# Arbitration:', '').strip()

            # Extract task type
            if "**Type:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Type:**' in line:
                        outcome['task_type'] = line.split('**Type:**')[1].strip()

            # Extract outcome
            if "**Outcome:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Outcome:**' in line and 'Task Context' not in memory_doc[:memory_doc.find(line)]:
                        outcome['outcome'] = line.split('**Outcome:**')[1].strip()

            # Extract confidence (convert percentage to decimal)
            if "**Confidence:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Confidence:**' in line:
                        conf_str = line.split('**Confidence:**')[1].strip().rstrip('%')
                        try:
                            outcome['confidence'] = float(conf_str) / 100.0
                        except:
                            pass

            # Extract cost (in summary section)
            if "**Total Cost:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Total Cost:**' in line:
                        cost_str = line.split('**Total Cost:**')[1].strip().lstrip('$')
                        try:
                            outcome['total_cost'] = float(cost_str)
                        except:
                            pass

            # Extract tokens
            if "**Total Tokens:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Total Tokens:**' in line:
                        token_str = line.split('**Total Tokens:**')[1].strip().replace(',', '')
                        try:
                            outcome['total_tokens'] = int(token_str)
                        except:
                            pass

            # Extract routing strategy
            if "**Strategy:**" in memory_doc:
                for line in memory_doc.split('\n'):
                    if '**Strategy:**' in line and 'Thompson Routing' in memory_doc[:memory_doc.find(line)]:
                        outcome['routing_strategy'] = line.split('**Strategy:**')[1].strip()

            return outcome if outcome else None

        except Exception as e:
            logger.debug(f"Error parsing arbitration record: {e}")
            return None

    def generate_thompson_signals(self, outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert arbitration outcomes to Thompson learning signals.

        Generates update for Thompson model:
          - Per model: success rate, avg cost, task type performance
          - Per task type: which models work best
          - Per scope: cost-quality tradeoff
        """
        if not outcomes:
            return {}

        signals = {
            'timestamp': datetime.utcnow().isoformat(),
            'outcome_count': len(outcomes),
            'by_task_type': {},
            'by_model_performance': {},
            'by_scope': {},
        }

        # Aggregate outcomes
        task_type_stats = {}
        model_stats = {}
        scope_stats = {}

        for outcome in outcomes:
            task_type = outcome.get('task_type', 'unknown')
            outcome_val = outcome.get('outcome', 'unknown')
            confidence = outcome.get('confidence', 0.0)
            cost = outcome.get('total_cost', 0.0)
            tokens = outcome.get('total_tokens', 0)

            # Task type stats
            if task_type not in task_type_stats:
                task_type_stats[task_type] = {
                    'count': 0,
                    'success_count': 0,
                    'avg_cost': 0.0,
                    'avg_confidence': 0.0,
                    'total_tokens': 0
                }

            task_type_stats[task_type]['count'] += 1
            if outcome_val == 'success':
                task_type_stats[task_type]['success_count'] += 1
            task_type_stats[task_type]['avg_cost'] += cost
            task_type_stats[task_type]['avg_confidence'] += confidence
            task_type_stats[task_type]['total_tokens'] += tokens

        # Calculate averages
        for task_type, stats in task_type_stats.items():
            count = stats['count']
            signals['by_task_type'][task_type] = {
                'count': count,
                'success_rate': stats['success_count'] / count if count > 0 else 0.0,
                'avg_cost': stats['avg_cost'] / count if count > 0 else 0.0,
                'avg_confidence': stats['avg_confidence'] / count if count > 0 else 0.0,
                'total_tokens': stats['total_tokens'],
            }

        # Per-scope signals
        # (extracted from task_scope in outcomes if available)
        scopes = set()
        for outcome in outcomes:
            # Parse from memory doc or task metadata
            # For now: small < 5K, medium 5K-20K, large > 20K tokens
            tokens = outcome.get('total_tokens', 0)
            if tokens < 5000:
                scope = 'small'
            elif tokens < 20000:
                scope = 'medium'
            else:
                scope = 'large'

            if scope not in scope_stats:
                scope_stats[scope] = {
                    'count': 0,
                    'avg_cost': 0.0,
                    'total_cost': 0.0,
                }

            scope_stats[scope]['count'] += 1
            scope_stats[scope]['avg_cost'] += outcome.get('total_cost', 0.0)
            scope_stats[scope]['total_cost'] += outcome.get('total_cost', 0.0)

        for scope, stats in scope_stats.items():
            count = stats['count']
            signals['by_scope'][scope] = {
                'count': count,
                'avg_cost': stats['avg_cost'] / count if count > 0 else 0.0,
                'total_cost': stats['total_cost'],
            }

        return signals

    def send_signals_to_thompson(self, signals: Dict[str, Any]) -> bool:
        """Send Thompson signals to learning service for model optimization.

        Thompson uses these signals to update model selection priors:
          P(model works for task_type) is updated based on outcomes
          Cost estimates are calibrated from actual arbitration costs
          Routing strategy confidence is validated
        """
        if not self.thompson_client:
            logger.warning("Thompson client not available, cannot send signals")
            return False

        try:
            # Format signal for Thompson
            signal_record = {
                'type': 'arbitration_outcome_batch',
                'timestamp': signals.get('timestamp'),
                'outcome_count': signals.get('outcome_count'),
                'data': signals
            }

            # Send to Thompson via learning client
            # (Thompson client handles REST boundary via learning service)
            success = self.thompson_client.record_feedback(
                feedback_type='arbitration_outcomes',
                data=signal_record
            )

            if success:
                logger.info(f"Sent {signals.get('outcome_count', 0)} arbitration signals to Thompson")
            else:
                logger.warning("Thompson signal delivery failed")

            return success

        except Exception as e:
            logger.error(f"Error sending signals to Thompson: {e}")
            return False

    def run_feedback_loop(self, interval_hours: int = 1) -> None:
        """Run continuous feedback loop: read outcomes → generate signals → update Thompson.

        This runs in background (or as scheduled job) to keep Thompson model fresh.
        """
        logger.info(f"Starting arbitration outcomes feedback loop (interval: {interval_hours}h)")

        try:
            while True:
                try:
                    # Read recent outcomes
                    outcomes = self.read_arbitration_outcomes(days=7)

                    if outcomes:
                        # Generate Thompson signals
                        signals = self.generate_thompson_signals(outcomes)

                        # Send to Thompson
                        self.send_signals_to_thompson(signals)

                        logger.info(f"Feedback loop: processed {len(outcomes)} outcomes")
                    else:
                        logger.debug("No new outcomes in this iteration")

                    # Wait before next iteration
                    import time
                    time.sleep(interval_hours * 3600)

                except Exception as e:
                    logger.error(f"Error in feedback loop: {e}")
                    import time
                    time.sleep(60)  # Brief wait before retry

        except KeyboardInterrupt:
            logger.info("Feedback loop stopped")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bridge = ArbitrationOutcomesBridge()

    # Read recent outcomes
    outcomes = bridge.read_arbitration_outcomes(days=7)
    print(f"Read {len(outcomes)} outcomes")

    if outcomes:
        # Generate signals
        signals = bridge.generate_thompson_signals(outcomes)
        print(f"Generated signals:\n{json.dumps(signals, indent=2)}")

        # Send to Thompson
        success = bridge.send_signals_to_thompson(signals)
        print(f"Thompson update: {'success' if success else 'failed'}")
