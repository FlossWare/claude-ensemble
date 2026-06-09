---
name: feedback_clean_api_naming
description: User prefers clean API naming without version suffixes in class names
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 43468100-682a-41f1-8f56-f5c078edba57
---

User prefers clean, professional API naming without version numbers in class names. Remove dual-version nomenclature in favor of single unified API.

**Why:** User explicitly requested "please remove all references to V1 and also make the version be 1.0". They wanted to consolidate FileBackedListV2/MapV2/SetV2 into FileBackedList/Map/Set, eliminating confusion from having both V1 and V2 classes.

**How to apply:** 
- Use version numbers in pom.xml and git tags (e.g., v1.0, v1.1), NOT in class names
- Present all features as part of single cohesive release, not as "V2 features" vs "V1 features"
- In documentation, avoid version comparisons - just describe what the library does
- When evolving APIs, prefer clean renames or new packages rather than adding version suffixes to class names
- User values professional, clean project presentation without confusing dual-version artifacts

**Context:** This preference emerged after implementing all enterprise features. Rather than maintaining V1 (simple) and V2 (enhanced) classes side-by-side, user wanted single unified 1.0 release with all features included via builder configuration.
