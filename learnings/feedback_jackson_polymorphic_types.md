---
name: jackson-polymorphic-types
description: "XML, YAML, and MessagePack mappers need activateDefaultTyping for @JsonTypeInfo fields"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ac456e14-1126-4cac-93c3-a6202a0df585
---

When using Jackson with XML, YAML, or MessagePack formats, fields annotated with `@JsonTypeInfo(use = JsonTypeInfo.Id.CLASS)` require `activateDefaultTyping()` to be called on the ObjectMapper/XmlMapper.

**Why:** jremote's `RemoteInvocation.args` and `RemoteResponse.result` fields use `@JsonTypeInfo` for polymorphic serialization. During multi-format implementation, XML and YAML formats initially failed to deserialize these fields correctly, causing null values or type mismatches. MessagePack had it from the start and worked. Adding `activateDefaultTyping()` to XML and YAML strategies fixed the deserialization.

**How to apply:** For any Jackson-based serialization strategy (ObjectMapper, XmlMapper, etc.), if the data model contains `@JsonTypeInfo` annotations, configure the mapper with:

```java
mapper.activateDefaultTyping(
    mapper.getPolymorphicTypeValidator(),
    ObjectMapper.DefaultTyping.JAVA_LANG_OBJECT
);
```

This ensures type information is preserved during serialization and correctly restored during deserialization, which is critical for Object[] arrays and polymorphic result types.
