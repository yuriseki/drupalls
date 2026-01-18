#!/bin/bash
# Setup script for bundled Phpactor CLI

set -e

echo "Setting up Phpactor CLI dependency..."

# Check if composer is available
if ! command -v composer &> /dev/null; then
    echo "ERROR: Composer is required to set up Phpactor"
    echo "Please install Composer: https://getcomposer.org/"
    exit 1
fi

# Navigate to phpactor directory
cd "$(dirname "$0")/../phpactor"

# Install PHP dependencies if not already installed
if [ ! -d "vendor" ]; then
    echo "Installing Phpactor PHP dependencies..."
    composer install --no-dev --optimize-autoloader
else
    echo "Phpactor dependencies already installed"
fi

# Make sure phpactor binary is executable
if [ -f "bin/phpactor" ]; then
    chmod +x bin/phpactor
    echo "✓ Phpactor CLI ready at: $(pwd)/bin/phpactor"
else
    echo "ERROR: Phpactor binary not found"
    exit 1
fi

echo "✓ Phpactor setup complete"
