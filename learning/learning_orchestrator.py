#!/usr/bin/env python3
"""
Learning Orchestrator — Unified REST Endpoint

Orchestrates all learning components (arbitration outcomes, graph population,
Thompson signals) through a single REST endpoint.

This is the "conductor" that:
1. Reads arbitration outcomes from Memory Service
2. Populates graph database with relationships
3. Generates Thompson learning signals
4. Feeds Thompson model with all insights

REST API:
  POST /learning/sync-outcomes   → Read outcomes + populate graph + update Thompson
  GET  /learning/status          → Status of all learning components
  GET  /learning/graph/query     → Graph query endpoint
  POST /learning/thompson/query  → Thompson model query
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

ENSEMBLE_SERVER_URL = "http://127.0.0.1:8080"


class LearningOrchestrator:
    """Orchestrate all learning components"""

    def __init__(self):
        self.ensemble_server_url = ENSEMBLE_SERVER_URL
        # Lazy-load bridges on first use
        self.arbitration_bridge = None
        self.graph_bridge = None
        self.thompson_client = None

    def _ensure_bridges(self) -> bool:
        """Lazy-load bridges"""
        if self.arbitration_bridge is None:
            try:
                from arbitration_outcomes_bridge import ArbitrationOutcomesBridge
                self.arbitration_bridge = ArbitrationOutcomesBridge()
            except Exception as e:
                logger.warning(f"Could not load ArbitrationOutcomesBridge: {e}")
                return False

        if self.graph_bridge is None:
            try:
                from graph_outcomes_bridge import GraphOutcomesBridge
                self.graph_bridge = GraphOutcomesBridge()
            except Exception as e:
                logger.warning(f"Could not load GraphOutcomesBridge: {e}")
                return False

        if self.thompson_client is None:
            try:
                from shared.thompson_client import ThompsonClient
                self.thompson_client = ThompsonClient()
            except Exception as e:
                logger.warning(f"Could not load Thompson client: {e}")

        return True

    def sync_all_outcomes(self, days: int = 7) -> Dict[str, Any]:
        """Full sync: read outcomes → populate graph → update Thompson.

        This is the "end-to-end learning loop" that happens on a schedule
        (e.g., hourly) to keep all components in sync.

        Circuit Breaker Pattern:
        - CRITICAL steps: graph population (step 2) — fail-fast on error
        - OPTIONAL steps: Thompson update (step 4) — log but continue
        - Early return on critical failures
        - Explicit error propagation

        Steps:
        1. Read arbitration outcomes from Memory Service (CRITICAL)
        2. Populate graph with outcome nodes/edges (CRITICAL)
        3. Generate Thompson signals from outcomes (CRITICAL)
        4. Send Thompson signals for model optimization (OPTIONAL)
        """
        if not self._ensure_bridges():
            return {
                'ok': False,
                'error': 'Learning components not available'
            }

        result = {
            'ok': True,
            'timestamp': datetime.utcnow().isoformat(),
            'steps': {}
        }

        try:
            # Step 1: Read outcomes (CRITICAL)
            logger.info("Step 1: Reading arbitration outcomes from Memory Service...")
            try:
                outcomes = self.arbitration_bridge.read_arbitration_outcomes(days=days)
                result['steps']['read_outcomes'] = {
                    'status': 'success',
                    'count': len(outcomes),
                    'critical': True,
                }
            except Exception as e:
                logger.error(f"CRITICAL: Step 1 (read outcomes) failed: {e}", exc_info=True)
                result['ok'] = False
                result['error'] = f"Failed to read arbitration outcomes: {str(e)}"
                result['steps']['read_outcomes'] = {
                    'status': 'failed',
                    'critical': True,
                    'error': str(e),
                }
                return result  # Early return on critical failure

            if not outcomes:
                logger.info("No outcomes to process")
                return result

            # Step 2: Populate graph (CRITICAL)
            logger.info("Step 2: Populating graph database...")
            try:
                graph_success = self.graph_bridge.populate_graph_from_outcomes(outcomes)
                if not graph_success:
                    raise RuntimeError("Graph population returned False")
                result['steps']['populate_graph'] = {
                    'status': 'success',
                    'critical': True,
                }
            except Exception as e:
                logger.error(f"CRITICAL: Step 2 (populate graph) failed: {e}", exc_info=True)
                result['ok'] = False
                result['error'] = f"Failed to populate graph: {str(e)}"
                result['steps']['populate_graph'] = {
                    'status': 'failed',
                    'critical': True,
                    'error': str(e),
                }
                return result  # Early return on critical failure

            # Step 3: Generate Thompson signals (CRITICAL)
            logger.info("Step 3: Generating Thompson learning signals...")
            try:
                signals = self.arbitration_bridge.generate_thompson_signals(outcomes)
                if not signals:
                    raise RuntimeError("Signal generation returned None or empty")
                result['steps']['generate_signals'] = {
                    'status': 'success',
                    'signal_count': signals.get('outcome_count', 0),
                    'critical': True,
                }
            except Exception as e:
                logger.error(f"CRITICAL: Step 3 (generate signals) failed: {e}", exc_info=True)
                result['ok'] = False
                result['error'] = f"Failed to generate Thompson signals: {str(e)}"
                result['steps']['generate_signals'] = {
                    'status': 'failed',
                    'critical': True,
                    'error': str(e),
                }
                return result  # Early return on critical failure

            # Step 4: Send to Thompson (OPTIONAL)
            logger.info("Step 4: Sending signals to Thompson model...")
            if self.thompson_client:
                try:
                    success = self.arbitration_bridge.send_signals_to_thompson(signals)
                    result['steps']['thompson_update'] = {
                        'status': 'success' if success else 'failed',
                        'critical': False,
                    }
                    if not success:
                        logger.warning("Step 4 (Thompson update) returned False; pipeline continues")
                except Exception as e:
                    logger.warning(f"OPTIONAL: Step 4 (Thompson update) failed: {e}")
                    result['steps']['thompson_update'] = {
                        'status': 'failed',
                        'critical': False,
                        'error': str(e),
                        'note': 'Pipeline continues despite optional step failure'
                    }
            else:
                logger.warning("Thompson client not available, skipping model update")
                result['steps']['thompson_update'] = {
                    'status': 'skipped',
                    'critical': False,
                    'reason': 'Thompson client unavailable'
                }

            logger.info(f"Learning sync complete: processed {len(outcomes)} outcomes")
            return result

        except Exception as e:
            # Catch-all for unexpected errors outside step-specific handlers
            logger.error(f"Unexpected error in learning sync: {e}", exc_info=True)
            result['ok'] = False
            result['error'] = f"Unexpected error: {str(e)}"
            return result

    def get_learning_status(self) -> Dict[str, Any]:
        """Get status of all learning components"""
        if not self._ensure_bridges():
            return {
                'ok': False,
                'components': {
                    'arbitration_bridge': 'unavailable',
                    'graph_bridge': 'unavailable',
                    'thompson_client': 'unavailable',
                    'memory_service': 'unknown',
                    'graph_service': 'unknown',
                }
            }

        status = {
            'ok': True,
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'arbitration_bridge': 'loaded' if self.arbitration_bridge else 'unavailable',
                'graph_bridge': 'loaded' if self.graph_bridge else 'unavailable',
                'thompson_client': 'loaded' if self.thompson_client else 'unavailable',
            }
        }

        # Check external service availability
        try:
            # Check Memory Service via REST
            response = requests.get(
                f"{self.ensemble_server_url}/memory/status",
                timeout=2.0
            )
            status['components']['memory_service'] = 'available' if response.status_code == 200 else 'unavailable'
        except:
            status['components']['memory_service'] = 'unavailable'

        try:
            # Check Graph Service via REST
            response = requests.post(
                f"{self.ensemble_server_url}/graph/stats",
                timeout=2.0
            )
            if response.status_code == 200:
                graph_stats = response.json().get('stats', {})
                status['components']['graph_service'] = 'available'
                status['graph_stats'] = graph_stats
        except:
            status['components']['graph_service'] = 'unavailable'

        return status

    def query_graph(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Forward query to graph service via REST endpoint"""
        try:
            url = f"{self.ensemble_server_url}/graph/query"
            response = requests.post(url, json=query_data, timeout=5.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error querying graph: {e}")
            return {'ok': False, 'error': str(e)}

    def query_thompson(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Query Thompson model for insights (via Thompson client)"""
        if not self.thompson_client:
            if not self._ensure_bridges():
                return {'ok': False, 'error': 'Thompson client unavailable'}

        try:
            # Query examples:
            # - "Which models succeed on code reviews?"
            # - "What's the cost-quality tradeoff for large tasks?"
            # - "Recommend best model for security audit, large scope"
            query = query_data.get('query')
            if not query:
                return {'ok': False, 'error': 'Missing query'}

            # Forward to Thompson client
            # (Implementation depends on Thompson query API)
            logger.info(f"Thompson query: {query}")

            # Placeholder: Thompson would analyze graph + model priors
            return {
                'ok': True,
                'query': query,
                'status': 'queued',
                'note': 'Thompson query routing to model (implementation pending)'
            }

        except Exception as e:
            logger.error(f"Error querying Thompson: {e}")
            return {'ok': False, 'error': str(e)}

    def handle_sync_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """REST endpoint handler for POST /learning/sync-outcomes"""
        days = request_data.get('days', 7)
        return self.sync_all_outcomes(days=days)

    def handle_status_request(self) -> Dict[str, Any]:
        """REST endpoint handler for GET /learning/status"""
        return self.get_learning_status()

    def handle_graph_query(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """REST endpoint handler for GET /learning/graph/query"""
        return self.query_graph(request_data)

    def handle_thompson_query(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """REST endpoint handler for POST /learning/thompson/query"""
        return self.query_thompson(request_data)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    orchestrator = LearningOrchestrator()

    # Example: full sync
    print("=== Learning Orchestrator ===\n")

    print("1. Getting status...")
    status = orchestrator.get_learning_status()
    print(json.dumps(status, indent=2))

    print("\n2. Running full sync (read outcomes → graph → Thompson)...")
    result = orchestrator.sync_all_outcomes(days=7)
    print(json.dumps(result, indent=2))

    print("\n3. Querying graph...")
    graph_result = orchestrator.query_graph({
        'type': 'edges',
        'relationship': 'succeeded_on'
    })
    print(json.dumps(graph_result, indent=2))

    print("\n4. Querying Thompson...")
    thompson_result = orchestrator.query_thompson({
        'query': 'Which models succeed on code reviews?'
    })
    print(json.dumps(thompson_result, indent=2))
