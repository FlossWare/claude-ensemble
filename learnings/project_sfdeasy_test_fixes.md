---
name: project-sfdeasy-test-fixes
description: "Test failures fixed in May 2026 - import errors, missing methods, BETWEEN syntax"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

**Test failures encountered and resolved (2026-05-16):**

**Issue 1: Wrong Field class imported in tests**
- Tests imported `com.redhat.gss.sfdeasy.scala.model.Field` (just holds name/type)
- Should import `com.redhat.gss.sfdeasy.query.fields.Field` (has valueOf() factory methods)
- Fixed in: SelectQueryTest, ConditionTest, FilterTest, FieldTest
- Symptom: Compilation errors about missing valueOf() methods

**Issue 2: Missing Apex factory methods**
- RedHatPortEnum.APEX existed but RedHatPortFactory.createApexPort() methods were missing
- Caused testEnumAndFactoryAlignment to fail (expected 44 methods, found 42)
- Fixed by adding createApexPort(SessionContext) and createApexPort(Credentials)
- Pattern: Every enum entry needs 2 factory methods (one for each parameter type)

**Issue 3: BetweenCondition not using BETWEEN keyword**
- Original: `(field >= value1 AND field <= value2)`
- Fixed: `(field BETWEEN value1 AND value2)`
- Makes SOQL more idiomatic and matches test expectations

**Why:** These fixes were needed because initial test implementation had:
1. Copy-paste error in imports (wrong Field class)
2. Incomplete factory coverage (APEX enum added but factory methods forgotten)
3. Non-idiomatic SOQL generation (functional but not using BETWEEN keyword)

**How to apply:** When adding new enum entries to RedHatPortEnum, always add both factory method variants to RedHatPortFactory. When writing tests for query builders, verify imports use `query.fields.Field` not `scala.model.Field`.
