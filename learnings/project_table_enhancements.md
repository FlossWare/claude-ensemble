---
name: project-table-enhancements
description: "Enhanced JTable with column sorting and multi-row selection capabilities"
metadata:
  type: project
  originSessionId: 94f4d6f1-3bcc-4b78-a0b9-7eca2b004c75
---

Completed 2026-05-19: Major enhancements to JTable widget with column sorting and multi-row selection.

**Why:** User requested "a table based widget that supports columns and column sorting" and "allow for multi row selection" to provide richer data presentation capabilities in the terminal UI.

**What was delivered:**

1. **Column Sorting**
   - Click column headers to cycle through sort modes: ascending → descending → unsorted
   - Visual sort indicators: `^` for ascending, `v` for descending
   - `sortByColumn(int columnIndex)` method
   - `getSortColumn()` and `getSortDirection()` getters
   - Sort constants: SORT_NONE, SORT_ASCENDING, SORT_DESCENDING
   - Preserves original data order when unsorted
   - Thread-safe sorting implementation with comparator
   - Mouse event handling for column header clicks

2. **Multi-Row Selection**
   - `setMultiSelectionEnabled(boolean)` to toggle selection mode
   - New selection methods:
     - `selectRow(int row)` - add to selection (or replace in single-select mode)
     - `deselectRow(int row)` - remove from selection
     - `toggleRowSelection(int row)` - toggle selection state
     - `clearSelection()` - clear all selections
     - `getSelectedRows()` - returns Set<Integer> of selected rows
     - `isRowSelected(int row)` - check if row is selected
   - Visual selection markers:
     - Multi-select mode: `[*]` for selected, `[ ]` for unselected
     - Single-select mode: `>` for selected, ` ` for unselected
   - Mouse click support for row selection

3. **Additional Improvements**
   - `setColumnWidth(int width)` / `getColumnWidth()` for configurable column sizing
   - `getRowCount()` to get table row count
   - `getColumnNames()` to retrieve column names list
   - Backward compatibility: deprecated `setSelectedRow()` and `getSelectedRow()` still work
   - Enhanced paint() method with proper formatting for selections and sort indicators
   - Mouse event handling dispatches header clicks vs row clicks appropriately

4. **Testing**
   - Added 23 new comprehensive unit tests (total: 26, up from 3)
   - Test coverage includes:
     - Column sorting (ascending, descending, reset)
     - Multi-row and single-row selection
     - Selection toggling and clearing
     - Mouse event handling (header clicks, row clicks)
     - Column width configuration
     - Backward compatibility with deprecated methods
     - Edge cases (invalid row/column indices)
   - All 367 tests passing (up from 344)

5. **InteractiveDemo Enhancement**
   - Added "Show Table Demo" button
   - Opens table frame with 7 sample rows, 5 columns
   - Demonstrates:
     - Column sorting by clicking headers
     - Multi-row selection with checkbox indicators
     - Sort direction indicators (^/v)
   - Includes helpful instruction label

6. **Documentation**
   - Updated README.md version: 1.14 → 1.15
   - Updated test counts: 344 → 367 tests
   - Updated JTable description to mention column sorting and multi-row selection

**Implementation Details:**
- Original data preserved in `originalData` list for unsorted state restoration
- Selected rows tracked in `Set<Integer>` for efficient lookup
- Sort state tracked with `sortColumn` (int) and `sortDirection` (int constant)
- Mouse events at y=0 trigger column header sorting
- Mouse events at y>=2 (after header + separator) trigger row selection
- Column width defaults to 15, minimum enforced at 5

**Test Coverage:**
- Total tests: 367 (up from 344, added 23 new tests)
- JTableTest: 26 tests covering all new functionality
- All tests passing

**Git Commits:**
- commit 1a7a997 (rebased to 805604f): "feat: enhance JTable with column sorting and multi-row selection"
- Pushed to GitHub main branch 2026-05-19

**How to apply:** 
- Column sorting provides familiar spreadsheet-like interaction for data tables
- Multi-row selection enables batch operations on table data
- Backward compatible - existing code using JTable continues to work
- Interactive demo shows best practices for using enhanced table features
