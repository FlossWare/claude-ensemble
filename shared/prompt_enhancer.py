#!/usr/bin/env python3
"""
Prompt Pattern Learning Integration
Enhances prompts based on learned patterns from 692 task examples across 11 task types
"""
import pickle
import re
from pathlib import Path
from typing import Dict, List, Optional


class PromptEnhancer:
    """Enhance prompts based on learned patterns from task execution history"""

    def __init__(self, patterns_path: Optional[str] = None):
        """
        Load prompt patterns from pickle file

        Args:
            patterns_path: Path to prompt_patterns.pkl (default: ~/.claude/learning/prompt_patterns.pkl)
        """
        if patterns_path is None:
            patterns_path = str(Path.home() / ".claude" / "learning" / "prompt_patterns.pkl")
            # Fallback to project directory if not in ~/.claude
            if not Path(patterns_path).exists():
                patterns_path = str(Path(__file__).parent.parent / "learning" / "prompt_patterns.pkl")

        self.patterns_path = patterns_path
        self.patterns = None
        self.stats_by_type = {}

        try:
            with open(patterns_path, 'rb') as f:
                data = pickle.load(f)
                self.stats_by_type = data.get('stats_by_type', {})
                self.patterns_by_type = data.get('patterns_by_type', {})
                print(f"✅ Loaded prompt patterns from {patterns_path}")
                print(f"   Task types: {len(self.stats_by_type)}")
                print(f"   Total examples: {sum(v.get('count', 0) for v in self.stats_by_type.values())}")
        except FileNotFoundError:
            print(f"⚠️  Prompt patterns not found at {patterns_path}")
            print("   Run tools/prompt_optimizer.py to generate patterns")
        except Exception as e:
            print(f"⚠️  Error loading prompt patterns: {e}")

    def classify_task_type(self, task: str, workflow_name: str = '') -> str:
        """
        Classify task type from task description and workflow name

        Returns: One of the 11 task types or 'general'
        """
        task_lower = task.lower()
        workflow_lower = workflow_name.lower()

        # Priority 1: Exact workflow name matches
        if 'orchestrat' in workflow_lower or 'fleet' in workflow_lower:
            return 'orchestration'
        if 'research' in workflow_lower or 'deep-research' in workflow_lower:
            return 'research'

        # Priority 2: Strong keyword matches
        if re.search(r'\b(train|learning|ml|bandit|ga|optimizer)\b', task_lower):
            return 'ml_training'
        if re.search(r'\b(review|audit|check|verify|validate)\b', task_lower):
            return 'code_review'
        if re.search(r'\b(implement|generate|create|build|write code)\b', task_lower):
            return 'code_generation'
        if re.search(r'\b(debug|fix|error|bug|issue)\b', task_lower):
            return 'debugging'
        if re.search(r'\b(test|unit test|integration|spec)\b', task_lower):
            return 'testing'
        if re.search(r'\b(document|readme|guide|explain)\b', task_lower):
            return 'documentation'
        if re.search(r'\b(database|sql|postgres|query)\b', task_lower):
            return 'database'
        if re.search(r'\b(config|setup|install|configure)\b', task_lower):
            return 'system_config'

        # Default
        return 'general'

    def get_pattern_stats(self, task_type: str) -> Dict:
        """Get learned pattern statistics for a task type"""
        return self.stats_by_type.get(task_type, {})

    def enhance_prompt(self, task: str, task_type: Optional[str] = None,
                      workflow_name: str = '') -> str:
        """
        Enhance prompt based on learned patterns

        Args:
            task: Original task description
            task_type: Task type (auto-classified if None)
            workflow_name: Workflow context

        Returns:
            Enhanced prompt with proven patterns
        """
        if not self.stats_by_type:
            # No patterns loaded, return original
            return task

        # Auto-classify if not provided
        if task_type is None:
            task_type = self.classify_task_type(task, workflow_name)

        stats = self.get_pattern_stats(task_type)
        if not stats or stats.get('count', 0) == 0:
            # No patterns for this task type
            return task

        # Apply learned patterns
        enhanced = task
        enhancements = []

        # Pattern 1: Add task label (if high percentage in examples)
        if stats.get('task_label_pct', 0) > 0.3:
            if not re.match(r'^\*\*TASK', task):
                enhanced = f"**TASK:** {enhanced}"
                enhancements.append("task_label")

        # Pattern 2: Add constraints (if common in this task type)
        if stats.get('constraints_pct', 0) > 0.3 and task_type in ['code_generation', 'ml_training']:
            if 'constraint' not in task.lower():
                constraints = self._get_default_constraints(task_type)
                if constraints:
                    enhanced = f"{enhanced}\n\n**CONSTRAINTS:**\n{constraints}"
                    enhancements.append("constraints")

        # Pattern 3: Add examples (if common pattern)
        if stats.get('examples_pct', 0) > 0.3 and task_type in ['code_generation', 'debugging']:
            if 'example' not in task.lower():
                enhanced = f"{enhanced}\n\nProvide a concrete example."
                enhancements.append("examples")

        # Pattern 4: Add context (if common pattern)
        if stats.get('context_pct', 0) > 0.3:
            if 'context' not in task.lower() and workflow_name:
                enhanced = f"**CONTEXT:** {workflow_name}\n\n{enhanced}"
                enhancements.append("context")

        # Pattern 5: Convert to imperative form (if high percentage)
        if stats.get('imperative_pct', 0) > 0.5 and not re.match(r'^(Implement|Generate|Create|Build|Review|Debug|Test|Document)', task):
            # Convert "I want to..." or "Can you..." to imperative
            if task.lower().startswith(('i want', 'can you', 'could you', 'please')):
                enhanced = re.sub(r'^(I want to |Can you |Could you |Please )', '', enhanced, flags=re.IGNORECASE)
                # Capitalize first word
                if enhanced:
                    enhanced = enhanced[0].upper() + enhanced[1:]
                enhancements.append("imperative")

        # Pattern 6: Add structure (bullets/numbered lists) if common
        if stats.get('bullet_points_pct', 0) > 0.3 or stats.get('numbered_list_pct', 0) > 0.3:
            # Add structure hint if multi-step task
            if '\n' not in enhanced and len(enhanced.split()) > 15:
                enhanced = f"{enhanced}\n\nBreak down into steps."
                enhancements.append("structure")

        if enhancements:
            print(f"🎨 Enhanced prompt for {task_type} (applied: {', '.join(enhancements)})")

        return enhanced

    def _get_default_constraints(self, task_type: str) -> str:
        """Get default constraints for a task type"""
        constraints = {
            'code_generation': '- Use Python 3.10+\n- Follow PEP 8 style\n- Include error handling',
            'ml_training': '- Use existing fleet infrastructure\n- Log metrics to PostgreSQL\n- Report results in JSON',
            'database': '- Use prepared statements\n- Include error handling\n- Test on PostgreSQL',
            'testing': '- Write unit tests\n- Cover edge cases\n- Use pytest',
        }
        return constraints.get(task_type, '')

    def get_learned_patterns_summary(self, task_type: str) -> Dict:
        """
        Get summary of learned patterns for a task type

        Returns:
            Dict with pattern statistics and example prompts
        """
        stats = self.get_pattern_stats(task_type)
        if not stats:
            return {}

        return {
            'task_type': task_type,
            'sample_count': stats.get('count', 0),
            'avg_length': stats.get('avg_length', 0),
            'common_patterns': {
                'code_blocks': f"{stats.get('code_block_pct', 0)*100:.0f}%",
                'bullet_points': f"{stats.get('bullet_points_pct', 0)*100:.0f}%",
                'numbered_lists': f"{stats.get('numbered_list_pct', 0)*100:.0f}%",
                'questions': f"{stats.get('question_pct', 0)*100:.0f}%",
                'imperative': f"{stats.get('imperative_pct', 0)*100:.0f}%",
                'constraints': f"{stats.get('constraints_pct', 0)*100:.0f}%",
                'examples': f"{stats.get('examples_pct', 0)*100:.0f}%",
            },
            'example_prompts': stats.get('examples', [])[:3]
        }


# Convenience function for quick use
def enhance_prompt(task: str, task_type: Optional[str] = None,
                   workflow_name: str = '') -> str:
    """
    Quick enhancement function (creates new enhancer each time)

    For repeated use, create PromptEnhancer instance and call enhance_prompt() directly
    """
    enhancer = PromptEnhancer()
    return enhancer.enhance_prompt(task, task_type, workflow_name)


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 prompt_enhancer.py '<task>' [task_type] [workflow_name]")
        print()
        print("Examples:")
        print("  prompt_enhancer.py 'fix the bug in parser.py'")
        print("  prompt_enhancer.py 'implement Java parser' code_generation")
        print("  prompt_enhancer.py 'research firmware methods' research deep-research")
        print()
        print("Options:")
        print("  --stats <task_type> : Show learned patterns for task type")
        sys.exit(1)

    enhancer = PromptEnhancer()

    if sys.argv[1] == '--stats':
        task_type = sys.argv[2] if len(sys.argv) > 2 else 'general'
        summary = enhancer.get_learned_patterns_summary(task_type)

        if not summary:
            print(f"❌ No patterns found for task type: {task_type}")
            print(f"Available types: {list(enhancer.stats_by_type.keys())}")
            return

        print(f"\n{'='*60}")
        print(f"LEARNED PATTERNS: {task_type.upper()}")
        print(f"{'='*60}")
        print(f"Sample count: {summary['sample_count']}")
        print(f"Avg length: {summary['avg_length']:.0f} chars")
        print()
        print("Common patterns:")
        for pattern, pct in summary['common_patterns'].items():
            print(f"  {pattern:20s}: {pct:>6s}")
        print()
        print("Example prompts:")
        for i, example in enumerate(summary['example_prompts'], 1):
            print(f"  {i}. {example[:100]}...")
        print()
        return

    task = sys.argv[1]
    task_type = sys.argv[2] if len(sys.argv) > 2 else None
    workflow_name = sys.argv[3] if len(sys.argv) > 3 else ''

    print(f"\n{'='*60}")
    print(f"ORIGINAL PROMPT:")
    print(f"{'='*60}")
    print(task)
    print()

    enhanced = enhancer.enhance_prompt(task, task_type, workflow_name)

    print(f"{'='*60}")
    print(f"ENHANCED PROMPT:")
    print(f"{'='*60}")
    print(enhanced)
    print()

    if task_type is None:
        detected_type = enhancer.classify_task_type(task, workflow_name)
        print(f"Auto-detected task type: {detected_type}")
        print()


if __name__ == "__main__":
    main()
