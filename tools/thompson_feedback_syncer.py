#!/usr/bin/env python3
"""
Thompson Feedback Loop Syncer - Blocker #2 Fix

Synchronizes quality feedback from PostgreSQL back to Thompson Sampling state.

Problem: Thompson learns only from local JSON file (learning/thompson-sampling-state.json).
Production outcomes are logged to workflow.worker_results table but Thompson never sees them.

Solution: Query worker_results table → extract outcomes → update Thompson state.

Usage:
    python3 tools/thompson_feedback_syncer.py --sync-now
    python3 tools/thompson_feedback_syncer.py --diagnose

Runs as background task (cron every 5 minutes):
    */5 * * * * /usr/bin/python3 /path/to/tools/thompson_feedback_syncer.py --sync-now
"""

import psycopg2
import json
import logging
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/thompson_feedback_syncer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ThompsonFeedbackSyncer:
    """Sync quality feedback from PostgreSQL to Thompson state"""

    def __init__(self, state_file: str = None, db_host: str = "aio-01",
                 db_port: int = 5433, db_name: str = "learning", db_user: str = "claude"):
        """Initialize syncer"""
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user

        if state_file is None:
            state_file = str(
                Path(__file__).parent.parent / 'learning' / 'thompson-sampling-state.json'
            )
        self.state_file = Path(state_file)

        self.sync_log_file = Path(self.state_file).parent / 'thompson_feedback_sync.log'
        self.conn = None
        self.last_sync_time = self._load_last_sync_time()

    def _load_last_sync_time(self) -> datetime:
        """Load last sync timestamp from log file"""
        try:
            if self.sync_log_file.exists():
                with open(self.sync_log_file, 'r') as f:
                    data = json.load(f)
                    if 'last_sync_time' in data:
                        return datetime.fromisoformat(data['last_sync_time'])
        except Exception as e:
            logger.warning(f"Failed to load last sync time: {e}")
        # Default: sync last 24 hours
        return datetime.utcnow() - timedelta(hours=24)

    def _save_sync_time(self, sync_time: datetime):
        """Save sync timestamp to log file"""
        try:
            log_data = {
                'last_sync_time': sync_time.isoformat(),
                'syncs_total': 0,
                'outcomes_processed': 0
            }
            if self.sync_log_file.exists():
                with open(self.sync_log_file, 'r') as f:
                    log_data = json.load(f)
                    log_data['last_sync_time'] = sync_time.isoformat()
                    log_data['syncs_total'] = log_data.get('syncs_total', 0) + 1

            with open(self.sync_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sync time: {e}")

    def connect(self) -> bool:
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user
            )
            logger.info(f"✓ Connected to database {self.db_name}@{self.db_host}")
            return True
        except psycopg2.Error as e:
            logger.error(f"✗ Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            self.conn.close()

    def fetch_outcomes(self, since: datetime) -> List[Dict]:
        """
        Fetch worker results from database since last sync

        Returns:
            List of outcome records with: model, outcome, cost_usd, duration_ms, created_at
        """
        cursor = self.conn.cursor()
        try:
            query = """
                SELECT
                    id,
                    model,
                    outcome,
                    COALESCE(CAST(NULLIF(metadata->>'quality_score', '') AS FLOAT), 0.5) as quality_score,
                    cost_usd,
                    duration_ms,
                    created_at
                FROM workflow.worker_results
                WHERE created_at > %s
                ORDER BY created_at ASC
            """
            cursor.execute(query, (since,))
            results = cursor.fetchall()
            cursor.close()

            outcomes = []
            for row in results:
                outcomes.append({
                    'id': row[0],
                    'model': row[1],
                    'outcome': row[2],  # 'success', 'error', 'failed'
                    'quality_score': row[3],
                    'cost_usd': row[4],
                    'duration_ms': row[5],
                    'created_at': row[6]
                })

            logger.info(f"✓ Fetched {len(outcomes)} outcomes since {since.isoformat()}")
            return outcomes

        except psycopg2.Error as e:
            logger.error(f"✗ Failed to fetch outcomes: {e}")
            return []
        finally:
            cursor.close()

    def load_thompson_state(self) -> Dict:
        """Load current Thompson state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load Thompson state: {e}")
        return {'last_updated': datetime.utcnow().isoformat(), 'models': {}}

    def save_thompson_state(self, state: Dict):
        """Save updated Thompson state to file"""
        try:
            state['last_updated'] = datetime.utcnow().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info(f"✓ Saved updated Thompson state with {len(state['models'])} models")
        except Exception as e:
            logger.error(f"✗ Failed to save Thompson state: {e}")

    def process_outcomes(self, outcomes: List[Dict], quality_threshold: float = 0.7) -> Tuple[int, int]:
        """
        Process outcomes and update Thompson state

        Args:
            outcomes: List of outcome records from database
            quality_threshold: Threshold for quality_score to count as "success"

        Returns:
            (successes_processed, failures_processed)
        """
        state = self.load_thompson_state()
        successes_processed = 0
        failures_processed = 0

        for outcome in outcomes:
            model_name = outcome['model']

            # Initialize model if not present
            if model_name not in state['models']:
                state['models'][model_name] = {
                    'model_name': model_name,
                    'successes': 0,
                    'failures': 0,
                    'total_latency_ms': 0,
                    'total_cost': 0,
                    'calls': 0,
                    'last_updated': datetime.utcnow().isoformat()
                }

            model = state['models'][model_name]

            # Update counts
            model['calls'] += 1
            model['total_latency_ms'] += outcome['duration_ms']
            model['total_cost'] += outcome['cost_usd']
            model['last_updated'] = outcome['created_at'].isoformat()

            # Binary outcome: quality meets threshold
            if outcome['quality_score'] >= quality_threshold:
                model['successes'] += 1
                successes_processed += 1
                status = 'SUCCESS'
            else:
                model['failures'] += 1
                failures_processed += 1
                status = 'FAILURE'

            logger.debug(
                f"PROCESSED {outcome['id']}: {model_name} → {status} "
                f"(quality={outcome['quality_score']:.2f}, cost=${outcome['cost_usd']:.4f})"
            )

        self.save_thompson_state(state)
        return (successes_processed, failures_processed)

    def sync(self, hours: int = 1) -> Dict:
        """
        Run full sync: fetch outcomes from DB and update Thompson state

        Args:
            hours: How many hours of outcomes to process (default 1)

        Returns:
            Dict with sync statistics
        """
        logger.info("=" * 80)
        logger.info("THOMPSON FEEDBACK SYNCER - Starting sync")
        logger.info("=" * 80)

        if not self.connect():
            return {'success': False, 'error': 'Database connection failed'}

        try:
            # Fetch outcomes since last sync
            since = datetime.utcnow() - timedelta(hours=hours)
            outcomes = self.fetch_outcomes(since)

            if not outcomes:
                logger.info("No new outcomes to process")
                return {'success': True, 'outcomes_processed': 0}

            # Process outcomes and update Thompson
            successes, failures = self.process_outcomes(outcomes)

            # Save sync time
            self._save_sync_time(datetime.utcnow())

            logger.info("=" * 80)
            logger.info(f"SYNC COMPLETE: {successes} successes + {failures} failures")
            logger.info("=" * 80)

            return {
                'success': True,
                'outcomes_processed': len(outcomes),
                'successes': successes,
                'failures': failures
            }

        except Exception as e:
            logger.error(f"✗ Sync failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
        finally:
            self.disconnect()

    def diagnose(self) -> Dict:
        """
        Run diagnostic to trace feedback loop

        Checks:
        1. Database connectivity
        2. Outcome records present
        3. Thompson state consistent
        4. Quality score data quality
        """
        logger.info("=" * 80)
        logger.info("THOMPSON FEEDBACK LOOP - DIAGNOSTIC")
        logger.info("=" * 80)

        diagnostics = {
            'timestamp': datetime.utcnow().isoformat(),
            'checks': {}
        }

        # Check 1: Database connectivity
        if not self.connect():
            diagnostics['checks']['database'] = {'status': 'FAILED', 'message': 'Cannot connect'}
            return diagnostics

        try:
            cursor = self.conn.cursor()

            # Check 2: Recent outcomes in database
            cursor.execute("""
                SELECT COUNT(*), MAX(created_at)
                FROM workflow.worker_results
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            count, max_time = cursor.fetchone()
            diagnostics['checks']['database'] = {
                'status': 'OK',
                'outcomes_last_7_days': count,
                'most_recent': max_time.isoformat() if max_time else None
            }

            # Check 3: Quality score data quality
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(metadata->>'quality_score') as with_quality,
                    AVG(CAST(NULLIF(metadata->>'quality_score', '') AS FLOAT)) as avg_quality,
                    MIN(CAST(NULLIF(metadata->>'quality_score', '') AS FLOAT)) as min_quality,
                    MAX(CAST(NULLIF(metadata->>'quality_score', '') AS FLOAT)) as max_quality
                FROM workflow.worker_results
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            row = cursor.fetchone()
            diagnostics['checks']['quality_scores'] = {
                'status': 'OK',
                'total_outcomes': row[0],
                'with_quality_scores': row[1],
                'coverage_pct': (row[1] / row[0] * 100) if row[0] > 0 else 0,
                'avg_quality': float(row[2]) if row[2] else None,
                'min_quality': float(row[3]) if row[3] else None,
                'max_quality': float(row[4]) if row[4] else None
            }

            # Check 4: Thompson state consistency
            state = self.load_thompson_state()
            total_calls = sum(m['calls'] for m in state['models'].values())
            total_successes = sum(m['successes'] for m in state['models'].values())

            diagnostics['checks']['thompson_state'] = {
                'status': 'OK',
                'models_tracked': len(state['models']),
                'total_calls': total_calls,
                'total_successes': total_successes,
                'success_rate': (total_successes / total_calls * 100) if total_calls > 0 else 0,
                'models': {
                    name: {
                        'calls': perf['calls'],
                        'successes': perf['successes'],
                        'success_rate': (perf['successes'] / perf['calls'] * 100) if perf['calls'] > 0 else 0,
                        'avg_cost': perf['total_cost'] / perf['calls'] if perf['calls'] > 0 else 0
                    }
                    for name, perf in state['models'].items()
                }
            }

            # Check 5: Last sync status
            last_sync = self._load_last_sync_time()
            diagnostics['checks']['last_sync'] = {
                'status': 'OK',
                'last_sync_time': last_sync.isoformat(),
                'hours_since_sync': (datetime.utcnow() - last_sync).total_seconds() / 3600
            }

            logger.info("DIAGNOSTIC COMPLETE")
            return diagnostics

        except Exception as e:
            logger.error(f"Diagnostic failed: {e}", exc_info=True)
            diagnostics['checks']['error'] = {'status': 'FAILED', 'message': str(e)}
            return diagnostics
        finally:
            cursor.close()
            self.disconnect()


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(
        description="Thompson Feedback Loop Syncer - Sync DB outcomes to Thompson state"
    )
    parser.add_argument('--sync-now', action='store_true', help='Sync outcomes immediately')
    parser.add_argument('--diagnose', action='store_true', help='Run diagnostic')
    parser.add_argument('--hours', type=int, default=1, help='Hours of outcomes to sync (default 1)')
    parser.add_argument('--state-file', help='Thompson state file path')
    parser.add_argument('--db-host', default='aio-01', help='Database host')
    parser.add_argument('--db-port', type=int, default=5433, help='Database port')
    parser.add_argument('--db-name', default='learning', help='Database name')
    parser.add_argument('--db-user', default='claude', help='Database user')

    args = parser.parse_args()

    syncer = ThompsonFeedbackSyncer(
        state_file=args.state_file,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user
    )

    if args.sync_now:
        result = syncer.sync(hours=args.hours)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['success'] else 1)

    elif args.diagnose:
        result = syncer.diagnose()
        print(json.dumps(result, indent=2))
        sys.exit(0)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
