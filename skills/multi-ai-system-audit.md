# multi-ai-system-audit

Multi-AI consensus audit of system architecture, quality, and improvement opportunities.

## What It Does

Uses 16 AI agents across 6 different models (Opus, Sonnet, Haiku, Fable, GPT-4o, Gemini) to comprehensively audit a codebase from multiple perspectives:

1. **Architecture Analysis** (6 models) - Design patterns, orchestration quality, modularity
2. **Component Inventory** (3 models) - Workflows, skills, libraries, SDLC coverage
3. **Integration Analysis** (3 models) - Coupling, cohesion, dependencies, reliability
4. **Quality Assessment** (4 models) - Code quality, documentation, test coverage, gaps
5. **Audit Synthesis** (1 arbiter) - Comprehensive report with prioritized recommendations

## Output

Markdown audit report with:
- Executive summary (key insights)
- System strengths (what works well)
- System weaknesses (what needs improvement)
- Critical issues (P0 blockers)
- Recommended actions (P0/P1/P2 prioritized)
- Strategic recommendations (long-term)
- Model consensus analysis (agreement vs disagreement)

## Usage

```bash
# Audit the claude-global-skills system (default)
/multi-ai-system-audit

# Audit a different repository
/multi-ai-system-audit repo_path=/path/to/repo system_name=my-project
```

## When to Use

- **Before major refactoring** - Understand current state and risks
- **After significant changes** - Verify integration quality
- **Quality assessment** - Get multi-perspective evaluation
- **Strategic planning** - Identify improvement priorities
- **New team member onboarding** - Comprehensive system overview

## Not a Learning System

**IMPORTANT:** This workflow uses the term "audit" not "deep learning" because:
- ✅ It's **analysis and research** by multiple AI models
- ✅ It's **distributed orchestration** over pre-trained models
- ❌ It's NOT machine learning (no training, no gradient descent)
- ❌ It's NOT fine-tuning (no weight updates)
- ❌ It's NOT a learning algorithm

The value comes from **diverse perspectives** (6 different model architectures) catching issues that single-model analysis misses, not from any learning or training process.

## Cost

Approximately 30-50k tokens across 16 agents. Budget: +100k recommended.

## Phases

1. **Architecture Analysis** - 6-model consensus on design patterns
2. **Component Inventory** - Catalog all components
3. **Integration Analysis** - Assess coupling and dependencies
4. **Quality Assessment** - Score code quality and identify gaps
5. **Audit Synthesis** - Fable arbiter creates final report

## Invoke

Workflow({ name: "multi-ai-system-audit", args: { repo_path: "/path/to/repo", system_name: "project-name" } })
