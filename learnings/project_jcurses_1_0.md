---
name: project-jcurses-1-0
description: "jcurses is a Java 21 terminal UI library with AWT-like components using ncurses, completed version 1.0 with all planned features"
metadata: 
  node_type: memory
  type: project
  originSessionId: 94f4d6f1-3bcc-4b78-a0b9-7eca2b004c75
---

jcurses is complete and in production (May 2026).

**Why:** User requested completion of all "In Progress" and "Planned" features from the README. This was a comprehensive implementation project that took the library from initial prototype to production-ready with full test coverage.

**Key Facts:**
- Maven artifactId: `org.flossware:jcurses` (changed from jcurses-awt)
- Project name: "jcurses" (lowercase, all references to "JCurses-AWT" removed)
- Current version: 1.5 (X.Y format, not semantic X.Y.Z, auto-incremented by CI/CD)
- 56 source files: 28 widgets + 9 support classes + infrastructure (added DraggableWindow, WindowDragManager)
- 312 unit tests across 42 test classes (0 failures, deleted JFrameDragTest)
- 80%+ code coverage with JaCoCo
- CI/CD pipeline: Fully operational with Node.js 24 support (see [[project-cicd-pipeline]])
- Window drag/resize: NOT WORKING - implementation broke event dispatch, removed to restore clicking (see [[project-window-drag-in-progress]])
- Cross-platform scripts: Linux/macOS (.sh), Windows batch (.bat), and PowerShell (.ps1) for running demos

**Completed Features (all marked as "Working" in README):**
1. Mouse event handling - click detection and component dispatch
2. Color support - 8 standard colors with predefined color pairs
3. Advanced text editing - selection, cut/copy/paste, undo/redo, word navigation
4. Scrolling in JScrollPane - viewport clipping and scrollbar integration
5. Performance optimization - dirty rectangles, layout caching
6. Module system - opt-in JPMS support with module-info.java.template
7. Theme system - Default, Dark, Light themes with pluggable architecture

**Technology Stack:**
- Java 21 with preview features (Virtual Threads, Foreign Function API, Record Patterns, Sealed Interfaces)
- ncurses integration via Project Panama FFI
- ReentrantLock for thread safety (not synchronized - avoids Virtual Thread carrier pinning)
- GitHub Actions CI/CD with packagecloud.io deployment
- Maven with enforcer plugin for X.Y version format

**How to apply:** When working on jcurses, remember all features are complete and production-ready. Focus on maintenance, bug fixes, or new feature additions beyond the 1.0 scope. The project follows X.Y versioning with automated CI/CD pipeline that auto-increments version on push to main.
