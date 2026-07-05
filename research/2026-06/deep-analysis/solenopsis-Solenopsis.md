# Deep Code Analysis: Solenopsis

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/Solenopsis

## 1. Repository Structure

```
.
├── ant
│   ├── 1.1
│   │   ├── lib
│   │   ├── properties
│   │   ├── templates
│   │   ├── util
│   │   ├── solenopsis-build.xml
│   │   └── solenopsis-setup.xml
│   ├── 1.2
│   │   ├── lib
│   │   ├── salesforce-util.xml
│   │   ├── setup-antcontrib.xml
│   │   ├── setup-salesforce.xml
│   │   ├── setup-solenopsis.xml
│   │   ├── solenopsis-build.xml
│   │   ├── solenopsis-util.xml
│   │   └── util.xml
│   ├── lib
│   │   └── 1.9.6
│   └── solenopsis.xml
├── bsh
│   └── Foo.bsh
├── config
│   ├── apex.vim
│   └── defaults.cfg
├── docs
│   ├── Apache-LICENSE-1.1
│   ├── Apache-LICENSE-2.0
│   ├── Eclipse-Distribution-LICENSE-v1.0
│   ├── lgpl-LICENSE
│   ├── LICENSE
│   ├── MOZILLA-PUBLIC-LICENSE-Version-1.0
│   └── README
├── mindmap
│   └── to-do.mm
├── scripts
│   ├── lib
│   │   ├── ant.py
│   │   ├── create.py
│   │   ├── environment.py
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   ├── osutils.py
│   │   └── parser.py
│   ├── selenium
│   │   ├── set_profile_permissions.py
│   │   └── utils.py
│   ├── templates
│   │   ├── class.template
│   │   ├── class-test.template
│   │   ├── class-trigger.template
│   │   ├── class.xml
│   │   ├── component.xml
│   │   ├── page.template
│   │   ├── page.xml
│   │   ├── trigger.template
│   │   ├── trigger.xml
│   │   └── webservice.template
│   ├── bsolenopsis
│   ├── solenopsis
│   ├── solenopsis-completion.bash
│   └── solenopsis-profile.sh
├── test
│   └── ant
│       ├── 1.1
│       └── 1.2
├── xsl
│   ├── objects
│   │   ├── ActionOverride
│   │   ├── BusinessProcess
│   │   ├── CustomField
│   │   ├── ListView
│   │   ├── NamedFilter
│   │   ├── object2csv.xsl
│   │   ├── object2properties.xsl
│   │   ├── objects2ddl.xsl
│   │   ├── RecordType
│   │   ├── ValidationRule
│   │   └── WebLink
│   ├── templates
│   │   └── sfdcignore-template.xsl
│   └── workflows
│       ├── WorkflowAlert
│       ├── WorkflowFieldUpdate
│       └── WorkflowRule
├── buildrpm.sh
├── CODE_OF_CONDUCT.md
├── install.sh
├── LICENSE.md
├── Makefile
├── README.md
├── solenopsis-main-analysis.md
├── solenopsis.spec
├── SUPPORT.md
└── uninstall.sh

27 directories, 69 files
```

**File Statistics:**
- Total files: 124
- Java files: 0
- XML files: 24
- Python files: 9
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**

**Key Packages/Modules:**

**Design Patterns Detected:**
- Pattern usage: 0 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 0

**Documentation:**
- README.md (40 lines)
- docs/ directory exists
- Javadoc annotations: 0

**Code Metrics:**

## 4. Key Files Deep Dive

### README.md
```markdown
# Solenopsis

Solenopsis is a tool born out of necessity. With no good command-line tool to deploy Salesforce code with it was written to meet a need. Solenopsis is a combination of some ANT scripts to do deployment and Python scripts to do easily manage flags and other neat things like templates.

Right now, all testing and development has been focused on Linux. But patches are welcome to make it truely multi-platform.

![Build Status](https://flossware.no-ip.org:58080/buildStatus/icon?job=Solenopsis-Ant&style=plastic)

## Dependencies
+ Python
+ Ant
+ Python Beatbox (optional)

## Libraries
These are the libraries used in Solenopsis.  Just a list for them being awesome (and some legal reasons too).

### Ant
+ [ant](https://ant.apache.org/index.html/)
+ [ant-contrib](https://ant-contrib.sourceforge.net/)
+ [ant-unit](https://ant.apache.org/antlibs/antunit/)
+ [beanshell](https://www.beanshell.org/manual/bsf.html) 
+ [ivy](https://ant.apache.org/ivy/)
+ [JGit](https://www.eclipse.org/jgit)

_Licenses and additional information can be found in the docs directory._

### Python
+ [beatbox](https://code.google.com/p/salesforce-beatbox/) (optional)

## Getting Started
...
```

### Top 5 Largest Source Files
- ./scripts/lib/environment.py (431 lines)
- ./scripts/selenium/set_profile_permissions.py (268 lines)
- ./scripts/lib/create.py (252 lines)
- ./scripts/lib/ant.py (239 lines)
- ./scripts/selenium/utils.py (85 lines)

---
**Analysis Complete**
