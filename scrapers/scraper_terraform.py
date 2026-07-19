#!/usr/bin/env python3
"""Terraform documentation scraper.

Covers:
  - Terraform language (resources, variables, modules, expressions, functions)
  - Terraform CLI (init, plan, apply, workspace, providers)
  - Terraform providers (AWS, Azure, GCP, Kubernetes, etc.)
  - Terraform Cloud and CDKTF
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class TerraformScraper(BaseScraper):
    """Scrape Terraform documentation from developer.hashicorp.com."""

    SOURCES = {
        "language": {
            "pages": {
                # ── Overview and syntax ──────────────────────────────────
                "https://developer.hashicorp.com/terraform/language": "Terraform Language Overview",
                "https://developer.hashicorp.com/terraform/language/syntax": "Syntax Overview",
                "https://developer.hashicorp.com/terraform/language/syntax/configuration": "Configuration Syntax",
                "https://developer.hashicorp.com/terraform/language/syntax/json": "JSON Configuration Syntax",
                "https://developer.hashicorp.com/terraform/language/syntax/style": "Style Conventions",
                "https://developer.hashicorp.com/terraform/language/files": "Files and Directories",
                "https://developer.hashicorp.com/terraform/language/files/override": "Override Files",
                "https://developer.hashicorp.com/terraform/language/files/dependency-lock": "Dependency Lock File",
                # ── Resources ────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/resources": "Resources Overview",
                "https://developer.hashicorp.com/terraform/language/resources/behavior": "Resource Behavior",
                "https://developer.hashicorp.com/terraform/language/resources/provisioners": "Provisioners Overview",
                "https://developer.hashicorp.com/terraform/language/resources/syntax": "Resource Syntax",
                "https://developer.hashicorp.com/terraform/language/resources/provisioners/connection": "Provisioner Connection Settings",
                "https://developer.hashicorp.com/terraform/language/resources/provisioners/file": "File Provisioner",
                "https://developer.hashicorp.com/terraform/language/resources/provisioners/local-exec": "Local-exec Provisioner",
                "https://developer.hashicorp.com/terraform/language/resources/provisioners/remote-exec": "Remote-exec Provisioner",
                # ── Data sources ─────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/data-sources": "Data Sources",
                # ── Values ───────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/values/variables": "Input Variables",
                "https://developer.hashicorp.com/terraform/language/values/outputs": "Output Values",
                "https://developer.hashicorp.com/terraform/language/values/locals": "Local Values",
                # ── Modules ──────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/modules": "Modules Overview",
                "https://developer.hashicorp.com/terraform/language/modules/develop": "Module Development",
                "https://developer.hashicorp.com/terraform/language/modules/sources": "Module Sources",
                "https://developer.hashicorp.com/terraform/language/modules/syntax": "Module Blocks",
                "https://developer.hashicorp.com/terraform/language/modules/testing-experiment": "Module Testing Experiment",
                # ── Expressions ──────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/expressions": "Expressions Overview",
                "https://developer.hashicorp.com/terraform/language/expressions/types": "Types and Values",
                "https://developer.hashicorp.com/terraform/language/expressions/strings": "Strings and Templates",
                "https://developer.hashicorp.com/terraform/language/expressions/references": "References to Values",
                "https://developer.hashicorp.com/terraform/language/expressions/operators": "Operators",
                "https://developer.hashicorp.com/terraform/language/expressions/conditionals": "Conditional Expressions",
                "https://developer.hashicorp.com/terraform/language/expressions/for": "For Expressions",
                "https://developer.hashicorp.com/terraform/language/expressions/splat": "Splat Expressions",
                "https://developer.hashicorp.com/terraform/language/expressions/dynamic-blocks": "Dynamic Blocks",
                "https://developer.hashicorp.com/terraform/language/expressions/type-constraints": "Type Constraints",
                "https://developer.hashicorp.com/terraform/language/expressions/version-constraints": "Version Constraints",
                "https://developer.hashicorp.com/terraform/language/expressions/function-calls": "Function Calls",
                "https://developer.hashicorp.com/terraform/language/expressions/custom-conditions": "Custom Conditions",
                # ── Functions: overview ──────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions": "Built-in Functions Overview",
                # ── Functions: numeric ───────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/abs": "Function: abs",
                "https://developer.hashicorp.com/terraform/language/functions/ceil": "Function: ceil",
                "https://developer.hashicorp.com/terraform/language/functions/floor": "Function: floor",
                "https://developer.hashicorp.com/terraform/language/functions/log": "Function: log",
                "https://developer.hashicorp.com/terraform/language/functions/max": "Function: max",
                "https://developer.hashicorp.com/terraform/language/functions/min": "Function: min",
                "https://developer.hashicorp.com/terraform/language/functions/parseint": "Function: parseint",
                "https://developer.hashicorp.com/terraform/language/functions/pow": "Function: pow",
                "https://developer.hashicorp.com/terraform/language/functions/signum": "Function: signum",
                # ── Functions: string ────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/chomp": "Function: chomp",
                "https://developer.hashicorp.com/terraform/language/functions/format": "Function: format",
                "https://developer.hashicorp.com/terraform/language/functions/formatlist": "Function: formatlist",
                "https://developer.hashicorp.com/terraform/language/functions/indent": "Function: indent",
                "https://developer.hashicorp.com/terraform/language/functions/join": "Function: join",
                "https://developer.hashicorp.com/terraform/language/functions/lower": "Function: lower",
                "https://developer.hashicorp.com/terraform/language/functions/regex": "Function: regex",
                "https://developer.hashicorp.com/terraform/language/functions/regexall": "Function: regexall",
                "https://developer.hashicorp.com/terraform/language/functions/replace": "Function: replace",
                "https://developer.hashicorp.com/terraform/language/functions/split": "Function: split",
                "https://developer.hashicorp.com/terraform/language/functions/startswith": "Function: startswith",
                "https://developer.hashicorp.com/terraform/language/functions/endswith": "Function: endswith",
                "https://developer.hashicorp.com/terraform/language/functions/strcontains": "Function: strcontains",
                "https://developer.hashicorp.com/terraform/language/functions/strrev": "Function: strrev",
                "https://developer.hashicorp.com/terraform/language/functions/substr": "Function: substr",
                "https://developer.hashicorp.com/terraform/language/functions/title": "Function: title",
                "https://developer.hashicorp.com/terraform/language/functions/trim": "Function: trim",
                "https://developer.hashicorp.com/terraform/language/functions/trimprefix": "Function: trimprefix",
                "https://developer.hashicorp.com/terraform/language/functions/trimsuffix": "Function: trimsuffix",
                "https://developer.hashicorp.com/terraform/language/functions/trimspace": "Function: trimspace",
                "https://developer.hashicorp.com/terraform/language/functions/upper": "Function: upper",
                # ── Functions: collection ────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/alltrue": "Function: alltrue",
                "https://developer.hashicorp.com/terraform/language/functions/anytrue": "Function: anytrue",
                "https://developer.hashicorp.com/terraform/language/functions/chunklist": "Function: chunklist",
                "https://developer.hashicorp.com/terraform/language/functions/coalesce": "Function: coalesce",
                "https://developer.hashicorp.com/terraform/language/functions/coalescelist": "Function: coalescelist",
                "https://developer.hashicorp.com/terraform/language/functions/compact": "Function: compact",
                "https://developer.hashicorp.com/terraform/language/functions/concat": "Function: concat",
                "https://developer.hashicorp.com/terraform/language/functions/contains": "Function: contains",
                "https://developer.hashicorp.com/terraform/language/functions/distinct": "Function: distinct",
                "https://developer.hashicorp.com/terraform/language/functions/element": "Function: element",
                "https://developer.hashicorp.com/terraform/language/functions/flatten": "Function: flatten",
                "https://developer.hashicorp.com/terraform/language/functions/index": "Function: index",
                "https://developer.hashicorp.com/terraform/language/functions/keys": "Function: keys",
                "https://developer.hashicorp.com/terraform/language/functions/length": "Function: length",
                "https://developer.hashicorp.com/terraform/language/functions/list": "Function: list",
                "https://developer.hashicorp.com/terraform/language/functions/lookup": "Function: lookup",
                "https://developer.hashicorp.com/terraform/language/functions/map": "Function: map",
                "https://developer.hashicorp.com/terraform/language/functions/matchkeys": "Function: matchkeys",
                "https://developer.hashicorp.com/terraform/language/functions/merge": "Function: merge",
                "https://developer.hashicorp.com/terraform/language/functions/one": "Function: one",
                "https://developer.hashicorp.com/terraform/language/functions/range": "Function: range",
                "https://developer.hashicorp.com/terraform/language/functions/reverse": "Function: reverse",
                "https://developer.hashicorp.com/terraform/language/functions/setintersection": "Function: setintersection",
                "https://developer.hashicorp.com/terraform/language/functions/setproduct": "Function: setproduct",
                "https://developer.hashicorp.com/terraform/language/functions/setsubtract": "Function: setsubtract",
                "https://developer.hashicorp.com/terraform/language/functions/setunion": "Function: setunion",
                "https://developer.hashicorp.com/terraform/language/functions/slice": "Function: slice",
                "https://developer.hashicorp.com/terraform/language/functions/sort": "Function: sort",
                "https://developer.hashicorp.com/terraform/language/functions/sum": "Function: sum",
                "https://developer.hashicorp.com/terraform/language/functions/transpose": "Function: transpose",
                "https://developer.hashicorp.com/terraform/language/functions/values": "Function: values",
                "https://developer.hashicorp.com/terraform/language/functions/zipmap": "Function: zipmap",
                # ── Functions: encoding ──────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/base64decode": "Function: base64decode",
                "https://developer.hashicorp.com/terraform/language/functions/base64encode": "Function: base64encode",
                "https://developer.hashicorp.com/terraform/language/functions/base64gzip": "Function: base64gzip",
                "https://developer.hashicorp.com/terraform/language/functions/csvdecode": "Function: csvdecode",
                "https://developer.hashicorp.com/terraform/language/functions/jsondecode": "Function: jsondecode",
                "https://developer.hashicorp.com/terraform/language/functions/jsonencode": "Function: jsonencode",
                "https://developer.hashicorp.com/terraform/language/functions/textdecodebase64": "Function: textdecodebase64",
                "https://developer.hashicorp.com/terraform/language/functions/textencodebase64": "Function: textencodebase64",
                "https://developer.hashicorp.com/terraform/language/functions/urlencode": "Function: urlencode",
                "https://developer.hashicorp.com/terraform/language/functions/yamldecode": "Function: yamldecode",
                "https://developer.hashicorp.com/terraform/language/functions/yamlencode": "Function: yamlencode",
                # ── Functions: filesystem ────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/abspath": "Function: abspath",
                "https://developer.hashicorp.com/terraform/language/functions/dirname": "Function: dirname",
                "https://developer.hashicorp.com/terraform/language/functions/pathexpand": "Function: pathexpand",
                "https://developer.hashicorp.com/terraform/language/functions/basename": "Function: basename",
                "https://developer.hashicorp.com/terraform/language/functions/file": "Function: file",
                "https://developer.hashicorp.com/terraform/language/functions/fileexists": "Function: fileexists",
                "https://developer.hashicorp.com/terraform/language/functions/fileset": "Function: fileset",
                "https://developer.hashicorp.com/terraform/language/functions/filebase64": "Function: filebase64",
                "https://developer.hashicorp.com/terraform/language/functions/templatefile": "Function: templatefile",
                # ── Functions: date and time ─────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/formatdate": "Function: formatdate",
                "https://developer.hashicorp.com/terraform/language/functions/plantimestamp": "Function: plantimestamp",
                "https://developer.hashicorp.com/terraform/language/functions/timeadd": "Function: timeadd",
                "https://developer.hashicorp.com/terraform/language/functions/timecmp": "Function: timecmp",
                "https://developer.hashicorp.com/terraform/language/functions/timestamp": "Function: timestamp",
                # ── Functions: hash and crypto ───────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/base64sha256": "Function: base64sha256",
                "https://developer.hashicorp.com/terraform/language/functions/base64sha512": "Function: base64sha512",
                "https://developer.hashicorp.com/terraform/language/functions/bcrypt": "Function: bcrypt",
                "https://developer.hashicorp.com/terraform/language/functions/filebase64sha256": "Function: filebase64sha256",
                "https://developer.hashicorp.com/terraform/language/functions/filebase64sha512": "Function: filebase64sha512",
                "https://developer.hashicorp.com/terraform/language/functions/filemd5": "Function: filemd5",
                "https://developer.hashicorp.com/terraform/language/functions/filesha1": "Function: filesha1",
                "https://developer.hashicorp.com/terraform/language/functions/filesha256": "Function: filesha256",
                "https://developer.hashicorp.com/terraform/language/functions/filesha512": "Function: filesha512",
                "https://developer.hashicorp.com/terraform/language/functions/md5": "Function: md5",
                "https://developer.hashicorp.com/terraform/language/functions/rsadecrypt": "Function: rsadecrypt",
                "https://developer.hashicorp.com/terraform/language/functions/sha1": "Function: sha1",
                "https://developer.hashicorp.com/terraform/language/functions/sha256": "Function: sha256",
                "https://developer.hashicorp.com/terraform/language/functions/sha512": "Function: sha512",
                "https://developer.hashicorp.com/terraform/language/functions/uuid": "Function: uuid",
                "https://developer.hashicorp.com/terraform/language/functions/uuidv5": "Function: uuidv5",
                # ── Functions: IP network ────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/cidrhost": "Function: cidrhost",
                "https://developer.hashicorp.com/terraform/language/functions/cidrnetmask": "Function: cidrnetmask",
                "https://developer.hashicorp.com/terraform/language/functions/cidrsubnet": "Function: cidrsubnet",
                "https://developer.hashicorp.com/terraform/language/functions/cidrsubnets": "Function: cidrsubnets",
                # ── Functions: type conversion ───────────────────────────
                "https://developer.hashicorp.com/terraform/language/functions/can": "Function: can",
                "https://developer.hashicorp.com/terraform/language/functions/issensitive": "Function: issensitive",
                "https://developer.hashicorp.com/terraform/language/functions/nonsensitive": "Function: nonsensitive",
                "https://developer.hashicorp.com/terraform/language/functions/sensitive": "Function: sensitive",
                "https://developer.hashicorp.com/terraform/language/functions/tobool": "Function: tobool",
                "https://developer.hashicorp.com/terraform/language/functions/tolist": "Function: tolist",
                "https://developer.hashicorp.com/terraform/language/functions/tomap": "Function: tomap",
                "https://developer.hashicorp.com/terraform/language/functions/tonumber": "Function: tonumber",
                "https://developer.hashicorp.com/terraform/language/functions/toset": "Function: toset",
                "https://developer.hashicorp.com/terraform/language/functions/tostring": "Function: tostring",
                "https://developer.hashicorp.com/terraform/language/functions/try": "Function: try",
                "https://developer.hashicorp.com/terraform/language/functions/type": "Function: type",
                # ── State ────────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/state": "State Overview",
                "https://developer.hashicorp.com/terraform/language/state/backends": "State Backends",
                "https://developer.hashicorp.com/terraform/language/state/locking": "State Locking",
                "https://developer.hashicorp.com/terraform/language/state/import": "Importing State",
                "https://developer.hashicorp.com/terraform/language/state/remote": "Remote State",
                "https://developer.hashicorp.com/terraform/language/state/purpose": "Purpose of State",
                "https://developer.hashicorp.com/terraform/language/state/sensitive-data": "Sensitive Data in State",
                "https://developer.hashicorp.com/terraform/language/state/workspaces": "State Workspaces",
                # ── Settings and backends ────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/settings": "Terraform Settings",
                "https://developer.hashicorp.com/terraform/language/settings/backends": "Backend Configuration",
                "https://developer.hashicorp.com/terraform/language/settings/backends/local": "Backend: local",
                "https://developer.hashicorp.com/terraform/language/settings/backends/remote": "Backend: remote",
                "https://developer.hashicorp.com/terraform/language/settings/backends/s3": "Backend: s3",
                "https://developer.hashicorp.com/terraform/language/settings/backends/azurerm": "Backend: azurerm",
                "https://developer.hashicorp.com/terraform/language/settings/backends/gcs": "Backend: gcs",
                "https://developer.hashicorp.com/terraform/language/settings/backends/consul": "Backend: consul",
                "https://developer.hashicorp.com/terraform/language/settings/backends/cos": "Backend: cos",
                "https://developer.hashicorp.com/terraform/language/settings/backends/http": "Backend: http",
                "https://developer.hashicorp.com/terraform/language/settings/backends/kubernetes": "Backend: kubernetes",
                "https://developer.hashicorp.com/terraform/language/settings/backends/oss": "Backend: oss",
                "https://developer.hashicorp.com/terraform/language/settings/backends/pg": "Backend: pg",
                # ── Providers (language) ─────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/providers": "Providers Overview",
                "https://developer.hashicorp.com/terraform/language/providers/configuration": "Provider Configuration",
                "https://developer.hashicorp.com/terraform/language/providers/requirements": "Provider Requirements",
                "https://developer.hashicorp.com/terraform/language/providers/meta": "Provider Meta-Argument",
                # ── Meta-arguments ───────────────────────────────────────
                "https://developer.hashicorp.com/terraform/language/meta-arguments/count": "Meta-Argument: count",
                "https://developer.hashicorp.com/terraform/language/meta-arguments/depends_on": "Meta-Argument: depends_on",
                "https://developer.hashicorp.com/terraform/language/meta-arguments/for_each": "Meta-Argument: for_each",
                "https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle": "Meta-Argument: lifecycle",
                "https://developer.hashicorp.com/terraform/language/meta-arguments/providers": "Meta-Argument: providers",
                # ── Additional language features ─────────────────────────
                "https://developer.hashicorp.com/terraform/language/import": "Import",
                "https://developer.hashicorp.com/terraform/language/moved": "Moved Blocks",
                "https://developer.hashicorp.com/terraform/language/checks": "Checks",
                "https://developer.hashicorp.com/terraform/language/tests": "Tests",
                "https://developer.hashicorp.com/terraform/language/tests/mocking": "Test Mocking",
                "https://developer.hashicorp.com/terraform/language/attr-as-blocks": "Attributes as Blocks",
                "https://developer.hashicorp.com/terraform/language/v1-compatibility-promises": "v1 Compatibility Promises",
                "https://developer.hashicorp.com/terraform/language/terraform": "Terraform Block",
                "https://developer.hashicorp.com/terraform/language/upgrade-guides": "Upgrade Guides",
                "https://developer.hashicorp.com/terraform/language/stacks": "Stacks Overview",
                "https://developer.hashicorp.com/terraform/language/stacks/deploy": "Stack Deployments",
                "https://developer.hashicorp.com/terraform/language/stacks/config": "Stack Configuration",
            },
        },
        "cli": {
            "pages": {
                # ── Overview ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli": "Terraform CLI Overview",
                "https://developer.hashicorp.com/terraform/cli/commands": "CLI Commands Overview",
                "https://developer.hashicorp.com/terraform/cli/install": "Install Terraform",
                # ── Main commands ────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/init": "Command: init",
                "https://developer.hashicorp.com/terraform/cli/plan": "Command: plan",
                "https://developer.hashicorp.com/terraform/cli/apply": "Command: apply",
                "https://developer.hashicorp.com/terraform/cli/destroy": "Command: destroy",
                "https://developer.hashicorp.com/terraform/cli/validate": "Command: validate",
                "https://developer.hashicorp.com/terraform/cli/fmt": "Command: fmt",
                "https://developer.hashicorp.com/terraform/cli/show": "Command: show",
                "https://developer.hashicorp.com/terraform/cli/output": "Command: output",
                "https://developer.hashicorp.com/terraform/cli/taint": "Command: taint",
                "https://developer.hashicorp.com/terraform/cli/untaint": "Command: untaint",
                "https://developer.hashicorp.com/terraform/cli/import": "Command: import",
                "https://developer.hashicorp.com/terraform/cli/refresh": "Command: refresh",
                "https://developer.hashicorp.com/terraform/cli/graph": "Command: graph",
                "https://developer.hashicorp.com/terraform/cli/console": "Command: console",
                "https://developer.hashicorp.com/terraform/cli/force-unlock": "Command: force-unlock",
                "https://developer.hashicorp.com/terraform/cli/login": "Command: login",
                "https://developer.hashicorp.com/terraform/cli/logout": "Command: logout",
                "https://developer.hashicorp.com/terraform/cli/test": "Command: test",
                "https://developer.hashicorp.com/terraform/cli/version": "Command: version",
                "https://developer.hashicorp.com/terraform/cli/get": "Command: get",
                "https://developer.hashicorp.com/terraform/cli/push": "Command: push",
                # ── Workspace commands ───────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/workspace": "Command: workspace",
                "https://developer.hashicorp.com/terraform/cli/workspace/list": "Command: workspace list",
                "https://developer.hashicorp.com/terraform/cli/workspace/new": "Command: workspace new",
                "https://developer.hashicorp.com/terraform/cli/workspace/select": "Command: workspace select",
                "https://developer.hashicorp.com/terraform/cli/workspace/show": "Command: workspace show",
                "https://developer.hashicorp.com/terraform/cli/workspace/delete": "Command: workspace delete",
                # ── State commands ───────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/state": "Command: state",
                "https://developer.hashicorp.com/terraform/cli/state/list": "Command: state list",
                "https://developer.hashicorp.com/terraform/cli/state/show": "Command: state show",
                "https://developer.hashicorp.com/terraform/cli/state/mv": "Command: state mv",
                "https://developer.hashicorp.com/terraform/cli/state/rm": "Command: state rm",
                "https://developer.hashicorp.com/terraform/cli/state/pull": "Command: state pull",
                "https://developer.hashicorp.com/terraform/cli/state/push": "Command: state push",
                "https://developer.hashicorp.com/terraform/cli/state/replace-provider": "Command: state replace-provider",
                # ── Provider commands ────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/providers": "Command: providers",
                "https://developer.hashicorp.com/terraform/cli/providers/lock": "Command: providers lock",
                "https://developer.hashicorp.com/terraform/cli/providers/mirror": "Command: providers mirror",
                "https://developer.hashicorp.com/terraform/cli/providers/schema": "Command: providers schema",
                # ── Cloud integration ────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/cloud": "HCP Terraform CLI Integration",
                "https://developer.hashicorp.com/terraform/cli/cloud/settings": "Cloud CLI Settings",
                "https://developer.hashicorp.com/terraform/cli/cloud/command-line-arguments": "Cloud Command-Line Arguments",
                # ── Metadata commands ────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/metadata": "Command: metadata",
                "https://developer.hashicorp.com/terraform/cli/metadata/functions": "Command: metadata functions",
                # ── Configuration ────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/environment-variables": "Environment Variables",
                "https://developer.hashicorp.com/terraform/cli/config/config-file": "CLI Configuration File",
                "https://developer.hashicorp.com/terraform/cli/config/environment-variables": "CLI Environment Variables",
                # ── Internals ────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/internals": "CLI Internals",
                "https://developer.hashicorp.com/terraform/cli/internals/credentials": "Credentials Helpers",
                "https://developer.hashicorp.com/terraform/cli/internals/debugging": "Debugging Terraform",
                "https://developer.hashicorp.com/terraform/cli/internals/json-format": "JSON Output Format",
                "https://developer.hashicorp.com/terraform/cli/internals/machine-readable-ui": "Machine-Readable Output",
                "https://developer.hashicorp.com/terraform/cli/internals/provider-network-mirror-protocol": "Provider Network Mirror Protocol",
                "https://developer.hashicorp.com/terraform/cli/internals/provider-registry-protocol": "Provider Registry Protocol",
                "https://developer.hashicorp.com/terraform/cli/internals/dependency-lock-file": "Dependency Lock File Internals",
                "https://developer.hashicorp.com/terraform/cli/internals/login-protocol": "Login Protocol",
                # ── Upgrade commands ─────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/0.12upgrade": "Command: 0.12upgrade",
                "https://developer.hashicorp.com/terraform/cli/0.13upgrade": "Command: 0.13upgrade",
                # ── Auth ─────────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cli/auth": "CLI Authentication",
            },
        },
        "providers": {
            "pages": {
                # ══════════════════════════════════════════════════════════
                # AWS PROVIDER
                # ══════════════════════════════════════════════════════════
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs": "AWS Provider Overview",
                # ── AWS resources: compute ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/instance": "AWS: aws_instance",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/launch_template": "AWS: aws_launch_template",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/autoscaling_group": "AWS: aws_autoscaling_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/placement_group": "AWS: aws_placement_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/spot_instance_request": "AWS: aws_spot_instance_request",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/key_pair": "AWS: aws_key_pair",
                # ── AWS resources: networking ─────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc": "AWS: aws_vpc",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet": "AWS: aws_subnet",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group": "AWS: aws_security_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/security_group_rule": "AWS: aws_security_group_rule",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_security_group": "AWS: aws_default_security_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_vpc": "AWS: aws_default_vpc",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eip": "AWS: aws_eip",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/nat_gateway": "AWS: aws_nat_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/internet_gateway": "AWS: aws_internet_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table": "AWS: aws_route_table",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route": "AWS: aws_route",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route_table_association": "AWS: aws_route_table_association",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/main_route_table_association": "AWS: aws_main_route_table_association",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/network_interface": "AWS: aws_network_interface",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/network_acl": "AWS: aws_network_acl",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_peering_connection": "AWS: aws_vpc_peering_connection",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpn_gateway": "AWS: aws_vpn_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/customer_gateway": "AWS: aws_customer_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpn_connection": "AWS: aws_vpn_connection",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/flow_log": "AWS: aws_flow_log",
                # ── AWS resources: S3 ────────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket": "AWS: aws_s3_bucket",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy": "AWS: aws_s3_bucket_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning": "AWS: aws_s3_bucket_versioning",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_lifecycle_configuration": "AWS: aws_s3_bucket_lifecycle_configuration",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object": "AWS: aws_s3_object",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block": "AWS: aws_s3_bucket_public_access_block",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration": "AWS: aws_s3_bucket_server_side_encryption_configuration",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_cors_configuration": "AWS: aws_s3_bucket_cors_configuration",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_notification": "AWS: aws_s3_bucket_notification",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_acl": "AWS: aws_s3_bucket_acl",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_logging": "AWS: aws_s3_bucket_logging",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_website_configuration": "AWS: aws_s3_bucket_website_configuration",
                # ── AWS resources: IAM ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role": "AWS: aws_iam_role",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_policy": "AWS: aws_iam_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment": "AWS: aws_iam_role_policy_attachment",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_user": "AWS: aws_iam_user",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_group": "AWS: aws_iam_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_instance_profile": "AWS: aws_iam_instance_profile",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_access_key": "AWS: aws_iam_access_key",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy": "AWS: aws_iam_role_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_user_policy": "AWS: aws_iam_user_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_group_membership": "AWS: aws_iam_group_membership",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_group_policy": "AWS: aws_iam_group_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_openid_connect_provider": "AWS: aws_iam_openid_connect_provider",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_saml_provider": "AWS: aws_iam_saml_provider",
                # ── AWS resources: Lambda ────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function": "AWS: aws_lambda_function",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_permission": "AWS: aws_lambda_permission",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_event_source_mapping": "AWS: aws_lambda_event_source_mapping",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_layer_version": "AWS: aws_lambda_layer_version",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_alias": "AWS: aws_lambda_alias",
                # ── AWS resources: API Gateway ───────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_rest_api": "AWS: aws_api_gateway_rest_api",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_resource": "AWS: aws_api_gateway_resource",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_method": "AWS: aws_api_gateway_method",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apigatewayv2_api": "AWS: aws_apigatewayv2_api",
                # ── AWS resources: DynamoDB ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/dynamodb_table": "AWS: aws_dynamodb_table",
                # ── AWS resources: RDS ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/rds_cluster": "AWS: aws_rds_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_instance": "AWS: aws_db_instance",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_subnet_group": "AWS: aws_db_subnet_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_parameter_group": "AWS: aws_db_parameter_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/db_option_group": "AWS: aws_db_option_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/rds_cluster_instance": "AWS: aws_rds_cluster_instance",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/rds_cluster_parameter_group": "AWS: aws_rds_cluster_parameter_group",
                # ── AWS resources: ECS ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_cluster": "AWS: aws_ecs_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_service": "AWS: aws_ecs_service",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_task_definition": "AWS: aws_ecs_task_definition",
                # ── AWS resources: EKS ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_cluster": "AWS: aws_eks_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/eks_node_group": "AWS: aws_eks_node_group",
                # ── AWS resources: load balancing ────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb": "AWS: aws_lb",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group": "AWS: aws_lb_target_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener": "AWS: aws_lb_listener",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_listener_rule": "AWS: aws_lb_listener_rule",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lb_target_group_attachment": "AWS: aws_lb_target_group_attachment",
                # ── AWS resources: Route 53 ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_zone": "AWS: aws_route53_zone",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/route53_record": "AWS: aws_route53_record",
                # ── AWS resources: CloudFront ────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudfront_distribution": "AWS: aws_cloudfront_distribution",
                # ── AWS resources: CloudWatch ────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group": "AWS: aws_cloudwatch_log_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm": "AWS: aws_cloudwatch_metric_alarm",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_dashboard": "AWS: aws_cloudwatch_dashboard",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_rule": "AWS: aws_cloudwatch_event_rule",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_event_target": "AWS: aws_cloudwatch_event_target",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_subscription_filter": "AWS: aws_cloudwatch_log_subscription_filter",
                # ── AWS resources: messaging ─────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic": "AWS: aws_sns_topic",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription": "AWS: aws_sns_topic_subscription",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue": "AWS: aws_sqs_queue",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sqs_queue_policy": "AWS: aws_sqs_queue_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kinesis_stream": "AWS: aws_kinesis_stream",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kinesis_firehose_delivery_stream": "AWS: aws_kinesis_firehose_delivery_stream",
                # ── AWS resources: caching ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_cluster": "AWS: aws_elasticache_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_replication_group": "AWS: aws_elasticache_replication_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_subnet_group": "AWS: aws_elasticache_subnet_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_parameter_group": "AWS: aws_elasticache_parameter_group",
                # ── AWS resources: ECR ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository": "AWS: aws_ecr_repository",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_lifecycle_policy": "AWS: aws_ecr_lifecycle_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecr_repository_policy": "AWS: aws_ecr_repository_policy",
                # ── AWS resources: KMS and secrets ───────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kms_key": "AWS: aws_kms_key",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret": "AWS: aws_secretsmanager_secret",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret_version": "AWS: aws_secretsmanager_secret_version",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_parameter": "AWS: aws_ssm_parameter",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_document": "AWS: aws_ssm_document",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_association": "AWS: aws_ssm_association",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ssm_maintenance_window": "AWS: aws_ssm_maintenance_window",
                # ── AWS resources: EBS and storage ───────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ebs_volume": "AWS: aws_ebs_volume",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_file_system": "AWS: aws_efs_file_system",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_mount_target": "AWS: aws_efs_mount_target",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/efs_access_point": "AWS: aws_efs_access_point",
                # ── AWS resources: certificates ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/acm_certificate": "AWS: aws_acm_certificate",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/acm_certificate_validation": "AWS: aws_acm_certificate_validation",
                # ── AWS resources: WAF ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_web_acl": "AWS: aws_wafv2_web_acl",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_ip_set": "AWS: aws_wafv2_ip_set",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/wafv2_rule_group": "AWS: aws_wafv2_rule_group",
                # ── AWS resources: CI/CD ─────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codebuild_project": "AWS: aws_codebuild_project",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codepipeline": "AWS: aws_codepipeline",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codecommit_repository": "AWS: aws_codecommit_repository",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codestar_connections_connection": "AWS: aws_codestar_connections_connection",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codedeploy_app": "AWS: aws_codedeploy_app",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/codedeploy_deployment_group": "AWS: aws_codedeploy_deployment_group",
                # ── AWS resources: search and analytics ──────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticsearch_domain": "AWS: aws_elasticsearch_domain",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/opensearch_domain": "AWS: aws_opensearch_domain",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/msk_cluster": "AWS: aws_msk_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/kinesis_stream": "AWS: aws_kinesis_stream (resource)",
                # ── AWS resources: Step Functions ────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sfn_state_machine": "AWS: aws_sfn_state_machine",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sfn_activity": "AWS: aws_sfn_activity",
                # ── AWS resources: data analytics ────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/glue_catalog_database": "AWS: aws_glue_catalog_database",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/glue_catalog_table": "AWS: aws_glue_catalog_table",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/glue_job": "AWS: aws_glue_job",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/glue_crawler": "AWS: aws_glue_crawler",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/athena_database": "AWS: aws_athena_database",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/redshift_cluster": "AWS: aws_redshift_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/emr_cluster": "AWS: aws_emr_cluster",
                # ── AWS resources: ML ────────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sagemaker_endpoint": "AWS: aws_sagemaker_endpoint",
                # ── AWS resources: Cognito ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool": "AWS: aws_cognito_user_pool",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_user_pool_client": "AWS: aws_cognito_user_pool_client",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cognito_identity_pool": "AWS: aws_cognito_identity_pool",
                # ── AWS resources: SES ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ses_domain_identity": "AWS: aws_ses_domain_identity",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ses_configuration_set": "AWS: aws_ses_configuration_set",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ses_receipt_rule_set": "AWS: aws_ses_receipt_rule_set",
                # ── AWS resources: Organizations ─────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/organizations_organization": "AWS: aws_organizations_organization",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/organizations_account": "AWS: aws_organizations_account",
                # ── AWS resources: security and compliance ────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/config_rule": "AWS: aws_config_rule",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/guardduty_detector": "AWS: aws_guardduty_detector",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/inspector2_enabler": "AWS: aws_inspector2_enabler",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/macie2_account": "AWS: aws_macie2_account",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudtrail": "AWS: aws_cloudtrail",
                # ── AWS resources: Transfer ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/transfer_server": "AWS: aws_transfer_server",
                # ── AWS resources: batch ─────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_compute_environment": "AWS: aws_batch_compute_environment",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_job_definition": "AWS: aws_batch_job_definition",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/batch_job_queue": "AWS: aws_batch_job_queue",
                # ── AWS resources: CloudFormation ────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack": "AWS: aws_cloudformation_stack",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudformation_stack_set": "AWS: aws_cloudformation_stack_set",
                # ── AWS resources: Backup ────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/backup_plan": "AWS: aws_backup_plan",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/backup_vault": "AWS: aws_backup_vault",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/backup_selection": "AWS: aws_backup_selection",
                # ── AWS resources: cost ──────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/budgets_budget": "AWS: aws_budgets_budget",
                # ── AWS resources: auto scaling ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appautoscaling_target": "AWS: aws_appautoscaling_target",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appautoscaling_policy": "AWS: aws_appautoscaling_policy",
                # ── AWS resources: misc ──────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appsync_graphql_api": "AWS: aws_appsync_graphql_api",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/amplify_app": "AWS: aws_amplify_app",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iot_thing": "AWS: aws_iot_thing",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iot_policy": "AWS: aws_iot_policy",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/pinpoint_app": "AWS: aws_pinpoint_app",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/service_discovery_service": "AWS: aws_service_discovery_service",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/service_discovery_private_dns_namespace": "AWS: aws_service_discovery_private_dns_namespace",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloud9_environment_ec2": "AWS: aws_cloud9_environment_ec2",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elastic_beanstalk_application": "AWS: aws_elastic_beanstalk_application",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elastic_beanstalk_environment": "AWS: aws_elastic_beanstalk_environment",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/media_store_container": "AWS: aws_media_store_container",
                # ── AWS data sources ─────────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ami": "AWS Data: aws_ami",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/availability_zones": "AWS Data: aws_availability_zones",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity": "AWS Data: aws_caller_identity",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document": "AWS Data: aws_iam_policy_document",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region": "AWS Data: aws_region",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/vpc": "AWS Data: aws_vpc",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnet": "AWS Data: aws_subnet",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/subnets": "AWS Data: aws_subnets",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/security_group": "AWS Data: aws_security_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/s3_bucket": "AWS Data: aws_s3_bucket",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_role": "AWS Data: aws_iam_role",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/partition": "AWS Data: aws_partition",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/eks_cluster": "AWS Data: aws_eks_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ssm_parameter": "AWS Data: aws_ssm_parameter",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/secretsmanager_secret": "AWS Data: aws_secretsmanager_secret",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route53_zone": "AWS Data: aws_route53_zone",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/lb": "AWS Data: aws_lb",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/acm_certificate": "AWS Data: aws_acm_certificate",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/kms_key": "AWS Data: aws_kms_key",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ebs_volume": "AWS Data: aws_ebs_volume",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/instances": "AWS Data: aws_instances",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/nat_gateway": "AWS Data: aws_nat_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/internet_gateway": "AWS Data: aws_internet_gateway",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/route_table": "AWS Data: aws_route_table",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/network_interface": "AWS Data: aws_network_interface",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ecs_cluster": "AWS Data: aws_ecs_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/rds_cluster": "AWS Data: aws_rds_cluster",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/lambda_function": "AWS Data: aws_lambda_function",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/cloudfront_distribution": "AWS Data: aws_cloudfront_distribution",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/elb": "AWS Data: aws_elb",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/db_instance": "AWS Data: aws_db_instance",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/autoscaling_group": "AWS Data: aws_autoscaling_group",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/launch_template": "AWS Data: aws_launch_template",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/organizations_organization": "AWS Data: aws_organizations_organization",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/ecr_repository": "AWS Data: aws_ecr_repository",
                "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/efs_file_system": "AWS Data: aws_efs_file_system",
                # ══════════════════════════════════════════════════════════
                # AZURE PROVIDER
                # ══════════════════════════════════════════════════════════
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs": "Azure Provider Overview",
                # ── Azure resources: core ────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/resource_group": "Azure: azurerm_resource_group",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/role_assignment": "Azure: azurerm_role_assignment",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/user_assigned_identity": "Azure: azurerm_user_assigned_identity",
                # ── Azure resources: networking ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/virtual_network": "Azure: azurerm_virtual_network",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/subnet": "Azure: azurerm_subnet",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/network_security_group": "Azure: azurerm_network_security_group",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/network_interface": "Azure: azurerm_network_interface",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/public_ip": "Azure: azurerm_public_ip",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/lb": "Azure: azurerm_lb",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/application_gateway": "Azure: azurerm_application_gateway",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/dns_zone": "Azure: azurerm_dns_zone",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/private_dns_zone": "Azure: azurerm_private_dns_zone",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/traffic_manager_profile": "Azure: azurerm_traffic_manager_profile",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/firewall": "Azure: azurerm_firewall",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/bastion_host": "Azure: azurerm_bastion_host",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/private_endpoint": "Azure: azurerm_private_endpoint",
                # ── Azure resources: compute ─────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/virtual_machine": "Azure: azurerm_virtual_machine",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_virtual_machine": "Azure: azurerm_linux_virtual_machine",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/windows_virtual_machine": "Azure: azurerm_windows_virtual_machine",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/managed_disk": "Azure: azurerm_managed_disk",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/availability_set": "Azure: azurerm_availability_set",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/virtual_machine_scale_set": "Azure: azurerm_virtual_machine_scale_set",
                # ── Azure resources: storage ─────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account": "Azure: azurerm_storage_account",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_container": "Azure: azurerm_storage_container",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_blob": "Azure: azurerm_storage_blob",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_queue": "Azure: azurerm_storage_queue",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_table": "Azure: azurerm_storage_table",
                # ── Azure resources: Key Vault ───────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault": "Azure: azurerm_key_vault",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault_secret": "Azure: azurerm_key_vault_secret",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault_key": "Azure: azurerm_key_vault_key",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault_certificate": "Azure: azurerm_key_vault_certificate",
                # ── Azure resources: Kubernetes ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/kubernetes_cluster": "Azure: azurerm_kubernetes_cluster",
                # ── Azure resources: app services ────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/app_service_plan": "Azure: azurerm_app_service_plan",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_web_app": "Azure: azurerm_linux_web_app",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/function_app": "Azure: azurerm_function_app",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/app_configuration": "Azure: azurerm_app_configuration",
                # ── Azure resources: databases ───────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cosmosdb_account": "Azure: azurerm_cosmosdb_account",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/sql_server": "Azure: azurerm_sql_server",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/mssql_server": "Azure: azurerm_mssql_server",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/mssql_database": "Azure: azurerm_mssql_database",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/postgresql_flexible_server": "Azure: azurerm_postgresql_flexible_server",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/redis_cache": "Azure: azurerm_redis_cache",
                # ── Azure resources: containers ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_registry": "Azure: azurerm_container_registry",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_group": "Azure: azurerm_container_group",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app": "Azure: azurerm_container_app",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/container_app_environment": "Azure: azurerm_container_app_environment",
                # ── Azure resources: monitoring ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/log_analytics_workspace": "Azure: azurerm_log_analytics_workspace",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/monitor_metric_alert": "Azure: azurerm_monitor_metric_alert",
                # ── Azure resources: messaging ───────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/eventhub_namespace": "Azure: azurerm_eventhub_namespace",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_namespace": "Azure: azurerm_servicebus_namespace",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/notification_hub": "Azure: azurerm_notification_hub",
                # ── Azure resources: AI and CDN ──────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cognitive_account": "Azure: azurerm_cognitive_account",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/search_service": "Azure: azurerm_search_service",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cdn_profile": "Azure: azurerm_cdn_profile",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cdn_endpoint": "Azure: azurerm_cdn_endpoint",
                # ── Azure resources: integration ─────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/api_management": "Azure: azurerm_api_management",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/data_factory": "Azure: azurerm_data_factory",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/databricks_workspace": "Azure: azurerm_databricks_workspace",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/logic_app_workflow": "Azure: azurerm_logic_app_workflow",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/signalr_service": "Azure: azurerm_signalr_service",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/spring_cloud_service": "Azure: azurerm_spring_cloud_service",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/bot_service_azure_bot": "Azure: azurerm_bot_service_azure_bot",
                # ── Azure data sources ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/resource_group": "Azure Data: azurerm_resource_group",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/virtual_network": "Azure Data: azurerm_virtual_network",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/subnet": "Azure Data: azurerm_subnet",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/client_config": "Azure Data: azurerm_client_config",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/subscription": "Azure Data: azurerm_subscription",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/key_vault": "Azure Data: azurerm_key_vault",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/key_vault_secret": "Azure Data: azurerm_key_vault_secret",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/kubernetes_cluster": "Azure Data: azurerm_kubernetes_cluster",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/storage_account": "Azure Data: azurerm_storage_account",
                "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/data-sources/container_registry": "Azure Data: azurerm_container_registry",
                # ══════════════════════════════════════════════════════════
                # GCP PROVIDER
                # ══════════════════════════════════════════════════════════
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs": "GCP Provider Overview",
                # ── GCP resources: compute ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance": "GCP: google_compute_instance",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network": "GCP: google_compute_network",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_subnetwork": "GCP: google_compute_subnetwork",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_firewall": "GCP: google_compute_firewall",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_disk": "GCP: google_compute_disk",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_address": "GCP: google_compute_address",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_router": "GCP: google_compute_router",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_router_nat": "GCP: google_compute_router_nat",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_health_check": "GCP: google_compute_health_check",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_backend_service": "GCP: google_compute_backend_service",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_url_map": "GCP: google_compute_url_map",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_target_https_proxy": "GCP: google_compute_target_https_proxy",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_global_forwarding_rule": "GCP: google_compute_global_forwarding_rule",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_ssl_certificate": "GCP: google_compute_ssl_certificate",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance_template": "GCP: google_compute_instance_template",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_instance_group_manager": "GCP: google_compute_instance_group_manager",
                # ── GCP resources: storage ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/storage_bucket": "GCP: google_storage_bucket",
                # ── GCP resources: GKE ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_cluster": "GCP: google_container_cluster",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/container_node_pool": "GCP: google_container_node_pool",
                # ── GCP resources: IAM ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_iam_member": "GCP: google_project_iam_member",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_account": "GCP: google_service_account",
                # ── GCP resources: serverless ────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_service": "GCP: google_cloud_run_service",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloudfunctions_function": "GCP: google_cloudfunctions_function",
                # ── GCP resources: BigQuery ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/bigquery_dataset": "GCP: google_bigquery_dataset",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/bigquery_table": "GCP: google_bigquery_table",
                # ── GCP resources: SQL ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance": "GCP: google_sql_database_instance",
                # ── GCP resources: Pub/Sub ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_topic": "GCP: google_pubsub_topic",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription": "GCP: google_pubsub_subscription",
                # ── GCP resources: DNS ───────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dns_managed_zone": "GCP: google_dns_managed_zone",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dns_record_set": "GCP: google_dns_record_set",
                # ── GCP resources: security ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/kms_key_ring": "GCP: google_kms_key_ring",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/kms_crypto_key": "GCP: google_kms_crypto_key",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret": "GCP: google_secret_manager_secret",
                # ── GCP resources: Artifact Registry ─────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/artifact_registry_repository": "GCP: google_artifact_registry_repository",
                # ── GCP resources: monitoring ────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/monitoring_alert_policy": "GCP: google_monitoring_alert_policy",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/logging_metric": "GCP: google_logging_metric",
                # ── GCP resources: caching ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/redis_instance": "GCP: google_redis_instance",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/memcache_instance": "GCP: google_memcache_instance",
                # ── GCP resources: data ──────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataflow_job": "GCP: google_dataflow_job",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataproc_cluster": "GCP: google_dataproc_cluster",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/composer_environment": "GCP: google_composer_environment",
                # ── GCP resources: VPC access ────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/vpc_access_connector": "GCP: google_vpc_access_connector",
                # ── GCP resources: project ───────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project": "GCP: google_project",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/project_service": "GCP: google_project_service",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/folder": "GCP: google_folder",
                # ── GCP data sources ─────────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_instance": "GCP Data: google_compute_instance",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_network": "GCP Data: google_compute_network",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_subnetwork": "GCP Data: google_compute_subnetwork",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/project": "GCP Data: google_project",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/service_account": "GCP Data: google_service_account",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/container_cluster": "GCP Data: google_container_cluster",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_zones": "GCP Data: google_compute_zones",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/compute_image": "GCP Data: google_compute_image",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/client_config": "GCP Data: google_client_config",
                "https://registry.terraform.io/providers/hashicorp/google/latest/docs/data-sources/storage_bucket": "GCP Data: google_storage_bucket",
                # ══════════════════════════════════════════════════════════
                # KUBERNETES PROVIDER
                # ══════════════════════════════════════════════════════════
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs": "Kubernetes Provider Overview",
                # ── Kubernetes resources ─────────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/deployment": "K8s: kubernetes_deployment",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/service": "K8s: kubernetes_service",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/namespace": "K8s: kubernetes_namespace",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/config_map": "K8s: kubernetes_config_map",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/secret": "K8s: kubernetes_secret",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/ingress": "K8s: kubernetes_ingress",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/pod": "K8s: kubernetes_pod",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/persistent_volume_claim": "K8s: kubernetes_persistent_volume_claim",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/storage_class": "K8s: kubernetes_storage_class",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/service_account": "K8s: kubernetes_service_account",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/role": "K8s: kubernetes_role",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/role_binding": "K8s: kubernetes_role_binding",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/cluster_role": "K8s: kubernetes_cluster_role",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/cluster_role_binding": "K8s: kubernetes_cluster_role_binding",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/horizontal_pod_autoscaler": "K8s: kubernetes_horizontal_pod_autoscaler",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/network_policy": "K8s: kubernetes_network_policy",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/stateful_set": "K8s: kubernetes_stateful_set",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/daemon_set": "K8s: kubernetes_daemon_set",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/job": "K8s: kubernetes_job",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/cron_job": "K8s: kubernetes_cron_job",
                # ── Kubernetes data sources ──────────────────────────────
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/data-sources/service": "K8s Data: kubernetes_service",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/data-sources/namespace": "K8s Data: kubernetes_namespace",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/data-sources/secret": "K8s Data: kubernetes_secret",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/data-sources/config_map": "K8s Data: kubernetes_config_map",
                "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/data-sources/all_namespaces": "K8s Data: kubernetes_all_namespaces",
                # ══════════════════════════════════════════════════════════
                # OTHER PROVIDER OVERVIEWS
                # ══════════════════════════════════════════════════════════
                "https://registry.terraform.io/providers/hashicorp/docker/latest/docs": "Provider: Docker",
                "https://registry.terraform.io/providers/hashicorp/helm/latest/docs": "Provider: Helm",
                "https://registry.terraform.io/providers/hashicorp/github/latest/docs": "Provider: GitHub",
                "https://registry.terraform.io/providers/hashicorp/datadog/latest/docs": "Provider: Datadog",
                "https://registry.terraform.io/providers/hashicorp/cloudflare/latest/docs": "Provider: Cloudflare",
                "https://registry.terraform.io/providers/hashicorp/pagerduty/latest/docs": "Provider: PagerDuty",
                "https://registry.terraform.io/providers/hashicorp/vault/latest/docs": "Provider: Vault",
                "https://registry.terraform.io/providers/hashicorp/consul/latest/docs": "Provider: Consul",
                "https://registry.terraform.io/providers/hashicorp/nomad/latest/docs": "Provider: Nomad",
                "https://registry.terraform.io/providers/hashicorp/boundary/latest/docs": "Provider: Boundary",
                "https://registry.terraform.io/providers/hashicorp/waypoint/latest/docs": "Provider: Waypoint",
                "https://registry.terraform.io/providers/hashicorp/random/latest/docs": "Provider: Random",
                "https://registry.terraform.io/providers/hashicorp/null/latest/docs": "Provider: Null",
                "https://registry.terraform.io/providers/hashicorp/local/latest/docs": "Provider: Local",
                "https://registry.terraform.io/providers/hashicorp/tls/latest/docs": "Provider: TLS",
                "https://registry.terraform.io/providers/hashicorp/http/latest/docs": "Provider: HTTP",
                "https://registry.terraform.io/providers/hashicorp/external/latest/docs": "Provider: External",
                "https://registry.terraform.io/providers/hashicorp/archive/latest/docs": "Provider: Archive",
                "https://registry.terraform.io/providers/hashicorp/template/latest/docs": "Provider: Template",
                "https://registry.terraform.io/providers/hashicorp/time/latest/docs": "Provider: Time",
            },
        },
        "cdktf": {
            "pages": {
                # ── Overview ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf": "CDKTF Overview",
                "https://developer.hashicorp.com/terraform/cdktf/architecture": "CDKTF Architecture",
                # ── Concepts ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/concepts": "CDKTF Concepts",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/stacks": "CDKTF Stacks",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/constructs": "CDKTF Constructs",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/providers": "CDKTF Providers",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/resources": "CDKTF Resources",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/data-sources": "CDKTF Data Sources",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/variables-and-outputs": "CDKTF Variables and Outputs",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/remote-backends": "CDKTF Remote Backends",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/aspects": "CDKTF Aspects",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/tokens": "CDKTF Tokens",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/iterators": "CDKTF Iterators",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/functions": "CDKTF Functions",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/hcl-interoperability": "CDKTF HCL Interoperability",
                "https://developer.hashicorp.com/terraform/cdktf/concepts/modules": "CDKTF Modules",
                # ── CLI reference ────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/commands": "CDKTF CLI Commands",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/init": "CDKTF CLI: init",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/synth": "CDKTF CLI: synth",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/deploy": "CDKTF CLI: deploy",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/destroy": "CDKTF CLI: destroy",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/diff": "CDKTF CLI: diff",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/convert": "CDKTF CLI: convert",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/get": "CDKTF CLI: get",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/login": "CDKTF CLI: login",
                "https://developer.hashicorp.com/terraform/cdktf/cli-reference/output": "CDKTF CLI: output",
                # ── Create and deploy ────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/project-setup": "CDKTF Project Setup",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/configuration-file": "CDKTF Configuration File",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/best-practices": "CDKTF Best Practices",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/environment-variables": "CDKTF Environment Variables",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/connect-to-hcp-terraform": "CDKTF Connect to HCP Terraform",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/aws": "CDKTF Deploy to AWS",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/azure": "CDKTF Deploy to Azure",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/gcp": "CDKTF Deploy to GCP",
                "https://developer.hashicorp.com/terraform/cdktf/create-and-deploy/docker": "CDKTF Deploy with Docker",
                # ── Project types ────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/project-types": "CDKTF Project Types",
                "https://developer.hashicorp.com/terraform/cdktf/project-types/typescript": "CDKTF with TypeScript",
                "https://developer.hashicorp.com/terraform/cdktf/project-types/python": "CDKTF with Python",
                "https://developer.hashicorp.com/terraform/cdktf/project-types/java": "CDKTF with Java",
                "https://developer.hashicorp.com/terraform/cdktf/project-types/csharp": "CDKTF with C#",
                "https://developer.hashicorp.com/terraform/cdktf/project-types/go": "CDKTF with Go",
                # ── Testing ──────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/test": "CDKTF Testing",
                "https://developer.hashicorp.com/terraform/cdktf/test/unit-tests": "CDKTF Unit Tests",
                "https://developer.hashicorp.com/terraform/cdktf/test/integration-tests": "CDKTF Integration Tests",
                # ── Examples ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/examples": "CDKTF Examples",
                "https://developer.hashicorp.com/terraform/cdktf/examples/aws": "CDKTF Examples: AWS",
                "https://developer.hashicorp.com/terraform/cdktf/examples/azure": "CDKTF Examples: Azure",
                "https://developer.hashicorp.com/terraform/cdktf/examples/gcp": "CDKTF Examples: GCP",
                # ── Releases ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cdktf/release": "CDKTF Releases",
                "https://developer.hashicorp.com/terraform/cdktf/release/upgrade-guide-v0-18": "CDKTF Upgrade Guide v0.18",
                "https://developer.hashicorp.com/terraform/cdktf/release/upgrade-guide-v0-19": "CDKTF Upgrade Guide v0.19",
                "https://developer.hashicorp.com/terraform/cdktf/release/upgrade-guide-v0-20": "CDKTF Upgrade Guide v0.20",
            },
        },
        "cloud": {
            "pages": {
                # ── Overview ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs": "HCP Terraform Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/overview": "HCP Terraform Getting Started",
                "https://developer.hashicorp.com/terraform/cloud-docs/migrate": "Migrate to HCP Terraform",
                # ── Workspaces ───────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces": "Workspaces Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/creating": "Creating Workspaces",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/settings": "Workspace Settings",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/variables": "Workspace Variables",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/state": "Workspace State",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/explorer": "Workspace Explorer",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/dynamic-provider-credentials": "Dynamic Provider Credentials",
                "https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health": "Workspace Health",
                # ── Runs ─────────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/run": "Runs Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/ui": "Runs: UI",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/cli": "Runs: CLI-Driven",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/api": "Runs: API-Driven",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/states": "Run States",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/install-software": "Install Software in Run Environment",
                "https://developer.hashicorp.com/terraform/cloud-docs/run/manage": "Managing Runs",
                # ── VCS ──────────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/vcs": "VCS Integration Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/vcs/github": "VCS: GitHub",
                "https://developer.hashicorp.com/terraform/cloud-docs/vcs/gitlab": "VCS: GitLab",
                "https://developer.hashicorp.com/terraform/cloud-docs/vcs/bitbucket": "VCS: Bitbucket",
                "https://developer.hashicorp.com/terraform/cloud-docs/vcs/azure-devops": "VCS: Azure DevOps",
                # ── Policy enforcement ───────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement": "Policy Enforcement Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement/sentinel": "Policy: Sentinel",
                "https://developer.hashicorp.com/terraform/cloud-docs/policy-enforcement/opa": "Policy: OPA",
                # ── Registry ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/registry": "Registry Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/registry/publish-modules": "Publishing Modules",
                "https://developer.hashicorp.com/terraform/cloud-docs/registry/publish-providers": "Publishing Providers",
                "https://developer.hashicorp.com/terraform/cloud-docs/private-registry": "Private Registry",
                "https://developer.hashicorp.com/terraform/cloud-docs/private-registry/publish": "Private Registry: Publishing",
                # ── Users, teams, organizations ──────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations": "Users, Teams, and Organizations",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/users": "User Accounts",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/teams": "Teams",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/organizations": "Organizations",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/permissions": "Permissions",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/single-sign-on": "Single Sign-On",
                "https://developer.hashicorp.com/terraform/cloud-docs/users-teams-organizations/api-tokens": "API Tokens",
                # ── Agents ───────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/agents": "Cloud Agents",
                "https://developer.hashicorp.com/terraform/cloud-docs/agents/agent-pools": "Agent Pools",
                # ── Sentinel ─────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/sentinel": "Sentinel Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/sentinel/import": "Sentinel Imports",
                "https://developer.hashicorp.com/terraform/cloud-docs/sentinel/manage-policies": "Managing Sentinel Policies",
                # ── Cost estimation ──────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/cost-estimation": "Cost Estimation Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/cost-estimation/aws": "Cost Estimation: AWS",
                "https://developer.hashicorp.com/terraform/cloud-docs/cost-estimation/azure": "Cost Estimation: Azure",
                "https://developer.hashicorp.com/terraform/cloud-docs/cost-estimation/gcp": "Cost Estimation: GCP",
                # ── Notifications ────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/notifications": "Notifications Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/notifications/email": "Notifications: Email",
                "https://developer.hashicorp.com/terraform/cloud-docs/notifications/slack": "Notifications: Slack",
                "https://developer.hashicorp.com/terraform/cloud-docs/notifications/webhooks": "Notifications: Webhooks",
                # ── Architecture ─────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/architectural-details/data-security": "Data Security",
                "https://developer.hashicorp.com/terraform/cloud-docs/architectural-details/ip-ranges": "IP Ranges",
                # ── API ──────────────────────────────────────────────────
                "https://developer.hashicorp.com/terraform/cloud-docs/api": "API Overview",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/account": "API: Account",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/admin": "API: Admin",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/applies": "API: Applies",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/audit-trails": "API: Audit Trails",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/comments": "API: Comments",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/configuration-versions": "API: Configuration Versions",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/cost-estimates": "API: Cost Estimates",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/ip-ranges": "API: IP Ranges",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/notification-configurations": "API: Notification Configurations",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/oauth-clients": "API: OAuth Clients",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/oauth-tokens": "API: OAuth Tokens",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/organization-memberships": "API: Organization Memberships",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/plan-exports": "API: Plan Exports",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/plans": "API: Plans",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/policies": "API: Policies",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/policy-checks": "API: Policy Checks",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/projects": "API: Projects",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/registry-modules": "API: Registry Modules",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/registry-providers": "API: Registry Providers",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/run": "API: Runs",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/run-tasks": "API: Run Tasks",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/run-triggers": "API: Run Triggers",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/ssh-keys": "API: SSH Keys",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/state-versions": "API: State Versions",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/team-access": "API: Team Access",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/team-members": "API: Team Members",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/variables": "API: Variables",
                "https://developer.hashicorp.com/terraform/cloud-docs/api/workspaces": "API: Workspaces",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"terraform-{source_key}" if source_key else "terraform"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' | Terraform', ' - Terraform', ' | HashiCorp Developer', ' | Terraform | HashiCorp Developer']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})
        for url, title in pages.items():
            if not self.running:
                break
            item_id = self.make_id(url)
            content = self.fetch_url(url)
            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)
                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"terraform-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(1.5)
        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(f"Unknown source key: {self.source_key}. Available: {list(self.SOURCES.keys())}")
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping terraform/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    TerraformScraper(base, source_key).run()
