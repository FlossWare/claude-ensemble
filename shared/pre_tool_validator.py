#!/usr/bin/env python3
"""
Pre-Tool Validation Framework
Validates tool parameters before execution with schema validation, permission checks, and dry-run mode
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import jsonschema
from jsonschema import validate, ValidationError


class PreToolValidator:
    """Validates tool calls before execution"""

    # JSON schemas for common tools
    TOOL_SCHEMAS = {
        'Bash': {
            'type': 'object',
            'properties': {
                'command': {'type': 'string', 'minLength': 1},
                'timeout': {'type': 'number', 'minimum': 0, 'maximum': 600000},
                'run_in_background': {'type': 'boolean'}
            },
            'required': ['command']
        },
        'Read': {
            'type': 'object',
            'properties': {
                'file_path': {'type': 'string', 'minLength': 1},
                'offset': {'type': 'integer', 'minimum': 0},
                'limit': {'type': 'integer', 'minimum': 1}
            },
            'required': ['file_path']
        },
        'Write': {
            'type': 'object',
            'properties': {
                'file_path': {'type': 'string', 'minLength': 1},
                'content': {'type': 'string'}
            },
            'required': ['file_path', 'content']
        },
        'Edit': {
            'type': 'object',
            'properties': {
                'file_path': {'type': 'string', 'minLength': 1},
                'old_string': {'type': 'string', 'minLength': 1},
                'new_string': {'type': 'string'},
                'replace_all': {'type': 'boolean'}
            },
            'required': ['file_path', 'old_string', 'new_string']
        }
    }

    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        'rm -rf /',
        'dd if=/dev/zero',
        'mkfs.',
        ':(){:|:&};:',  # Fork bomb
        'chmod -R 777 /',
        'chown -R'
    ]

    # Protected paths
    PROTECTED_PATHS = [
        '/etc/passwd',
        '/etc/shadow',
        '/etc/sudoers',
        '/boot',
        '/sys',
        '/proc'
    ]

    def __init__(self, dry_run: bool = False, permission_check: bool = True):
        """
        Initialize validator

        Args:
            dry_run: If True, only validate without executing
            permission_check: If True, check file permissions
        """
        self.dry_run = dry_run
        self.permission_check = permission_check
        self.validation_errors = []

    def validate(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tool call parameters

        Args:
            tool_name: Name of the tool (e.g., 'Bash', 'Read', 'Write')
            parameters: Tool parameters to validate

        Returns:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'dry_run': bool
            }
        """
        self.validation_errors = []
        warnings = []

        # Schema validation
        if tool_name in self.TOOL_SCHEMAS:
            try:
                validate(instance=parameters, schema=self.TOOL_SCHEMAS[tool_name])
            except ValidationError as e:
                self.validation_errors.append(f"Schema validation failed: {e.message}")

        # Tool-specific validation
        if tool_name == 'Bash':
            bash_warnings = self._validate_bash(parameters)
            warnings.extend(bash_warnings)
        elif tool_name == 'Read':
            read_warnings = self._validate_read(parameters)
            warnings.extend(read_warnings)
        elif tool_name == 'Write':
            write_warnings = self._validate_write(parameters)
            warnings.extend(write_warnings)
        elif tool_name == 'Edit':
            edit_warnings = self._validate_edit(parameters)
            warnings.extend(edit_warnings)

        return {
            'valid': len(self.validation_errors) == 0,
            'errors': self.validation_errors,
            'warnings': warnings,
            'dry_run': self.dry_run
        }

    def _validate_bash(self, params: Dict[str, Any]) -> List[str]:
        """Validate Bash command"""
        warnings = []
        command = params.get('command', '')

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in command:
                self.validation_errors.append(
                    f"Dangerous command pattern detected: {pattern}"
                )

        # Warn about destructive operations
        if any(x in command for x in ['rm -rf', 'dd', 'mkfs']):
            warnings.append("Destructive operation detected - proceed with caution")

        # Warn about sudo
        if 'sudo' in command and not params.get('timeout'):
            warnings.append("sudo command without timeout - may hang if password required")

        return warnings

    def _validate_read(self, params: Dict[str, Any]) -> List[str]:
        """Validate Read operation"""
        warnings = []
        file_path = params.get('file_path', '')

        # Check if file exists
        if self.permission_check and file_path:
            path = Path(file_path).expanduser()
            if not path.exists():
                warnings.append(f"File does not exist: {file_path}")
            elif not os.access(path, os.R_OK):
                self.validation_errors.append(f"No read permission for: {file_path}")

        # Warn about large files
        if file_path and Path(file_path).expanduser().exists():
            size_mb = Path(file_path).expanduser().stat().st_size / (1024 * 1024)
            if size_mb > 10:
                warnings.append(f"Large file ({size_mb:.1f}MB) - consider using offset/limit")

        return warnings

    def _validate_write(self, params: Dict[str, Any]) -> List[str]:
        """Validate Write operation"""
        warnings = []
        file_path = params.get('file_path', '')

        # Check protected paths
        for protected in self.PROTECTED_PATHS:
            if file_path.startswith(protected):
                self.validation_errors.append(
                    f"Cannot write to protected path: {file_path}"
                )

        # Check parent directory exists
        if self.permission_check and file_path:
            parent = Path(file_path).expanduser().parent
            if not parent.exists():
                self.validation_errors.append(
                    f"Parent directory does not exist: {parent}"
                )
            elif not os.access(parent, os.W_OK):
                self.validation_errors.append(
                    f"No write permission for directory: {parent}"
                )

        # Warn about overwriting existing files
        if file_path and Path(file_path).expanduser().exists():
            warnings.append(f"Will overwrite existing file: {file_path}")

        return warnings

    def _validate_edit(self, params: Dict[str, Any]) -> List[str]:
        """Validate Edit operation"""
        warnings = []
        file_path = params.get('file_path', '')
        old_string = params.get('old_string', '')

        # Check file exists and is readable
        if self.permission_check and file_path:
            path = Path(file_path).expanduser()
            if not path.exists():
                self.validation_errors.append(f"File does not exist: {file_path}")
            elif not os.access(path, os.R_OK | os.W_OK):
                self.validation_errors.append(
                    f"No read/write permission for: {file_path}"
                )
            else:
                # Check if old_string exists in file
                try:
                    content = path.read_text()
                    if old_string not in content:
                        warnings.append(
                            f"String to replace not found in file (will fail)"
                        )
                except Exception as e:
                    warnings.append(f"Could not read file for validation: {e}")

        # Warn about replace_all
        if params.get('replace_all'):
            warnings.append("replace_all=True - all occurrences will be replaced")

        return warnings


# Example usage
if __name__ == "__main__":
    validator = PreToolValidator(dry_run=True, permission_check=True)

    # Example 1: Validate Bash command
    print("=== Example 1: Bash Command ===")
    result = validator.validate('Bash', {
        'command': 'ls -la /tmp',
        'timeout': 5000
    })
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
    print()

    # Example 2: Dangerous Bash command
    print("=== Example 2: Dangerous Bash Command ===")
    result = validator.validate('Bash', {
        'command': 'rm -rf / --no-preserve-root'
    })
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print()

    # Example 3: Read file
    print("=== Example 3: Read File ===")
    result = validator.validate('Read', {
        'file_path': '/etc/hosts'
    })
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
    print()

    # Example 4: Write to protected path
    print("=== Example 4: Write to Protected Path ===")
    result = validator.validate('Write', {
        'file_path': '/etc/passwd',
        'content': 'malicious content'
    })
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print()

    # Example 5: Edit file
    print("=== Example 5: Edit File ===")
    result = validator.validate('Edit', {
        'file_path': '/tmp/test.txt',
        'old_string': 'old',
        'new_string': 'new',
        'replace_all': True
    })
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")
