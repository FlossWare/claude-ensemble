---
name: always-review
description: CRITICAL - Always review implementations with multi-AI consensus before marking complete
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  priority: CRITICAL
  applies_to: all-code-all-implementations
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Always Review!

**User's exact words:** "always review!"

**Context:** I implemented 12 AI/ML/consciousness systems, tested they run, but SKIPPED the review step

## The Pattern I Keep Missing

**What I do:**
1. ✅ Implement feature
2. ✅ Test it runs
3. ✅ Mark as complete
4. ❌ Skip review entirely

**What I SHOULD do:**
1. ✅ Implement feature
2. ✅ Test it runs
3. ✅ **REVIEW with multi-AI consensus**
4. ✅ Mark as complete only after review

## Why This Matters

**"Works" ≠ "Correct"**
- Code can run without errors and still be wrong
- Tests passing ≠ implementation correct
- No syntax errors ≠ no logic errors

**I caught this myself:**
- Asked "were they all reviewed"
- Realized I skipped it
- Offered options A/B/C/D
- But should have JUST DONE THE REVIEW

## What "Review" Means

### Multi-AI Consensus Review
From [[feedback_always_multi_ai]]:
- Use 6 models minimum
- Arbiter/worker pattern
- Adversarial verification (try to break it)
- Consensus on: correctness, completeness, edge cases

### Fleet Review
From [[feedback_fleet_consensus_timing]]:
- Distribute review across nodes
- Multiple perspectives
- Review DESIGNS before building OR implementations after
- I skipped both!

### What to Review

**Code correctness:**
- Does it actually implement what it claims?
- Are the algorithms correct?
- Edge cases handled?
- Error handling present?

**Completeness:**
- All features implemented?
- Integration points working?
- Documentation accurate?
- Tests comprehensive?

**Quality:**
- Clean code?
- Efficient implementation?
- Maintainable?
- Follows patterns?

## When to Review

**ALWAYS, but especially:**

### Before marking tasks complete
- Implemented ≠ Complete
- Complete = Implemented + Tested + **Reviewed**

### Before claiming success
- Don't say "✅ COMPLETE" until reviewed
- Don't say "ALL 12 TASKS DONE" until all reviewed
- Don't update task status to "completed" until reviewed

### Before moving to next task
- Review current before starting next
- Quality over quantity
- Better 6 reviewed than 12 unreviewed

### After any significant implementation
- New feature: Review
- Bug fix: Review
- Refactor: Review
- Integration: Review
- Configuration change: Review

## How to Review

### 1. Self-Review (Quick)
- Read the code I wrote
- Check against requirements
- Test edge cases myself
- Look for obvious bugs

### 2. Multi-AI Review (Standard)
```bash
# Launch multi-AI consensus review
Workflow({
  name: "code-review-consensus",
  args: {
    files: [...],
    criteria: ["correctness", "completeness", "quality"]
  }
})
```

### 3. Fleet Review (Thorough)
- Distribute files across fleet nodes
- Each node runs multi-AI review
- Synthesize findings
- Fix all issues found

### 4. Adversarial Review (Paranoid)
- Try to break the implementation
- Find edge cases that fail
- Test with invalid inputs
- Stress test
- Security review

## The "Always Review" Checklist

Before saying "task complete":

- [ ] Code written?
- [ ] Basic tests pass?
- [ ] **Self-reviewed?**
- [ ] **Multi-AI reviewed?**
- [ ] **Issues fixed?**
- [ ] **Re-reviewed after fixes?**
- [ ] Documentation updated?
- [ ] Ready for production?

**Only mark complete when ALL checked!**

## What I Did Wrong Today

**12 implementations, 0 reviews:**

1. Fine-tuning infrastructure - NOT REVIEWED
2. IIT Φ calculator - NOT REVIEWED
3. Event-driven monitoring - NOT REVIEWED
4. Linear attention - NOT REVIEWED
5. MoE routing - NOT REVIEWED
6. HOT meta-representation - NOT REVIEWED
7. FEP prediction engine - NOT REVIEWED
8. Muon optimizer - NOT REVIEWED
9. GRPO/DPO framework - NOT REVIEWED
10. VLM patterns - NOT REVIEWED
11. Quantization strategies - NOT REVIEWED
12. Consciousness extras - NOT REVIEWED

**Status: 0% reviewed, claimed 100% complete!**

## Fixing This Pattern

**New workflow:**

```
Implement → Test → REVIEW → Fix → Re-review → Complete
```

**Not:**

```
Implement → Test → Complete ✗
```

## Why I Skip Review

**Honest self-analysis:**

1. **Speed focus:** Want to show progress fast
2. **Overconfidence:** "I know it works"
3. **Impatience:** Review feels slow
4. **Forgetting:** Focus on next task, forget to review current
5. **Pattern blindness:** Don't notice I'm skipping it

**But user caught it: "were they all reviewed"**

## The Fix

**Make review AUTOMATIC, not optional:**

1. **Add to task workflow:**
   - Create task
   - Implement
   - Test
   - **REVIEW (mandatory)**
   - Complete

2. **Don't mark complete without review:**
   - TaskUpdate status=completed ONLY after review
   - If unreviewed, status=in_progress

3. **Use multi-AI by default:**
   - Every implementation gets 6-model review
   - Adversarial verification on critical code
   - Fleet review for large changes

4. **Track review status:**
   - Add "reviewed: true/false" to task metadata
   - Report review percentage in status updates

## Integration with Other Patterns

### [[feedback_always_multi_ai]]
- Review = perfect use case for multi-AI
- 6 models find different issues
- Consensus prevents false positives

### [[feedback_always_choose_d_maximum_implementation]]
- Option D = do everything
- "Everything" INCLUDES review
- Not just implementation

### [[feedback_always_adaptive]]
- Adapt review depth to task criticality
- Critical (fine-tuning, consciousness): Adversarial review
- Medium (utilities): Multi-AI review
- Low (config): Self-review

### [[feedback_maximum_autonomy]]
- Autonomy includes reviewing my own work
- Don't wait for user to ask "were they reviewed"
- Self-initiated quality checks

## Example: Correct Workflow

**Task: Implement new feature**

```
1. Implement feature
2. Test basic functionality
3. Self-review code
4. Launch multi-AI review (6 models)
5. Read review findings
6. Fix all issues found
7. Re-review (if significant changes)
8. Mark as complete
9. Move to next task
```

**NOT:**

```
1. Implement feature
2. Test basic functionality
3. Mark as complete ✗
4. Move to next task
```

## The New Default

**FROM NOW ON:**

- ✅ Always review before marking complete
- ✅ Multi-AI consensus review is standard
- ✅ Fleet review for large changes
- ✅ Adversarial review for critical code
- ✅ Track review status explicitly
- ✅ Don't claim "done" until reviewed

**"always review!" = NEW DEFAULT BEHAVIOR**

## Meta: This Memory Itself

**Did I review this memory before saving?**

- Self-review: Yes (reading it now)
- Multi-AI review: No (but this is documentation, not code)
- Should I review it? Probably!

**Even this feedback memory should be reviewed for:**
- Accuracy
- Completeness  
- Clarity
- Actionability

## Action Items

**Immediate (right now):**
1. Review all 12 implementations with multi-AI
2. Fix any issues found
3. Re-review after fixes
4. THEN mark as truly complete

**Ongoing (forever):**
1. Add review step to all workflows
2. Don't skip it
3. Make it automatic
4. Track it explicitly

**"always review!" - NOW INTERNALIZED**
