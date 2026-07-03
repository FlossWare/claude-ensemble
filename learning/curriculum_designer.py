#!/usr/bin/env python3
"""
Curriculum Learning System
Optimizes task ordering, difficulty progression, and sample efficiency
"""

import numpy as np
import pickle
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

@dataclass
class Task:
    """Represents a learning task with difficulty and dependencies"""
    task_id: str
    difficulty: float  # 0.0 (easy) to 1.0 (hard)
    prerequisites: List[str] = field(default_factory=list)
    competency_threshold: float = 0.75
    samples_seen: int = 0
    success_rate: float = 0.0
    estimated_time_ms: int = 0

    def update_performance(self, success: bool):
        """Update task performance metrics"""
        self.samples_seen += 1
        alpha = 0.1  # Exponential moving average
        self.success_rate = (1 - alpha) * self.success_rate + alpha * (1.0 if success else 0.0)

    def is_mastered(self) -> bool:
        """Check if task has been mastered"""
        return self.success_rate >= self.competency_threshold and self.samples_seen >= 5


@dataclass
class CurriculumState:
    """Tracks curriculum learning state"""
    tasks: Dict[str, Task] = field(default_factory=dict)
    current_phase: int = 0
    total_samples: int = 0
    phases_completed: int = 0
    difficulty_curve: List[float] = field(default_factory=list)
    sample_efficiency: float = 0.0

    def add_task(self, task: Task):
        """Add task to curriculum"""
        self.tasks[task.task_id] = task

    def get_next_task(self) -> Optional[Task]:
        """Get next task using curriculum ordering"""
        # Filter tasks that are ready (prerequisites met)
        ready_tasks = [
            task for task in self.tasks.values()
            if not task.is_mastered() and self._prerequisites_met(task)
        ]

        if not ready_tasks:
            return None

        # Sort by difficulty and select appropriate task
        ready_tasks.sort(key=lambda t: t.difficulty)

        # Adaptive difficulty selection based on recent performance
        avg_success = np.mean([t.success_rate for t in ready_tasks if t.samples_seen > 0] or [0.5])

        # Zone of Proximal Development (ZPD)
        if avg_success > 0.85:
            # Doing well, increase difficulty
            target_difficulty = min(1.0, self._current_difficulty() + 0.1)
        elif avg_success < 0.60:
            # Struggling, decrease difficulty
            target_difficulty = max(0.0, self._current_difficulty() - 0.1)
        else:
            # In sweet spot, maintain difficulty
            target_difficulty = self._current_difficulty()

        # Select task closest to target difficulty
        selected_task = min(ready_tasks, key=lambda t: abs(t.difficulty - target_difficulty))

        return selected_task

    def _prerequisites_met(self, task: Task) -> bool:
        """Check if task prerequisites are mastered"""
        for prereq_id in task.prerequisites:
            if prereq_id not in self.tasks:
                return False
            if not self.tasks[prereq_id].is_mastered():
                return False
        return True

    def _current_difficulty(self) -> float:
        """Calculate current average difficulty"""
        if not self.difficulty_curve:
            return 0.1  # Start easy
        return np.mean(self.difficulty_curve[-10:])  # Last 10 tasks

    def record_sample(self, task_id: str, success: bool, duration_ms: int):
        """Record training sample"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        task.update_performance(success)
        task.estimated_time_ms = int(0.9 * task.estimated_time_ms + 0.1 * duration_ms)

        self.total_samples += 1
        self.difficulty_curve.append(task.difficulty)

        # Calculate sample efficiency (mastery per sample)
        mastered_count = sum(1 for t in self.tasks.values() if t.is_mastered())
        self.sample_efficiency = mastered_count / max(1, self.total_samples)

    def get_curriculum_plan(self, max_tasks: int = 20) -> List[str]:
        """Generate optimal task ordering for curriculum"""
        plan = []
        visited = set()

        def _add_with_deps(task_id: str):
            if task_id in visited or task_id not in self.tasks:
                return

            task = self.tasks[task_id]

            # Add prerequisites first
            for prereq_id in task.prerequisites:
                _add_with_deps(prereq_id)

            if task_id not in visited:
                plan.append(task_id)
                visited.add(task_id)

        # Sort tasks by difficulty
        sorted_tasks = sorted(self.tasks.values(), key=lambda t: t.difficulty)

        for task in sorted_tasks:
            if len(plan) >= max_tasks:
                break
            _add_with_deps(task.task_id)

        return plan


class CurriculumDesigner:
    """Main curriculum learning designer"""

    def __init__(self):
        self.state = CurriculumState()
        self.learning_rate_schedule = self._create_lr_schedule()

    def _create_lr_schedule(self) -> List[Tuple[int, float]]:
        """Create learning rate schedule based on curriculum phases"""
        return [
            (0, 0.01),      # Phase 1: Easy tasks, higher LR
            (100, 0.005),   # Phase 2: Medium tasks, moderate LR
            (300, 0.002),   # Phase 3: Hard tasks, lower LR
            (500, 0.001),   # Phase 4: Expert tasks, minimal LR
        ]

    def get_learning_rate(self) -> float:
        """Get current learning rate based on curriculum progress"""
        for phase_samples, lr in reversed(self.learning_rate_schedule):
            if self.state.total_samples >= phase_samples:
                return lr
        return 0.01

    def create_default_curriculum(self) -> CurriculumState:
        """Create default curriculum for distributed LLM orchestration"""

        # Phase 1: Basic routing (difficulty 0.1-0.3)
        self.state.add_task(Task(
            task_id="simple_routing",
            difficulty=0.1,
            competency_threshold=0.80,
            prerequisites=[]
        ))

        self.state.add_task(Task(
            task_id="model_selection",
            difficulty=0.2,
            competency_threshold=0.75,
            prerequisites=["simple_routing"]
        ))

        self.state.add_task(Task(
            task_id="cost_optimization",
            difficulty=0.3,
            competency_threshold=0.75,
            prerequisites=["model_selection"]
        ))

        # Phase 2: Task decomposition (difficulty 0.4-0.5)
        self.state.add_task(Task(
            task_id="parallel_decomposition",
            difficulty=0.4,
            competency_threshold=0.75,
            prerequisites=["simple_routing"]
        ))

        self.state.add_task(Task(
            task_id="dependency_detection",
            difficulty=0.5,
            competency_threshold=0.70,
            prerequisites=["parallel_decomposition"]
        ))

        # Phase 3: Advanced strategies (difficulty 0.6-0.7)
        self.state.add_task(Task(
            task_id="consensus_voting",
            difficulty=0.6,
            competency_threshold=0.70,
            prerequisites=["model_selection", "parallel_decomposition"]
        ))

        self.state.add_task(Task(
            task_id="retry_logic",
            difficulty=0.65,
            competency_threshold=0.70,
            prerequisites=["consensus_voting"]
        ))

        self.state.add_task(Task(
            task_id="adaptive_routing",
            difficulty=0.7,
            competency_threshold=0.65,
            prerequisites=["cost_optimization", "retry_logic"]
        ))

        # Phase 4: Expert optimization (difficulty 0.8-0.9)
        self.state.add_task(Task(
            task_id="load_balancing",
            difficulty=0.8,
            competency_threshold=0.65,
            prerequisites=["adaptive_routing", "dependency_detection"]
        ))

        self.state.add_task(Task(
            task_id="feedback_integration",
            difficulty=0.85,
            competency_threshold=0.60,
            prerequisites=["consensus_voting", "adaptive_routing"]
        ))

        self.state.add_task(Task(
            task_id="meta_learning",
            difficulty=0.9,
            competency_threshold=0.60,
            prerequisites=["feedback_integration", "load_balancing"]
        ))

        return self.state

    def get_curriculum_summary(self) -> Dict:
        """Get curriculum summary for reporting"""
        plan = self.state.get_curriculum_plan()

        mastered = [t for t in self.state.tasks.values() if t.is_mastered()]
        in_progress = [t for t in self.state.tasks.values() if t.samples_seen > 0 and not t.is_mastered()]
        not_started = [t for t in self.state.tasks.values() if t.samples_seen == 0]

        return {
            "total_tasks": len(self.state.tasks),
            "mastered": len(mastered),
            "in_progress": len(in_progress),
            "not_started": len(not_started),
            "total_samples": self.state.total_samples,
            "sample_efficiency": round(self.state.sample_efficiency, 4),
            "current_difficulty": round(self.state._current_difficulty(), 3),
            "current_learning_rate": self.get_learning_rate(),
            "recommended_plan": plan[:10],
            "phases_completed": self.state.phases_completed,
            "tasks": {
                task_id: {
                    "difficulty": task.difficulty,
                    "success_rate": round(task.success_rate, 3),
                    "samples_seen": task.samples_seen,
                    "mastered": task.is_mastered(),
                    "prerequisites": task.prerequisites
                }
                for task_id, task in self.state.tasks.items()
            }
        }

    def save(self, filepath: str):
        """Save curriculum designer to pickle file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
        print(f"Saved curriculum designer to {filepath}")

    @staticmethod
    def load(filepath: str) -> 'CurriculumDesigner':
        """Load curriculum designer from pickle file"""
        with open(filepath, 'rb') as f:
            return pickle.load(f)


def main():
    """Create and save default curriculum"""
    designer = CurriculumDesigner()
    designer.create_default_curriculum()

    # Save to specified location
    save_path = str(Path.home() / '.claude' / 'learning' / 'curriculum_designer.pkl')
    designer.save(save_path)

    # Also save summary as JSON
    summary = designer.get_curriculum_summary()
    json_path = str(Path.home() / '.claude' / 'learning' / 'curriculum_designer_summary.json')
    with open(json_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nCurriculum Summary:")
    print(f"  Total tasks: {summary['total_tasks']}")
    print(f"  Current difficulty: {summary['current_difficulty']}")
    print(f"  Sample efficiency: {summary['sample_efficiency']}")
    print(f"  Recommended plan: {', '.join(summary['recommended_plan'][:5])}")

    return summary


if __name__ == '__main__':
    main()
