---
name: reference-packagecloud
description: Solenopsis artifacts are published to packagecloud.io/sfloess/solenopsis Maven repository
metadata: 
  node_type: memory
  type: reference
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

Solenopsis project artifacts are published to packagecloud.io under the sfloess account.

**Maven Repository URL:**
`https://packagecloud.io/sfloess/solenopsis/maven2/`

**Deployment Configuration (pom.xml):**
```xml
<distributionManagement>
    <repository>
        <id>packagecloud-sfloess</id>
        <url>https://packagecloud.io/sfloess/solenopsis/maven2/</url>
    </repository>
</distributionManagement>
```

**Authentication:**
Requires packagecloud token in `~/.m2/settings.xml`:
```xml
<server>
    <id>packagecloud-sfloess</id>
    <password>YOUR_PACKAGECLOUD_TOKEN</password>
</server>
```

**Deploy Command:**
```bash
mvn deploy
```

**Consumer Configuration:**
Users add this repository to their `pom.xml` or `~/.m2/settings.xml` to consume Solenopsis artifacts.

**Reference Projects:**
User mentioned "FlossWare jcollections" as an example of how artifacts should be published to packagecloud.io.
