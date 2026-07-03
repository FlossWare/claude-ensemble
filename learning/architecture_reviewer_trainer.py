#!/usr/bin/env python3
"""
Architecture Reviewer System Trainer

Learns design patterns (good and bad) from codebase analysis.
Detects anti-patterns, scalability issues, and dependency health.

Saves model to ~/.claude/learning/architecture_reviewer.pkl
"""

import os
import re
import json
import pickle
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Any


@dataclass
class Pattern:
    """Design pattern detected in code"""
    name: str
    type: str  # 'good', 'bad', 'neutral'
    frequency: int
    files: List[str]
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    examples: List[str]


@dataclass
class DependencyHealth:
    """Health metrics for dependencies"""
    name: str
    version: str
    usage_count: int
    is_dev_dependency: bool
    security_concerns: List[str]
    outdated: bool


@dataclass
class ArchitectureMetrics:
    """Overall architecture health metrics"""
    total_files: int
    total_lines: int
    avg_file_complexity: float
    test_coverage_ratio: float
    circular_dependencies: List[str]
    code_duplication_score: float
    modularity_score: float


class ArchitectureReviewer:
    """AI system for architecture review and pattern detection"""

    def __init__(self):
        self.patterns: List[Pattern] = []
        self.anti_patterns: List[Pattern] = []
        self.dependencies: Dict[str, DependencyHealth] = {}
        self.metrics: ArchitectureMetrics = None
        self.file_patterns: Dict[str, List[str]] = defaultdict(list)

    def analyze_codebase(self, base_path: str):
        """Analyze entire codebase for patterns and metrics"""
        print(f"📊 Analyzing codebase: {base_path}")

        # Collect all source files
        js_files = list(Path(base_path).rglob("*.js")) + \
                   list(Path(base_path).rglob("*.mjs")) + \
                   list(Path(base_path).rglob("*.cjs"))
        py_files = list(Path(base_path).rglob("*.py"))

        # Filter out node_modules, worktrees, and test files for pattern analysis
        source_files = [
            f for f in (js_files + py_files)
            if 'node_modules' not in str(f) and
               '.claude/worktrees' not in str(f)
        ]

        test_files = [
            f for f in js_files + py_files
            if '.test.' in str(f) or 'test_' in str(f.name)
        ]

        print(f"  Found {len(source_files)} source files, {len(test_files)} test files")

        # Analyze patterns
        self._detect_good_patterns(source_files)
        self._detect_anti_patterns(source_files)
        self._analyze_dependencies(base_path)
        self._calculate_metrics(source_files, test_files)

    def _detect_good_patterns(self, files: List[Path]):
        """Detect good design patterns"""
        print("  ✅ Detecting good patterns...")

        patterns_found = defaultdict(lambda: {"count": 0, "files": [], "examples": []})

        for file_path in files:
            try:
                content = file_path.read_text(errors='ignore')

                # Pattern: Circuit Breaker
                if re.search(r'circuit.*breaker|CircuitBreaker', content, re.IGNORECASE):
                    patterns_found["Circuit Breaker"]["count"] += 1
                    patterns_found["Circuit Breaker"]["files"].append(str(file_path))
                    patterns_found["Circuit Breaker"]["examples"].append(self._extract_example(content, r'circuit.*breaker'))

                # Pattern: Dependency Injection
                if re.search(r'constructor.*\{.*inject|dependencies.*=.*\{', content):
                    patterns_found["Dependency Injection"]["count"] += 1
                    patterns_found["Dependency Injection"]["files"].append(str(file_path))

                # Pattern: Factory Pattern
                if re.search(r'create[A-Z]\w+|factory\w*\(|Factory', content):
                    patterns_found["Factory Pattern"]["count"] += 1
                    patterns_found["Factory Pattern"]["files"].append(str(file_path))

                # Pattern: Strategy Pattern (Thompson Sampling, Consensus)
                if re.search(r'strategy.*=|selectStrategy|thompson.*sampling', content, re.IGNORECASE):
                    patterns_found["Strategy Pattern"]["count"] += 1
                    patterns_found["Strategy Pattern"]["files"].append(str(file_path))
                    patterns_found["Strategy Pattern"]["examples"].append(self._extract_example(content, r'strategy'))

                # Pattern: Observer/Event-Driven
                if re.search(r'\.on\(|\.emit\(|addEventListener|EventEmitter', content):
                    patterns_found["Observer Pattern"]["count"] += 1
                    patterns_found["Observer Pattern"]["files"].append(str(file_path))

                # Pattern: Adapter Pattern
                if re.search(r'adapter|Adapter|adapt\w+\(', content):
                    patterns_found["Adapter Pattern"]["count"] += 1
                    patterns_found["Adapter Pattern"]["files"].append(str(file_path))

                # Pattern: Graceful Degradation
                if re.search(r'try.*\{.*fallback|catch.*\{.*graceful|degraded.*mode', content, re.IGNORECASE):
                    patterns_found["Graceful Degradation"]["count"] += 1
                    patterns_found["Graceful Degradation"]["files"].append(str(file_path))
                    patterns_found["Graceful Degradation"]["examples"].append(self._extract_example(content, r'fallback|degraded'))

                # Pattern: Singleton (used correctly with lazy init)
                if re.search(r'let\s+instance\s*=\s*null.*getInstance|private\s+static\s+instance', content):
                    patterns_found["Singleton Pattern"]["count"] += 1
                    patterns_found["Singleton Pattern"]["files"].append(str(file_path))

                # Pattern: Connection Pooling
                if re.search(r'new\s+Pool\(|createPool|pool.*\{.*max:', content):
                    patterns_found["Connection Pooling"]["count"] += 1
                    patterns_found["Connection Pooling"]["files"].append(str(file_path))

                # Pattern: Error Handling with Context
                if re.search(r'catch\s*\(\s*\w+\s*\)\s*\{[^}]*console\.(error|warn).*message', content):
                    patterns_found["Contextual Error Handling"]["count"] += 1
                    patterns_found["Contextual Error Handling"]["files"].append(str(file_path))

                # Pattern: Configuration Externalization
                if re.search(r'process\.env\.|config\.|settings\.|\.env', content):
                    patterns_found["Configuration Externalization"]["count"] += 1
                    patterns_found["Configuration Externalization"]["files"].append(str(file_path))

                # Pattern: Retry with Exponential Backoff
                if re.search(r'retry.*backoff|exponential.*delay|Math\.pow.*attempt', content, re.IGNORECASE):
                    patterns_found["Retry with Backoff"]["count"] += 1
                    patterns_found["Retry with Backoff"]["files"].append(str(file_path))

            except Exception as e:
                print(f"    ⚠ Error reading {file_path}: {e}")
                continue

        # Convert to Pattern objects
        descriptions = {
            "Circuit Breaker": "Prevents cascade failures by opening circuit on repeated errors",
            "Dependency Injection": "Loose coupling through constructor/parameter injection",
            "Factory Pattern": "Centralized object creation with abstraction",
            "Strategy Pattern": "Runtime algorithm selection (Thompson Sampling, Consensus)",
            "Observer Pattern": "Event-driven architecture with loose coupling",
            "Adapter Pattern": "Interface translation for integration (postgres-adapter, etc.)",
            "Graceful Degradation": "Fallback behavior when dependencies fail",
            "Singleton Pattern": "Controlled single instance (pools, clients)",
            "Connection Pooling": "Resource reuse for database/API connections",
            "Contextual Error Handling": "Errors include context for debugging",
            "Configuration Externalization": "Environment-based config, not hardcoded",
            "Retry with Backoff": "Transient failure handling with exponential delays",
        }

        for name, data in patterns_found.items():
            if data["count"] > 0:
                pattern = Pattern(
                    name=name,
                    type='good',
                    frequency=data["count"],
                    files=data["files"][:10],  # Limit to 10 examples
                    description=descriptions.get(name, "Design pattern detected"),
                    severity='low',  # Good patterns are low severity (informational)
                    examples=data["examples"][:3]
                )
                self.patterns.append(pattern)

        print(f"    Found {len(self.patterns)} good patterns")

    def _detect_anti_patterns(self, files: List[Path]):
        """Detect anti-patterns and code smells"""
        print("  ⚠ Detecting anti-patterns...")

        anti_patterns_found = defaultdict(lambda: {"count": 0, "files": [], "examples": []})

        for file_path in files:
            try:
                content = file_path.read_text(errors='ignore')
                lines = content.split('\n')

                # Anti-pattern: God Object (very large classes/modules)
                if len(lines) > 1000:
                    anti_patterns_found["God Object"]["count"] += 1
                    anti_patterns_found["God Object"]["files"].append(str(file_path))
                    anti_patterns_found["God Object"]["examples"].append(f"{file_path.name}: {len(lines)} lines")

                # Anti-pattern: Callback Hell (deeply nested callbacks)
                nested_callbacks = len(re.findall(r'function.*\{[^}]*function.*\{[^}]*function', content))
                if nested_callbacks > 3:
                    anti_patterns_found["Callback Hell"]["count"] += 1
                    anti_patterns_found["Callback Hell"]["files"].append(str(file_path))

                # Anti-pattern: Magic Numbers
                magic_numbers = re.findall(r'(?<!\.)\b\d{2,}\b(?!\s*ms|\s*%)', content)
                if len(magic_numbers) > 10:
                    anti_patterns_found["Magic Numbers"]["count"] += 1
                    anti_patterns_found["Magic Numbers"]["files"].append(str(file_path))
                    anti_patterns_found["Magic Numbers"]["examples"].append(f"Found {len(magic_numbers)} magic numbers")

                # Anti-pattern: Empty Catch Blocks
                empty_catches = len(re.findall(r'catch\s*\([^)]*\)\s*\{\s*\}', content))
                if empty_catches > 0:
                    anti_patterns_found["Empty Catch Blocks"]["count"] += empty_catches
                    anti_patterns_found["Empty Catch Blocks"]["files"].append(str(file_path))
                    anti_patterns_found["Empty Catch Blocks"]["examples"].append(f"{file_path.name}: {empty_catches} empty catches")

                # Anti-pattern: Hardcoded Credentials/Secrets
                if re.search(r'password\s*=\s*["\'](?!.*process\.env)|api.*key\s*=\s*["\'](?!.*process\.env)', content, re.IGNORECASE):
                    anti_patterns_found["Hardcoded Secrets"]["count"] += 1
                    anti_patterns_found["Hardcoded Secrets"]["files"].append(str(file_path))

                # Anti-pattern: Monolithic Functions (> 100 lines)
                function_matches = re.finditer(r'(function|async\s+function)\s+\w+.*?\{', content)
                for match in function_matches:
                    start = match.start()
                    # Estimate function length (crude approximation)
                    rest = content[start:]
                    brace_count = 1
                    pos = match.end() - start
                    while brace_count > 0 and pos < len(rest):
                        if rest[pos] == '{':
                            brace_count += 1
                        elif rest[pos] == '}':
                            brace_count -= 1
                        pos += 1

                    func_lines = rest[:pos].count('\n')
                    if func_lines > 100:
                        anti_patterns_found["Monolithic Functions"]["count"] += 1
                        anti_patterns_found["Monolithic Functions"]["files"].append(str(file_path))
                        break  # One per file is enough

                # Anti-pattern: Tight Coupling (many direct imports)
                import_count = len(re.findall(r'^import |^from .* import |require\(', content, re.MULTILINE))
                if import_count > 30:
                    anti_patterns_found["High Coupling"]["count"] += 1
                    anti_patterns_found["High Coupling"]["files"].append(str(file_path))
                    anti_patterns_found["High Coupling"]["examples"].append(f"{file_path.name}: {import_count} imports")

                # Anti-pattern: Lack of Error Handling
                async_calls = len(re.findall(r'await\s+', content))
                try_blocks = len(re.findall(r'try\s*\{', content))
                if async_calls > 5 and try_blocks == 0:
                    anti_patterns_found["Missing Error Handling"]["count"] += 1
                    anti_patterns_found["Missing Error Handling"]["files"].append(str(file_path))

                # Anti-pattern: Code Duplication (repeated function signatures)
                function_sigs = re.findall(r'function\s+(\w+)\s*\(', content)
                sig_counts = Counter(function_sigs)
                duplicates = [name for name, count in sig_counts.items() if count > 1]
                if len(duplicates) > 3:
                    anti_patterns_found["Code Duplication"]["count"] += 1
                    anti_patterns_found["Code Duplication"]["files"].append(str(file_path))

            except Exception as e:
                continue

        # Convert to Pattern objects with severity
        severities = {
            "God Object": "high",
            "Callback Hell": "medium",
            "Magic Numbers": "low",
            "Empty Catch Blocks": "high",
            "Hardcoded Secrets": "critical",
            "Monolithic Functions": "medium",
            "High Coupling": "medium",
            "Missing Error Handling": "high",
            "Code Duplication": "medium",
        }

        descriptions = {
            "God Object": "Files > 1000 lines indicate lack of separation of concerns",
            "Callback Hell": "Deeply nested callbacks reduce readability and maintainability",
            "Magic Numbers": "Hardcoded numbers without named constants",
            "Empty Catch Blocks": "Swallowing errors without logging or handling",
            "Hardcoded Secrets": "Credentials in source code (security risk)",
            "Monolithic Functions": "Functions > 100 lines violate single responsibility",
            "High Coupling": "Too many dependencies reduce modularity",
            "Missing Error Handling": "Async code without try/catch can crash",
            "Code Duplication": "Repeated code violates DRY principle",
        }

        for name, data in anti_patterns_found.items():
            if data["count"] > 0:
                pattern = Pattern(
                    name=name,
                    type='bad',
                    frequency=data["count"],
                    files=data["files"][:10],
                    description=descriptions.get(name, "Anti-pattern detected"),
                    severity=severities.get(name, 'medium'),
                    examples=data["examples"][:3]
                )
                self.anti_patterns.append(pattern)

        print(f"    Found {len(self.anti_patterns)} anti-patterns")

    def _analyze_dependencies(self, base_path: str):
        """Analyze dependency health from package.json and requirements.txt"""
        print("  📦 Analyzing dependencies...")

        # JavaScript dependencies
        package_json = Path(base_path) / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                pkg = json.load(f)

                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})

                for name, version in deps.items():
                    self.dependencies[name] = DependencyHealth(
                        name=name,
                        version=version,
                        usage_count=0,  # Would need AST analysis
                        is_dev_dependency=False,
                        security_concerns=[],
                        outdated=False  # Would need npm outdated
                    )

                for name, version in dev_deps.items():
                    self.dependencies[name] = DependencyHealth(
                        name=name,
                        version=version,
                        usage_count=0,
                        is_dev_dependency=True,
                        security_concerns=[],
                        outdated=False
                    )

        # Python dependencies
        requirements = Path(base_path) / "config" / "requirements.txt"
        if requirements.exists():
            for line in requirements.read_text().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = re.split(r'[>=<]', line)
                    name = parts[0].strip()
                    version = parts[1].strip() if len(parts) > 1 else 'unknown'

                    self.dependencies[name] = DependencyHealth(
                        name=name,
                        version=version,
                        usage_count=0,
                        is_dev_dependency=False,
                        security_concerns=[],
                        outdated=False
                    )

        print(f"    Analyzed {len(self.dependencies)} dependencies")

    def _calculate_metrics(self, source_files: List[Path], test_files: List[Path]):
        """Calculate overall architecture metrics"""
        print("  📈 Calculating architecture metrics...")

        total_lines = 0
        complexity_sum = 0

        for file_path in source_files:
            try:
                lines = file_path.read_text(errors='ignore').split('\n')
                total_lines += len(lines)

                # Simple complexity: conditionals + loops + functions
                content = '\n'.join(lines)
                conditionals = len(re.findall(r'\bif\b|\belse\b|\bswitch\b|\bcase\b', content))
                loops = len(re.findall(r'\bfor\b|\bwhile\b|\bdo\b', content))
                functions = len(re.findall(r'\bfunction\b|\bdef\b', content))

                complexity_sum += conditionals + loops + functions
            except:
                continue

        avg_complexity = complexity_sum / len(source_files) if source_files else 0
        test_ratio = len(test_files) / len(source_files) if source_files else 0

        # Estimate modularity based on avg file size
        avg_file_size = total_lines / len(source_files) if source_files else 0
        modularity = max(0, 100 - (avg_file_size / 5))  # Penalize large files

        self.metrics = ArchitectureMetrics(
            total_files=len(source_files),
            total_lines=total_lines,
            avg_file_complexity=avg_complexity,
            test_coverage_ratio=test_ratio,
            circular_dependencies=[],  # Would need AST analysis
            code_duplication_score=0.0,  # Would need deep analysis
            modularity_score=modularity
        )

        print(f"    Metrics calculated: {len(source_files)} files, {total_lines} lines")

    def _extract_example(self, content: str, pattern: str, context_lines: int = 3) -> str:
        """Extract code example around pattern match"""
        match = re.search(pattern, content, re.IGNORECASE)
        if not match:
            return ""

        lines = content[:match.start()].split('\n')
        line_num = len(lines)
        all_lines = content.split('\n')

        start = max(0, line_num - context_lines)
        end = min(len(all_lines), line_num + context_lines)

        example = '\n'.join(all_lines[start:end])
        return example[:200]  # Truncate to 200 chars

    def save(self, output_path: str):
        """Save trained model to disk"""
        print(f"\n💾 Saving model to {output_path}")

        model_data = {
            'patterns': [asdict(p) for p in self.patterns],
            'anti_patterns': [asdict(p) for p in self.anti_patterns],
            'dependencies': {k: asdict(v) for k, v in self.dependencies.items()},
            'metrics': asdict(self.metrics) if self.metrics else None,
        }

        with open(output_path, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"  ✅ Model saved ({len(self.patterns)} patterns, {len(self.anti_patterns)} anti-patterns)")

    def generate_report(self) -> Dict[str, Any]:
        """Generate JSON report of findings"""
        return {
            'summary': {
                'total_patterns': len(self.patterns),
                'total_anti_patterns': len(self.anti_patterns),
                'total_dependencies': len(self.dependencies),
                'critical_anti_patterns': len([p for p in self.anti_patterns if p.severity == 'critical']),
                'high_severity_anti_patterns': len([p for p in self.anti_patterns if p.severity == 'high']),
            },
            'top_patterns': [asdict(p) for p in sorted(self.patterns, key=lambda p: p.frequency, reverse=True)[:5]],
            'top_anti_patterns': [asdict(p) for p in sorted(
                self.anti_patterns,
                key=lambda p: (
                    {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(p.severity, 0),
                    p.frequency
                ),
                reverse=True
            )[:10]],
            'metrics': asdict(self.metrics) if self.metrics else None,
            'scalability_concerns': self._identify_scalability_concerns(),
        }

    def _identify_scalability_concerns(self) -> List[Dict[str, str]]:
        """Identify scalability issues from patterns and metrics"""
        concerns = []

        # Check for blocking operations
        if any(p.name == "Missing Error Handling" for p in self.anti_patterns):
            concerns.append({
                "type": "reliability",
                "severity": "high",
                "description": "Async code without error handling can cause crashes under load"
            })

        # Check for resource management
        if not any(p.name == "Connection Pooling" for p in self.patterns):
            concerns.append({
                "type": "resource_management",
                "severity": "medium",
                "description": "No connection pooling detected - may exhaust connections under load"
            })

        # Check for modularity
        if self.metrics and self.metrics.modularity_score < 50:
            concerns.append({
                "type": "maintainability",
                "severity": "medium",
                "description": f"Low modularity score ({self.metrics.modularity_score:.1f}/100) - large files reduce maintainability"
            })

        # Check for high coupling
        high_coupling = [p for p in self.anti_patterns if p.name == "High Coupling"]
        if high_coupling:
            concerns.append({
                "type": "coupling",
                "severity": "medium",
                "description": f"High coupling detected in {len(high_coupling[0].files)} files - reduces flexibility"
            })

        return concerns


def main():
    """Train architecture reviewer and save model"""
    print("🏗️  Architecture Reviewer Training")
    print("=" * 60)

    # Determine codebase path
    codebase_path = os.environ.get('CODEBASE_PATH',
                                    '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills')

    reviewer = ArchitectureReviewer()
    reviewer.analyze_codebase(codebase_path)

    # Generate report
    report = reviewer.generate_report()

    print("\n📊 Analysis Report")
    print("=" * 60)
    print(f"Patterns Found: {report['summary']['total_patterns']}")
    print(f"Anti-Patterns: {report['summary']['total_anti_patterns']}")
    print(f"  - Critical: {report['summary']['critical_anti_patterns']}")
    print(f"  - High: {report['summary']['high_severity_anti_patterns']}")
    print(f"Dependencies: {report['summary']['total_dependencies']}")

    if report['metrics']:
        print(f"\nArchitecture Metrics:")
        print(f"  - Files: {report['metrics']['total_files']}")
        print(f"  - Lines: {report['metrics']['total_lines']:,}")
        print(f"  - Avg Complexity: {report['metrics']['avg_file_complexity']:.1f}")
        print(f"  - Test Ratio: {report['metrics']['test_coverage_ratio']:.2f}")
        print(f"  - Modularity: {report['metrics']['modularity_score']:.1f}/100")

    print(f"\nTop Patterns:")
    for i, pattern in enumerate(report['top_patterns'], 1):
        p = pattern if isinstance(pattern, dict) else asdict(pattern)
        print(f"  {i}. {p['name']} ({p['frequency']}x)")

    print(f"\nTop Anti-Patterns:")
    for i, pattern in enumerate(report['top_anti_patterns'], 1):
        p = pattern if isinstance(pattern, dict) else asdict(pattern)
        print(f"  {i}. {p['name']} [{p['severity'].upper()}] ({p['frequency']}x)")

    if report['scalability_concerns']:
        print(f"\nScalability Concerns:")
        for concern in report['scalability_concerns']:
            print(f"  ⚠ [{concern['severity'].upper()}] {concern['description']}")

    # Save model
    output_path = os.path.expanduser('~/.claude/learning/architecture_reviewer.pkl')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    reviewer.save(output_path)

    # Save JSON report
    json_path = os.path.expanduser('~/.claude/learning/architecture_reviewer_report.json')
    with open(json_path, 'w') as f:
        # Convert Pattern objects to dicts for JSON serialization
        serializable_report = {
            'summary': report['summary'],
            'top_patterns': [asdict(p) if hasattr(p, '__dict__') else p for p in report['top_patterns']],
            'top_anti_patterns': [asdict(p) if hasattr(p, '__dict__') else p for p in report['top_anti_patterns']],
            'metrics': report['metrics'],
            'scalability_concerns': report['scalability_concerns'],
        }
        json.dump(serializable_report, f, indent=2)

    print(f"\n✅ Training complete!")
    print(f"   Model: {output_path}")
    print(f"   Report: {json_path}")

    # Return structured output
    return {
        "patterns_found": len(reviewer.patterns),
        "anti_patterns": [p.name for p in reviewer.anti_patterns],
        "model_saved": True
    }


if __name__ == '__main__':
    result = main()
