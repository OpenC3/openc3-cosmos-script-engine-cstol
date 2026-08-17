# Justfile for common development tasks

# List available commands
default:
    @just --list

# Build COSMOS gem plugin (requires Ruby and rake)
# If no VERSION is provided, pulls from pyproject.toml
build-gem VERSION="":
    #!/usr/bin/env bash
    if ! command -v rake &> /dev/null; then
        echo "Error: rake not found. Please install Ruby and rake first."
        exit 1
    fi
    VERSION="{{VERSION}}"
    if [ -z "$VERSION" ]; then
        VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
    fi
    echo "Building COSMOS gem plugin version $VERSION..."
    rake build VERSION=$VERSION
    echo "Gem built successfully!"
    ls -lh *.gem 2>/dev/null || echo "No gem file found"
    for gem in *.gem; do
        [ -e "$gem" ] || continue
        echo "SHA256 ($gem):"
        shasum -a 256 "$gem"
    done

# Build COSMOS gem with auto-generated dev version (timestamp)
# Pulls base version from pyproject.toml
build-gem-dev:
    #!/usr/bin/env bash
    if ! command -v rake &> /dev/null; then
        echo "Error: rake not found. Please install Ruby and rake first."
        exit 1
    fi
    BASE_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
    VERSION="${BASE_VERSION}-dev.$(date +%Y%m%d%H%M%S)"
    echo "Building COSMOS gem plugin version $VERSION..."
    rake build VERSION=$VERSION
    echo "Development gem built successfully!"
    ls -lh *.gem 2>/dev/null || echo "No gem file found"
    for gem in *.gem; do
        [ -e "$gem" ] || continue
        echo "SHA256 ($gem):"
        shasum -a 256 "$gem"
    done

# Install python dependencies
install:
    uv sync

# Install python with dev dependencies
install-dev:
    uv sync --group dev

# Run all python tests
test:
    uv run --group dev pytest test/ -v

# Run python tests with coverage
test-cov:
    uv run --group dev pytest test/ -v --cov=lib --cov-report=term-missing

# Run specific python test file
test-file FILE:
    uv run --group dev pytest {{FILE}} -v

# Check python code with ruff
lint:
    uv run --group dev ruff check .

# Fix python linting issues automatically
lint-fix:
    uv run --group dev ruff check --fix .

# Format python code with ruff
format:
    uv run --group dev ruff format .

# Check python formatting without making changes
format-check:
    uv run --group dev ruff format --check .

# Type check python with ty
typecheck:
    uv run --group dev ty check --exit-zero-on-warning lib/ test/

# Run all python checks (lint + format check + typecheck + tests)
check: lint format-check typecheck test

# Generate python test coverage report in HTML
coverage-html:
    uv run --group dev pytest test/ --cov=lib --cov-report=html
    @echo "Coverage report generated in htmlcov/index.html"

# Clean python build artifacts
clean:
    rm -rf dist/
    rm -rf build/
    rm -rf *.egg-info
    rm -rf .pytest_cache
    rm -rf .ruff_cache
    rm -rf htmlcov
    rm -f .coverage
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Clean gem artifacts
clean-gem:
    rm -f *.gem
    @echo "Gem files cleaned"

# Full python clean (Python + Gem)
clean-all: clean clean-gem

# Update python dependencies
update:
    uv lock --upgrade

# Show python project info
info:
    @echo "Project: openc3-cosmos-script-engine-cstol-python"
    @echo "Python version:"
    @uv run python --version
    @echo "\nInstalled packages:"
    @uv pip list

# Run Python REPL with package loaded
repl:
    uv run python

# Export python project dependencies to requirements.txt (runtime only)
export-requirements:
    uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
    @echo "Runtime requirements exported to requirements.txt"

# Export all python dependencies including dev to requirements-dev.txt
export-requirements-dev:
    uv export --no-hashes --no-emit-project -o requirements-dev.txt
    @echo "All requirements (including dev) exported to requirements-dev.txt"
