default: install lint test

install:
    uv lock --upgrade
    uv sync --all-extras --frozen --group lint

lint:
    uv run eof-fixer .
    uv run ruff format
    uv run ruff check --fix
    uv run ty check

lint-ci:
    uv run eof-fixer . --check
    uv run ruff format --check
    uv run ruff check --no-fix
    uv run ty check
    uv run python planning/index.py --check

index:
    uv run python planning/index.py

check-planning:
    uv run python planning/index.py --check

test *args:
    uv run --no-sync pytest {{ args }}

test-ci:
    uv run --no-sync pytest --cov=. --cov-report term-missing --cov-report xml --cov-fail-under=100

test-branch:
    uv run --no-sync pytest --cov=. --cov-branch --cov-fail-under=100

# Auth via PyPI Trusted Publishing (OIDC); uv publish auto-detects the CI id-token.
publish:
    rm -rf dist
    uv version $GITHUB_REF_NAME
    uv build
    uv publish
