set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := true

PYTHON := "python3"
UV := "uv"
PACKAGE := "pretix-partial-cancellation"

# Show this list of available commands
help:
  @just --list

# Show current package version from pyproject.toml
version:
  @{{UV}} version --short

# Build source and wheel distributions
build:
  @rm -rf dist
  @{{UV}} build

# Publish to PyPI (expects PYPI_TOKEN or UV_PUBLISH_TOKEN)
publish: build
  @if [[ -f .env.local ]]; then set -a; source .env.local; set +a; fi
  @if [[ -z "${PYPI_TOKEN:-}" && -z "${UV_PUBLISH_TOKEN:-}" ]]; then echo "Set PYPI_TOKEN or UV_PUBLISH_TOKEN"; exit 1; fi
  @if [[ -n "${PYPI_TOKEN:-}" ]]; then {{UV}} publish --token "$PYPI_TOKEN"; else {{UV}} publish; fi

# Lint with Ruff and Ty (Astral)
lint:
  @{{UV}} tool run ruff check .
  @{{UV}} tool run --with "pretix>=2025.7.0" --with "django>=4.2" ty check .

# Create a GitHub release and push a new version tag
release:
  @if [[ -n $(git status --porcelain) ]]; then echo "Working tree not clean"; exit 1; fi
  @current_version=$({{UV}} version --short); \
  echo "Current version: $current_version"; \
  read -r -p "New version: " new_version; \
  if [[ -z "$new_version" ]]; then echo "No version provided"; exit 1; fi; \
  read -r -p "Release title: " release_title; \
  if [[ -z "$release_title" ]]; then echo "No release title provided"; exit 1; fi; \
  notes_file=$(mktemp); \
  echo "Enter release notes, finish with Ctrl-D:"; \
  cat > "$notes_file"; \
  {{UV}} version "$new_version"; \
  git add pyproject.toml; \
  git commit -m "Release v$new_version"; \
  git tag "v$new_version"; \
  git push --follow-tags; \
  gh release create "v$new_version" --title "$release_title" --notes-file "$notes_file"; \
  rm -f "$notes_file"
