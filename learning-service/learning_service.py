#!/usr/bin/env python3
"""
RH Learning Service Daemon

Central learning authority for autonomous task outcome recording and analysis.
Runs as systemd user service, listens on Unix socket.
Single-threaded (daemon owns all state, no race conditions).
Integrates with Thompson router for model performance tracking.
"""

import json
import logging
import socket
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import threading
import traceback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / '.claude' / 'rh-learning-service.log')
    ]
)
logger = logging.getLogger(__name__)

LEARNING_DIR = Path.home() / '.claude' / 'projects' / '-home-sfloess' / 'learning'
SOCKET_PATH = Path('/tmp/rh-learning.sock')

# Add shared module to path for thompson_client import
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


class AutonomousLearningSystem:
    """Load and manage the autonomous learning state"""

    def __init__(self, learning_dir: Path):
        self.learning_dir = Path(learning_dir)
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        self.outcomes_dir = self.learning_dir / 'autonomous_outcomes'
        self.priors_dir = self.learning_dir / 'autonomous_priors'
        self.outcomes_dir.mkdir(parents=True, exist_ok=True)
        self.priors_dir.mkdir(parents=True, exist_ok=True)

    def record_outcome(self, task_id: str, task_type: str, model: str,
                      rating: int, tokens: int, cost: float) -> bool:
        """Record a task outcome to disk"""
        try:
            outcome = {
                'task_id': task_id,
                'task_type': task_type,
                'model': model,
                'rating': rating,
                'tokens': tokens,
                'cost': cost,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Write to outcomes directory (one file per outcome)
            outcome_file = self.outcomes_dir / f"{task_id}_{datetime.utcnow().timestamp()}.json"
            with open(outcome_file, 'w') as f:
                json.dump(outcome, f, indent=2)

            logger.info(f"Recorded outcome: {task_id} ({model}, rating={rating})")
            return True
        except Exception as e:
            logger.error(f"Error recording outcome: {e}")
            return False

    def get_recent_outcomes(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get outcomes from the last N days"""
        try:
            outcomes = []
            cutoff_time = datetime.utcnow() - timedelta(days=days)

            for outcome_file in self.outcomes_dir.glob('*.json'):
                try:
                    with open(outcome_file, 'r') as f:
                        outcome = json.load(f)

                    outcome_time = datetime.fromisoformat(outcome.get('timestamp', ''))
                    if outcome_time >= cutoff_time:
                        outcomes.append(outcome)
                except Exception as e:
                    logger.debug(f"Error reading {outcome_file}: {e}")

            # Sort by timestamp, most recent first
            outcomes.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return outcomes
        except Exception as e:
            logger.error(f"Error getting recent outcomes: {e}")
            return []

    def generate_report(self) -> Dict[str, Any]:
        """Generate a learning summary report"""
        try:
            recent = self.get_recent_outcomes(days=30)

            if not recent:
                return {
                    'ok': True,
                    'total_outcomes': 0,
                    'report': 'No outcomes recorded yet'
                }

            # Aggregate by model and task type
            by_model = {}
            by_task_type = {}

            for outcome in recent:
                model = outcome.get('model', 'unknown')
                task_type = outcome.get('task_type', 'unknown')
                rating = outcome.get('rating', 0)
                cost = outcome.get('cost', 0.0)

                if model not in by_model:
                    by_model[model] = {'count': 0, 'total_rating': 0, 'total_cost': 0.0}
                by_model[model]['count'] += 1
                by_model[model]['total_rating'] += rating
                by_model[model]['total_cost'] += cost

                if task_type not in by_task_type:
                    by_task_type[task_type] = {'count': 0, 'total_rating': 0}
                by_task_type[task_type]['count'] += 1
                by_task_type[task_type]['total_rating'] += rating

            # Calculate averages
            model_summary = {}
            for model, stats in by_model.items():
                model_summary[model] = {
                    'count': stats['count'],
                    'avg_rating': round(stats['total_rating'] / stats['count'], 2),
                    'total_cost': round(stats['total_cost'], 4)
                }

            task_summary = {}
            for task_type, stats in by_task_type.items():
                task_summary[task_type] = {
                    'count': stats['count'],
                    'avg_rating': round(stats['total_rating'] / stats['count'], 2)
                }

            return {
                'ok': True,
                'total_outcomes': len(recent),
                'date_range': '30 days',
                'by_model': model_summary,
                'by_task_type': task_summary
            }
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return {'ok': False, 'error': str(e)}

    def reset_learning(self) -> bool:
        """Clear all outcomes and priors"""
        try:
            # Remove all files in outcomes and priors directories
            for f in self.outcomes_dir.glob('*.json'):
                f.unlink()
            for f in self.priors_dir.glob('*.json'):
                f.unlink()
            logger.info("Reset learning system (cleared all outcomes and priors)")
            return True
        except Exception as e:
            logger.error(f"Error resetting learning: {e}")
            return False


class LearningService:
    """Learning service daemon - single-threaded, listens on Unix socket"""

    def __init__(self, socket_path: Path, learning_dir: Path):
        self.socket_path = Path(socket_path)
        self.system = AutonomousLearningSystem(learning_dir)
        self.socket = None
        self.thompson_client = None

        # Try to import Thompson client for integration
        try:
            from shared.thompson_client import ThompsonClient
            self.thompson_client = ThompsonClient()
            logger.info("Initialized Thompson client for learning integration")
        except Exception as e:
            logger.warning(f"Thompson client not available (optional): {e}")

    def start(self):
        """Start the service - single-threaded event loop"""
        logger.info("Starting RH Learning Service")

        # Clean up old socket if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Create Unix domain socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.socket_path))
        self.socket.listen(5)
        self.socket.settimeout(None)

        logger.info(f"Listening on {self.socket_path}")

        try:
            # Single-threaded: handle requests one at a time
            while True:
                try:
                    conn, _ = self.socket.accept()
                    self._handle_client(conn)
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Connection error: {e}")
                    continue
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            self.stop()

    def stop(self):
        """Stop the service"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        if self.socket_path.exists():
            self.socket_path.unlink()
        logger.info("Learning service stopped")

    def _handle_client(self, conn: socket.socket):
        """Handle single client request (synchronous, single-threaded)"""
        try:
            conn.settimeout(5.0)

            # Read request (ends with newline)
            data = b''
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:
                    break

            request_str = data.decode('utf-8').strip()
            if not request_str:
                return

            response = self._process_request(request_str)

            # Send response
            conn.sendall((response + '\n').encode('utf-8'))
        except socket.timeout:
            logger.debug("Client timeout")
            try:
                conn.sendall(b'{"ok": false, "error": "timeout"}\n')
            except:
                pass
        except Exception as e:
            logger.error(f"Client error: {e}\n{traceback.format_exc()}")
            try:
                conn.sendall(b'{"ok": false, "error": "server error"}\n')
            except:
                pass
        finally:
            try:
                conn.close()
            except:
                pass

    def _process_request(self, request: str) -> str:
        """Process a request, return JSON response"""
        try:
            req_data = json.loads(request)
            operation = req_data.get('op')

            if operation == 'process_outcome':
                task_id = req_data.get('task_id')
                task_type = req_data.get('task_type')
                model = req_data.get('model')
                rating = req_data.get('rating')
                tokens = req_data.get('tokens')
                cost = req_data.get('cost')

                # Record outcome to disk
                success = self.system.record_outcome(
                    task_id, task_type, model, rating, tokens, cost
                )

                if success and self.thompson_client:
                    # Also update Thompson router with outcome
                    try:
                        self.thompson_client.record_outcome(
                            model=model,
                            task_type=task_type,
                            success=(rating >= 3),  # 3+ is success
                            cost=cost,
                            tokens=tokens
                        )
                    except Exception as e:
                        logger.warning(f"Failed to update Thompson: {e}")

                return json.dumps({'ok': success})

            elif operation == 'get_report':
                report = self.system.generate_report()
                return json.dumps(report)

            elif operation == 'get_recent_outcomes':
                days = req_data.get('days', 7)
                outcomes = self.system.get_recent_outcomes(days)
                return json.dumps({'ok': True, 'outcomes': outcomes})

            elif operation == 'reset_learning':
                success = self.system.reset_learning()
                return json.dumps({'ok': success})

            elif operation == 'ping':
                return json.dumps({'ok': True, 'message': 'pong'})

            else:
                return json.dumps({'ok': False, 'error': f'Unknown operation: {operation}'})

        except json.JSONDecodeError:
            return json.dumps({'ok': False, 'error': 'Invalid JSON'})
        except Exception as e:
            logger.error(f"Request error: {e}\n{traceback.format_exc()}")
            return json.dumps({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    service = LearningService(SOCKET_PATH, LEARNING_DIR)
    service.start()
