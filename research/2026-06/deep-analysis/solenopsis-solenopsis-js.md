# Deep Code Analysis: solenopsis-js

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/solenopsis-js

## 1. Repository Structure

```
.
├── src
│   ├── config
│   │   ├── __mocks__
│   │   ├── __tests__
│   │   └── index.js
│   ├── __mocks__
│   │   └── jsforce.js
│   ├── __tests__
│   │   └── index.test.js
│   └── index.js
├── jest.config.js
├── LICENSE
├── package.json
├── package-lock.json
└── README.md

7 directories, 9 files
```

**File Statistics:**
- Total files: 11
- Java files: 0
- XML files: 0
- Python files: 0
- JavaScript files: 7

## 2. Architecture & Code Patterns

**Build System:**
- npm/Node.js (package.json found)

**Key Packages/Modules:**
- src/__mocks__
- src/__tests__
- src/config
- src/config/__mocks__
- src/config/__tests__

**Design Patterns Detected:**
- Pattern usage: 0 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 0

**Documentation:**
- README.md (57 lines)
- Javadoc annotations: 0

**Code Metrics:**

## 4. Key Files Deep Dive

### README.md
```markdown
# solenopsis-js
[![Code Climate](https://api.codeclimate.com/v1/badges/10206747ee80ab74bdd6/maintainability)](https://codeclimate.com/github/solenopsis/solenopsis-js/maintainability)
[![Coverage Status](https://api.codeclimate.com/v1/badges/10206747ee80ab74bdd6/test_coverage)](https://codeclimate.com/github/solenopsis/solenopsis-js/test_coverage)

Javascript utility methods around Solenopsis

## Configuration
You will need to have your `environment.properties` files configured based on the standard [Solenopsis configuration](https://github.com/solenopsis/Solenopsis/wiki/1.1-Configuration#credentials-configuration) pattern.

## Usage
### Getting login credentials
Parse the `environment.properties` file and return the values inside

```
const solenopsis = require('solenopsis');

solenopsis.getCredentials('production')
    .then(function (credentials) {
        console.log(credentials.username);
    })
    .catch(console.error);
```

### Logging in to an instance
A helper method is provided to automatically create a [jsforce](https://jsforce.github.io) connection based on an environment name.

```
const solenopsis = require('solenopsis');

solenopsis.login('production')
...
```

### Top 5 Largest Source Files
- ./src/__tests__/index.test.js (91 lines)
- ./src/index.js (53 lines)
- ./src/config/__mocks__/fs.js (46 lines)
- ./src/config/__tests__/index.test.js (34 lines)
- ./src/config/index.js (26 lines)

---
**Analysis Complete**
