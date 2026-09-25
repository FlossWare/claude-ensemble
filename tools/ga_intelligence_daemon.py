#!/usr/bin/env python3
"""Intelligence Evolution Daemon

Runs ga_continuous_intelligence.py indefinitely with:
- Meta-GA evolved hyperparameters (from best_ga_hyperparams.json)
- PostgreSQL milestone storage via SSH tunnel to aio-01
- Periodic reporting
- Graceful shutdown with final checkpoint

Run directly:
    python3 ga_intelligence_daemon.py

Run with meta-GA evolved params:
    python3 ga_intelligence_daemon.py --use-evolved-params

Run as background daemon:
    nohup python3 ga_intelligence_daemon.py --use-evolved-params > intelligence.log 2>&1 &

Resume from checkpoint:
    python3 ga_intelligence_daemon.py --resume
"""

import argparse
import json
import os
import subprocess
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
EVOLVED_PARAMS_PATH = os.path.join(TOOLS_DIR, 'best_ga_hyperparams.json')
CHECKPOINT_DIR = os.path.join(TOOLS_DIR, 'intelligence_checkpoints')

sys.path.insert(0, TOOLS_DIR)
from ga_continuous_intelligence import ContinuousIntelligenceEngine, show_report


def load_evolved_hyperparams() -> dict:
    if not os.path.exists(EVOLVED_PARAMS_PATH):
        print(f"No evolved params at {EVOLVED_PARAMS_PATH}, using defaults")
        return {}

    with open(EVOLVED_PARAMS_PATH) as f:
        data = json.load(f)

    hp = data.get('hyperparams', {})
    print(f"Loaded meta-GA evolved hyperparams (fitness={data.get('fitness', 0):.4f}):")
    for k, v in hp.items():
        print(f"  {k}: {v}")
    return hp


def store_milestone_sql(level: str, epoch: int, metrics: dict):
    """Store intelligence milestone to PostgreSQL via SSH tunnel."""
    sql = f"""
INSERT INTO ga.best_solutions (use_case, chromosome, fitness, fitness_details)
VALUES (
    'intelligence-{level}',
    '{json.dumps(metrics)}',
    {metrics.get('intelligence_score', 0)},
    '{json.dumps({"level": level, "epoch": epoch, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")})}'
)
ON CONFLICT (use_case) DO UPDATE SET
    chromosome = EXCLUDED.chromosome,
    fitness = EXCLUDED.fitness,
    fitness_details = EXCLUDED.fitness_details,
    evolved_at = NOW();
"""
    sql_file = os.path.join(TOOLS_DIR, f'_milestone_{level}.sql')
    with open(sql_file, 'w') as f:
        f.write(sql)

    try:
        result = subprocess.run(
            ['ssh', '-o', 'ConnectTimeout=5', 'pi-01',
             f'scp -o ConnectTimeout=5 /dev/stdin aio-01:/tmp/_milestone.sql && '
             f'ssh -o ConnectTimeout=5 aio-01 "psql -U sfloess -d learning -f /tmp/_milestone.sql"'],
            input=sql.encode(), capture_output=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  [Milestone '{level}' stored in PostgreSQL]")
        else:
            print(f"  [PostgreSQL store failed: {result.stderr.decode()[:200]}]")
    except Exception as e:
        print(f"  [PostgreSQL store failed: {e}]")
    finally:
        if os.path.exists(sql_file):
            os.unlink(sql_file)


def main():
    parser = argparse.ArgumentParser(description='Intelligence Evolution Daemon')
    parser.add_argument('--use-evolved-params', action='store_true',
                        help='Use meta-GA evolved hyperparameters')
    parser.add_argument('--max-epochs', type=int, default=None,
                        help='Max epochs (default: infinite)')
    parser.add_argument('--population', type=int, default=40)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--resume', action='store_true',
                        help='Resume from latest checkpoint')
    parser.add_argument('--report', action='store_true',
                        help='Show latest report and exit')
    parser.add_argument('--store-milestones', action='store_true',
                        help='Store milestones to PostgreSQL via SSH')
    args = parser.parse_args()

    if args.report:
        show_report(CHECKPOINT_DIR)
        return

    if args.resume:
        latest = os.path.join(CHECKPOINT_DIR, 'latest.json')
        if os.path.exists(latest):
            engine = ContinuousIntelligenceEngine.from_checkpoint(latest)
            print(f"Resuming from epoch {engine.epoch}")
        else:
            print("No checkpoint found, starting fresh")
            engine = ContinuousIntelligenceEngine(
                population_size=args.population, seed=args.seed
            )
    else:
        engine = ContinuousIntelligenceEngine(
            population_size=args.population, seed=args.seed
        )

    if args.use_evolved_params:
        hp = load_evolved_hyperparams()
        if hp:
            engine.mutation_rate = hp.get('mutation_rate', engine.mutation_rate)
            engine.crossover_rate = hp.get('crossover_rate', engine.crossover_rate)
            engine.tournament_size = hp.get('tournament_size', engine.tournament_size)
            engine.elitism_ratio = hp.get('elitism_ratio', engine.elitism_ratio)
            engine.mutation_scale = hp.get('mutation_step_scale', engine.mutation_scale)

    # Monkey-patch checkpoint to also store milestones
    if args.store_milestones:
        original_check = engine._check_intelligence_thresholds
        def patched_check(metrics):
            original_check(metrics)
            for level, epoch in engine.intelligence_detected.items():
                if epoch == engine.epoch:
                    store_milestone_sql(level, epoch, metrics.to_dict())
        engine._check_intelligence_thresholds = patched_check

    engine.run(max_epochs=args.max_epochs)


if __name__ == '__main__':
    main()
