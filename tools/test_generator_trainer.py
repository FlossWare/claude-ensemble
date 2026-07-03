#!/usr/bin/env python3
"""
Test Generator Training System

Learns code → test patterns from existing repository.

Features:
1. Pattern extraction (code → test mapping)
2. Edge case discovery (boundary conditions, error paths)
3. Coverage optimization (missing test scenarios)
4. Test quality prediction (completeness score)
5. Model persistence (pickle to ~/.claude/learning/test_generator.pkl)

Training data:
- Existing test files (test_*.py)
- Code files (*.py)
- Test patterns (assertions, mocks, fixtures)
- Edge cases (boundary values, error handling)

Output:
- JSON with discovered patterns
- Trained model (.pkl)
- Test quality metrics
"""

import ast
import re
import json
import pickle
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split


@dataclass
class TestPattern:
    """Discovered test pattern"""
    pattern_type: str  # 'assertion', 'mock', 'fixture', 'edge_case'
    code_signature: str  # Function/class signature
    test_signature: str  # Test method signature
    assertions: List[str]  # Assertion types used
    edge_cases: List[str]  # Edge cases tested
    mocks: List[str]  # Mocked objects
    complexity: int  # Number of test cases
    coverage_areas: List[str]  # What aspects are tested


@dataclass
class EdgeCase:
    """Discovered edge case pattern"""
    case_type: str  # 'boundary', 'error', 'null', 'empty', 'concurrent'
    trigger: str  # What triggers this case
    expected_behavior: str  # Expected outcome
    test_pattern: str  # How it's tested
    frequency: int  # How often this pattern appears


class CodeAnalyzer:
    """Extract code features for test pattern learning"""

    def __init__(self):
        self.function_patterns = []
        self.class_patterns = []

    def analyze_file(self, filepath: Path) -> Dict[str, Any]:
        """Extract features from a code file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()

            tree = ast.parse(code)

            functions = []
            classes = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                        'lineno': node.lineno,
                        'returns': self._get_return_type(node),
                        'has_async': isinstance(node, ast.AsyncFunctionDef),
                        'complexity': self._calculate_complexity(node)
                    })

                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    classes.append({
                        'name': node.name,
                        'methods': methods,
                        'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list],
                        'lineno': node.lineno
                    })

                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        imports.extend([alias.name for alias in node.names])
                    else:
                        imports.append(node.module or '')

            return {
                'filepath': str(filepath),
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'is_test': 'test_' in filepath.name or '_test' in filepath.name
            }

        except Exception as e:
            return {'filepath': str(filepath), 'error': str(e)}

    def _get_return_type(self, node: ast.FunctionDef) -> str:
        """Extract return type annotation if present"""
        if node.returns:
            return ast.unparse(node.returns) if hasattr(ast, 'unparse') else 'Any'
        return 'None'

    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1
        for n in ast.walk(node):
            if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(n, ast.BoolOp):
                complexity += len(n.values) - 1
        return complexity


class TestAnalyzer:
    """Extract test patterns from test files"""

    def __init__(self):
        self.assertion_patterns = Counter()
        self.mock_patterns = Counter()
        self.edge_case_patterns = []

    def analyze_test_file(self, filepath: Path) -> Dict[str, Any]:
        """Extract test patterns from test file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()

            tree = ast.parse(code)

            test_methods = []
            setup_methods = []
            teardown_methods = []
            fixtures = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name.startswith('test_'):
                        assertions = self._extract_assertions(node)
                        mocks = self._extract_mocks(node)
                        edge_cases = self._detect_edge_cases(node)

                        test_methods.append({
                            'name': node.name,
                            'assertions': assertions,
                            'mocks': mocks,
                            'edge_cases': edge_cases,
                            'complexity': self._calculate_test_complexity(node),
                            'lineno': node.lineno
                        })

                        # Update pattern counters
                        for assertion in assertions:
                            self.assertion_patterns[assertion] += 1
                        for mock in mocks:
                            self.mock_patterns[mock] += 1

                    elif node.name in ('setUp', 'setUpClass', 'setUpModule'):
                        setup_methods.append(node.name)

                    elif node.name in ('tearDown', 'tearDownClass', 'tearDownModule'):
                        teardown_methods.append(node.name)

                    elif any(d.id == 'pytest.fixture' if isinstance(d, ast.Attribute) else d.id == 'fixture'
                            for d in node.decorator_list if isinstance(d, (ast.Name, ast.Attribute))):
                        fixtures.append(node.name)

            return {
                'filepath': str(filepath),
                'test_methods': test_methods,
                'setup_methods': setup_methods,
                'teardown_methods': teardown_methods,
                'fixtures': fixtures,
                'total_tests': len(test_methods)
            }

        except Exception as e:
            return {'filepath': str(filepath), 'error': str(e)}

    def _extract_assertions(self, node: ast.FunctionDef) -> List[str]:
        """Extract assertion types from test method"""
        assertions = []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute):
                    if n.func.attr.startswith('assert'):
                        assertions.append(n.func.attr)
                elif isinstance(n.func, ast.Name):
                    if n.func.id.startswith('assert'):
                        assertions.append(n.func.id)
        return assertions

    def _extract_mocks(self, node: ast.FunctionDef) -> List[str]:
        """Extract mock patterns from test method"""
        mocks = []
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Attribute):
                    if 'mock' in n.func.attr.lower() or 'patch' in n.func.attr.lower():
                        mocks.append(n.func.attr)
                elif isinstance(n.func, ast.Name):
                    if 'mock' in n.func.id.lower() or 'patch' in n.func.id.lower():
                        mocks.append(n.func.id)
        return mocks

    def _detect_edge_cases(self, node: ast.FunctionDef) -> List[str]:
        """Detect edge case testing patterns"""
        edge_cases = []

        # Check for boundary value testing (use ast.Constant for Python 3.8+)
        for n in ast.walk(node):
            if isinstance(n, ast.Constant):
                if n.value in (0, 1, -1, None, '', [], {}, 999999):
                    edge_cases.append('boundary_value')

        # Check for error handling tests
        for n in ast.walk(node):
            if isinstance(n, ast.Raise):
                edge_cases.append('error_handling')
            elif isinstance(n, ast.ExceptHandler):
                edge_cases.append('exception_test')

        # Check for concurrent execution tests
        code_str = ast.unparse(node) if hasattr(ast, 'unparse') else ''
        if 'thread' in code_str.lower() or 'concurrent' in code_str.lower():
            edge_cases.append('concurrent')

        # Check for timeout tests
        if 'timeout' in code_str.lower():
            edge_cases.append('timeout')

        # Check for empty/None tests
        if 'none' in node.name.lower() or 'empty' in node.name.lower():
            edge_cases.append('null_empty')

        return list(set(edge_cases))

    def _calculate_test_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate test complexity (number of assertions + mocks + edge cases)"""
        assertions = len(self._extract_assertions(node))
        mocks = len(self._extract_mocks(node))
        edge_cases = len(self._detect_edge_cases(node))
        return assertions + mocks + edge_cases


class TestGeneratorTrainer:
    """Train test generation model from existing code and tests"""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.code_analyzer = CodeAnalyzer()
        self.test_analyzer = TestAnalyzer()

        self.test_patterns: List[TestPattern] = []
        self.edge_cases: List[EdgeCase] = []
        self.coverage_gaps: List[Dict[str, Any]] = []

        self.vectorizer = TfidfVectorizer(max_features=100)
        self.quality_predictor = RandomForestClassifier(n_estimators=50, random_state=42)

    def train(self) -> Dict[str, Any]:
        """Train the test generator model"""
        print("📚 Training Test Generator System...")

        # Step 1: Collect training data
        print("\n1️⃣ Collecting code and test files...")
        code_files = list(self.repo_path.rglob('*.py'))
        code_files = [f for f in code_files if not f.name.startswith('test_') and '__pycache__' not in str(f)]

        test_files = list(self.repo_path.rglob('test_*.py'))
        test_files = [f for f in test_files if '__pycache__' not in str(f)]

        print(f"   Found {len(code_files)} code files, {len(test_files)} test files")

        # Step 2: Analyze code files
        print("\n2️⃣ Analyzing code patterns...")
        code_data = []
        for filepath in code_files[:100]:  # Limit for performance
            analysis = self.code_analyzer.analyze_file(filepath)
            if 'error' not in analysis:
                code_data.append(analysis)

        print(f"   Analyzed {len(code_data)} code files")

        # Step 3: Analyze test files
        print("\n3️⃣ Analyzing test patterns...")
        test_data = []
        for filepath in test_files:  # Analyze ALL test files
            analysis = self.test_analyzer.analyze_test_file(filepath)
            if 'error' not in analysis:
                test_data.append(analysis)
            else:
                print(f"   ⚠️  Error analyzing {filepath.name}: {analysis['error']}")

        print(f"   Analyzed {len(test_data)} test files")

        # Step 4: Extract patterns
        print("\n4️⃣ Extracting test patterns...")
        self._extract_patterns(code_data, test_data)
        print(f"   Discovered {len(self.test_patterns)} test patterns")

        # Step 5: Discover edge cases
        print("\n5️⃣ Discovering edge cases...")
        self._discover_edge_cases(test_data)
        print(f"   Found {len(self.edge_cases)} edge case patterns")

        # Step 6: Identify coverage gaps
        print("\n6️⃣ Identifying coverage gaps...")
        self._identify_coverage_gaps(code_data, test_data)
        print(f"   Identified {len(self.coverage_gaps)} coverage gaps")

        # Step 7: Train quality predictor
        print("\n7️⃣ Training test quality predictor...")
        quality_score = self._train_quality_predictor(test_data)
        print(f"   Quality predictor accuracy: {quality_score:.2%}")

        # Step 8: Save model
        print("\n8️⃣ Saving model...")
        model_path = Path.home() / '.claude/learning/test_generator.pkl'
        model_path.parent.mkdir(parents=True, exist_ok=True)

        model_data = {
            'test_patterns': [asdict(p) for p in self.test_patterns],
            'edge_cases': [asdict(e) for e in self.edge_cases],
            'coverage_gaps': self.coverage_gaps,
            'assertion_patterns': dict(self.test_analyzer.assertion_patterns),
            'mock_patterns': dict(self.test_analyzer.mock_patterns),
            'vectorizer': self.vectorizer,
            'quality_predictor': self.quality_predictor
        }

        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"   ✅ Model saved to {model_path}")

        # Return summary
        return {
            'test_patterns': len(self.test_patterns),
            'edge_cases_found': len(self.edge_cases),
            'coverage_gaps': len(self.coverage_gaps),
            'model_saved': True,
            'model_path': str(model_path),
            'assertion_patterns': len(self.test_analyzer.assertion_patterns),
            'mock_patterns': len(self.test_analyzer.mock_patterns),
            'quality_predictor_accuracy': quality_score,
            'code_files_analyzed': len(code_data),
            'test_files_analyzed': len(test_data)
        }

    def _extract_patterns(self, code_data: List[Dict], test_data: List[Dict]):
        """Extract code → test patterns"""
        # Match code functions to test methods
        for test_file in test_data:
            for test_method in test_file.get('test_methods', []):
                # Extract what's being tested from test name
                test_name = test_method['name']

                pattern = TestPattern(
                    pattern_type='unit_test',
                    code_signature=test_name.replace('test_', ''),
                    test_signature=test_name,
                    assertions=test_method['assertions'],
                    edge_cases=test_method['edge_cases'],
                    mocks=test_method['mocks'],
                    complexity=test_method['complexity'],
                    coverage_areas=self._infer_coverage_areas(test_method)
                )

                self.test_patterns.append(pattern)

    def _discover_edge_cases(self, test_data: List[Dict]):
        """Discover common edge case patterns"""
        edge_case_counter = defaultdict(list)

        for test_file in test_data:
            for test_method in test_file.get('test_methods', []):
                for edge_case in test_method['edge_cases']:
                    edge_case_counter[edge_case].append(test_method['name'])

        # Create EdgeCase objects
        for case_type, occurrences in edge_case_counter.items():
            edge_case = EdgeCase(
                case_type=case_type,
                trigger=self._infer_trigger(case_type),
                expected_behavior=self._infer_expected_behavior(case_type),
                test_pattern=self._infer_test_pattern(case_type),
                frequency=len(occurrences)
            )
            self.edge_cases.append(edge_case)

    def _identify_coverage_gaps(self, code_data: List[Dict], test_data: List[Dict]):
        """Identify missing test coverage"""
        # Get all tested functions
        tested_functions = set()
        for test_file in test_data:
            for test_method in test_file.get('test_methods', []):
                tested_name = test_method['name'].replace('test_', '')
                tested_functions.add(tested_name)

        # Find untested functions
        for code_file in code_data:
            for func in code_file.get('functions', []):
                if func['name'] not in tested_functions and not func['name'].startswith('_'):
                    self.coverage_gaps.append({
                        'function': func['name'],
                        'file': code_file['filepath'],
                        'complexity': func['complexity'],
                        'priority': 'high' if func['complexity'] > 5 else 'medium'
                    })

    def _train_quality_predictor(self, test_data: List[Dict]) -> float:
        """Train a model to predict test quality"""
        # Extract features
        X = []
        y = []

        for test_file in test_data:
            for test_method in test_file.get('test_methods', []):
                # Features: assertion count, mock count, edge case count
                features = [
                    len(test_method['assertions']),
                    len(test_method['mocks']),
                    len(test_method['edge_cases']),
                    test_method['complexity']
                ]

                # Label: quality score (0-1 based on complexity and coverage)
                quality = min(1.0, test_method['complexity'] / 10.0)

                X.append(features)
                y.append(1 if quality > 0.5 else 0)

        if len(X) < 10:
            print("   ⚠️  Insufficient data for quality predictor, using defaults")
            return 0.0

        # Train model
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.quality_predictor.fit(X_train, y_train)

        return self.quality_predictor.score(X_test, y_test)

    def _infer_coverage_areas(self, test_method: Dict) -> List[str]:
        """Infer what areas a test covers"""
        areas = []
        if test_method['assertions']:
            areas.append('correctness')
        if test_method['mocks']:
            areas.append('integration')
        if 'boundary_value' in test_method['edge_cases']:
            areas.append('boundary_conditions')
        if 'error_handling' in test_method['edge_cases']:
            areas.append('error_handling')
        if 'concurrent' in test_method['edge_cases']:
            areas.append('concurrency')
        return areas

    def _infer_trigger(self, case_type: str) -> str:
        """Infer what triggers an edge case"""
        triggers = {
            'boundary_value': 'Min/max values, zero, -1',
            'error_handling': 'Invalid input, exceptions',
            'null_empty': 'None, empty string, empty list',
            'concurrent': 'Multiple threads/processes',
            'timeout': 'Long-running operations',
            'exception_test': 'Expected exceptions'
        }
        return triggers.get(case_type, 'Unknown trigger')

    def _infer_expected_behavior(self, case_type: str) -> str:
        """Infer expected behavior for edge case"""
        behaviors = {
            'boundary_value': 'Handle min/max gracefully',
            'error_handling': 'Raise appropriate exception',
            'null_empty': 'Return default or raise error',
            'concurrent': 'Thread-safe execution',
            'timeout': 'Timeout after threshold',
            'exception_test': 'Correct exception type raised'
        }
        return behaviors.get(case_type, 'Unknown behavior')

    def _infer_test_pattern(self, case_type: str) -> str:
        """Infer how to test this edge case"""
        patterns = {
            'boundary_value': 'Test with 0, -1, MAX_INT values',
            'error_handling': 'Use assertRaises or pytest.raises',
            'null_empty': 'Test with None, "", [], {}',
            'concurrent': 'Use threading.Thread or concurrent.futures',
            'timeout': 'Use subprocess.TimeoutExpired or timeout decorator',
            'exception_test': 'Verify exception type and message'
        }
        return patterns.get(case_type, 'Unknown pattern')


def main():
    """Train test generator system"""
    repo_path = Path('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills')

    trainer = TestGeneratorTrainer(repo_path)
    results = trainer.train()

    # Save results as JSON
    results_path = Path.home() / '.claude/learning/test_generator_results.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Training complete!")
    print(f"\n📊 Results:")
    print(f"   Test patterns: {results['test_patterns']}")
    print(f"   Edge cases: {results['edge_cases_found']}")
    print(f"   Coverage gaps: {results['coverage_gaps']}")
    print(f"   Model saved: {results['model_saved']}")

    return results


if __name__ == '__main__':
    results = main()
    sys.exit(0 if results['model_saved'] else 1)
