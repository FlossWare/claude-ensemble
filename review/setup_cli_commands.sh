#!/bin/bash
# Setup CLI commands for multi-stage reviews
# Creates symlinks for:
#   review (1 stage)
#   meta-review (2 stages)
#   meta-meta-review (3 stages)
#   meta-meta-meta-review (4+ stages)

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BIN_DIR="$SCRIPT_DIR/bin"
WRAPPER="$SCRIPT_DIR/review/cli_wrapper.sh"

# Make wrapper executable
chmod +x "$WRAPPER"

# Create bin directory
mkdir -p "$BIN_DIR"

# Make wrapper executable
chmod +x "$WRAPPER"

# Create symlinks
echo "Creating CLI command symlinks..."

# Function to create symlink
create_link() {
  local name="$1"
  local link_path="$BIN_DIR/$name"

  if [ -L "$link_path" ] || [ -f "$link_path" ]; then
    rm -f "$link_path"
  fi

  ln -s "$WRAPPER" "$link_path"
  echo "  ✓ $name"
}

# Create base command
create_link "review"

# Create meta- prefixed commands (up to 5 levels)
for i in {1..5}; do
  # Build the meta- prefix
  prefix=""
  for ((j=0; j<i; j++)); do
    prefix="${prefix}meta-"
  done

  cmd_name="${prefix}review"
  create_link "$cmd_name"
done

echo ""
echo "✓ CLI commands created in $BIN_DIR"
echo ""
echo "Usage:"
echo "  $BIN_DIR/review artifact"
echo "  $BIN_DIR/meta-review artifact"
echo "  $BIN_DIR/meta-meta-review artifact"
echo "  etc."
echo ""
echo "To add to PATH:"
echo "  export PATH=\"$BIN_DIR:\$PATH\""
