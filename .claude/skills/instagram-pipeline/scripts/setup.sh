#!/bin/bash
# Instagram Pipeline — One-command setup
#
# Usage:
#   bash /path/to/setup.sh [--extract]
#
# Creates a .venv in the current directory and installs the socmed package.
# Pass --extract to also install Whisper + OCR dependencies (macOS only).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SOCMED_DATA_DIR:-.}/.venv"

echo "Setting up Instagram pipeline..."
echo "  Scripts: $SCRIPT_DIR"
echo "  Venv:    $VENV_DIR"
echo "  Data:    ${SOCMED_DATA_DIR:-$(pwd)}"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Upgrade pip
"$VENV_DIR/bin/pip" install --quiet --upgrade pip

# Install the bundled socmed package in editable mode
echo "Installing socmed package..."
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"

# Install extraction dependencies if requested
if [ "$1" = "--extract" ]; then
    echo "Installing extraction dependencies (Whisper + OCR)..."
    "$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements-extract.txt"
fi

# Create data directories
mkdir -p "${SOCMED_DATA_DIR:-.}/data/instagram"
mkdir -p "${SOCMED_DATA_DIR:-.}/data/media/instagram"

echo ""
echo "Setup complete!"
echo ""
echo "Quick start:"
echo "  # Sync saved posts"
echo "  SOCMED_DATA_DIR=\$(pwd) $VENV_DIR/bin/python -m socmed.platforms.instagram.api_bootstrap sync"
echo ""
echo "  # List collections"
echo "  SOCMED_DATA_DIR=\$(pwd) $VENV_DIR/bin/python -m socmed.platforms.instagram.api_bootstrap collections"
