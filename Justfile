default: install lint test

install:
    uv lock --upgrade
    uv sync --all-extras --all-groups --frozen

lint:
    uv run ruff format .
    uv run ruff check . --fix
    uv run mypy .

lint-ci:
    uv run ruff format . --check
    uv run ruff check . --no-fix
    uv run mypy .
    uv run python planning/index.py --check

test *args:
    uv run pytest {{ args }}

index:
    uv run python planning/index.py

check-planning:
    uv run python planning/index.py --check

publish:
    rm -rf dist
    uv version $GITHUB_REF_NAME
    uv build
    uv publish --token $PYPI_TOKEN
