#!/usr/bin/env python3
"""
Arbitration Outcomes → GraphDB Bridge

Populates the simple graph database with nodes and edges from arbitration outcomes.
Enables Thompson to query relationships: which models work together? What's the
outcome chain for code reviews? etc.

Data flow:
  Memory Service (arbitration records)
    → ArbitrationOutcomesBridge (parse outcomes)
    → GraphOutcomesBridge (populate graph)
    → GraphDB (nodes + edges)
    → Thompson queries
"""

import sys
import json
import logging
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# REST endpoint for GraphDB (via ensemble_server)
ENSEMBLE_SERVER_URL = "http://127.0.0.1:8080"


class GraphOutcomesBridge:
    """Populate GraphDB from arbitration outcomes"""

    def __init__(self):
        self.ensemble_server_url = ENSEMBLE_SERVER_URL

    def populate_graph_from_outcomes(self, outcomes: List[Dict[str, Any]]) -> bool:
        """Add nodes and edges to graph based on arbitration outcomes.

        Creates:
        - Nodes: models, task types, scopes, outcomes
        - Edges: model→task, outcome→model, task→outcome relationships
        """
        if not outcomes:
            logger.info("No outcomes to process")
            return True

        try:
            # Create task type nodes
            task_types = set()
            for outcome in outcomes:
                task_type = outcome.get('task_type', 'unknown')
                if task_type and task_type not in task_types:
                    self._add_node(f'task:{task_type}', 'task_type', {'name': task_type})
                    task_types.add(task_type)

            # Process each outcome
            for outcome in outcomes:
                outcome_id = f"outcome:{outcome.get('task_name', 'unknown')}_{hash(str(outcome)) % 10000}"
                task_type = outcome.get('task_type', 'unknown')
                success = outcome.get('outcome', 'unknown') == 'success'
                confidence = outcome.get('confidence', 0.0)
                cost = outcome.get('total_cost', 0.0)

                # Create outcome node
                self._add_node(
                    outcome_id,
                    'arbitration_outcome',
                    {
                        'task': outcome.get('task_name', 'unknown'),
                        'success': success,
                        'confidence': confidence,
                        'cost': cost
                    }
                )

                # Edge: task_type → outcome
                self._add_edge(
                    f'task:{task_type}',
                    outcome_id,
                    'produced_outcome',
                    {'success': success, 'confidence': confidence, 'cost': cost}
                )

                # Edge: outcome → task (for reverse queries)
                self._add_edge(
                    outcome_id,
                    f'task:{task_type}',
                    'outcome_of_task',
                    {}
                )

            logger.info(f"Populated graph with {len(outcomes)} outcomes")
            return True

        except Exception as e:
            logger.error(f"Error populating graph: {e}")
            return False

    def add_model_success_edges(self, model_name: str, task_type: str,
                               success: bool, confidence: float) -> bool:
        """Add/update edge: model → task_type with success relationship.

        This edge aggregates success statistics for Thompson routing queries.
        """
        try:
            model_id = f'model:{model_name}'
            task_id = f'task:{task_type}'

            # Ensure nodes exist
            self._add_node(model_id, 'model', {'name': model_name})
            self._add_node(task_id, 'task_type', {'name': task_type})

            # Add edge (relationship name indicates success/failure)
            rel = 'succeeded_on' if success else 'failed_on'
            self._add_edge(
                model_id,
                task_id,
                rel,
                {'confidence': confidence}
            )

            logger.info(f"Added edge: {model_id} -{rel}-> {task_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding model success edge: {e}")
            return False

    def add_scope_edges(self, task_scope: str, task_type: str, cost: float) -> bool:
        """Add edge: scope → task_type with cost information.

        Enables queries: "Which tasks cost most for large scope?" etc.
        """
        try:
            scope_id = f'scope:{task_scope}'
            task_id = f'task:{task_type}'

            # Ensure nodes exist
            self._add_node(scope_id, 'scope', {'name': task_scope})
            self._add_node(task_id, 'task_type', {'name': task_type})

            # Add edge with cost property
            self._add_edge(
                scope_id,
                task_id,
                'tasks_in_scope',
                {'cost': cost}
            )

            return True

        except Exception as e:
            logger.error(f"Error adding scope edge: {e}")
            return False

    def _add_node(self, node_id: str, node_type: str, properties: Dict[str, Any]) -> bool:
        """Add node to graph via REST endpoint"""
        try:
            url = f"{self.ensemble_server_url}/graph/add-node"
            response = requests.post(
                url,
                json={'id': node_id, 'type': node_type, 'properties': properties},
                timeout=5.0
            )
            response.raise_for_status()
            return response.json().get('ok', False)

        except requests.exceptions.RequestException as e:
            logger.debug(f"Error adding node {node_id}: {e}")
            return False

    def _add_edge(self, from_id: str, to_id: str, relationship: str,
                 properties: Dict[str, Any]) -> bool:
        """Add edge to graph via REST endpoint"""
        try:
            url = f"{self.ensemble_server_url}/graph/add-edge"
            response = requests.post(
                url,
                json={
                    'from': from_id,
                    'to': to_id,
                    'relationship': relationship,
                    'properties': properties
                },
                timeout=5.0
            )
            response.raise_for_status()
            return response.json().get('ok', False)

        except requests.exceptions.RequestException as e:
            logger.debug(f"Error adding edge {from_id}->{to_id}: {e}")
            return False

    def query_model_success(self, model_name: str, task_type: str) -> Optional[Dict[str, Any]]:
        """Query: did this model succeed on this task type?"""
        try:
            url = f"{self.ensemble_server_url}/graph/query"
            response = requests.post(
                url,
                json={
                    'type': 'edges',
                    'from_type': 'model',
                    'to_type': 'task_type',
                    'relationship': 'succeeded_on'  # Could also query 'failed_on'
                },
                timeout=5.0
            )
            response.raise_for_status()

            edges = response.json().get('edges', [])
            for edge in edges:
                if edge.get('from_id') == f'model:{model_name}' and \
                   edge.get('to_id') == f'task:{task_type}':
                    return edge

            return None

        except Exception as e:
            logger.error(f"Error querying model success: {e}")
            return None

    def find_related_models(self, task_type: str) -> List[str]:
        """Query: which models have worked on this task type?"""
        try:
            url = f"{self.ensemble_server_url}/graph/traverse"
            response = requests.post(
                url,
                json={'start': f'task:{task_type}', 'max_depth': 2},
                timeout=5.0
            )
            response.raise_for_status()

            data = response.json().get('data', {})
            nodes = data.get('nodes', {})

            # Filter for model nodes
            models = [nid.replace('model:', '') for nid in nodes.keys() if nid.startswith('model:')]
            return models

        except Exception as e:
            logger.error(f"Error finding related models: {e}")
            return []


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    bridge = GraphOutcomesBridge()

    # Example: populate graph from sample outcomes
    sample_outcomes = [
        {
            'task_name': 'code_review_1',
            'task_type': 'code_review',
            'outcome': 'success',
            'confidence': 0.92,
            'total_cost': 0.15,
        },
        {
            'task_name': 'security_audit_1',
            'task_type': 'security_audit',
            'outcome': 'success',
            'confidence': 0.88,
            'total_cost': 0.42,
        },
    ]

    bridge.populate_graph_from_outcomes(sample_outcomes)
    bridge.add_model_success_edges('claude-sonnet-5', 'code_review', True, 0.92)
    bridge.add_scope_edges('small', 'code_review', 0.15)

    print("Graph populated with sample data")
