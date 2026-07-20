#!/usr/bin/env bash
set -euo pipefail

repository_name="${1:-ThisTinti}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required." >&2
  exit 2
fi
gh auth status >/dev/null

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Run this script from the ThisTinti Git checkout." >&2
  exit 2
fi
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Refusing to publish a dirty working tree." >&2
  exit 2
fi

owner="$(gh api user --jq .login)"
full_name="${owner}/${repository_name}"
version="$(python -c 'from app.version import RELEASE_VERSION; print(RELEASE_VERSION)')"
tag="v${version}"

if gh repo view "$full_name" >/dev/null 2>&1; then
  echo "Repository ${full_name} already exists; refusing to overwrite it automatically." >&2
  exit 3
fi

# Keep the bundle/source remote untouched and publish through a dedicated remote.
git branch -M main
if git remote get-url github >/dev/null 2>&1; then
  git remote remove github
fi
gh repo create "$full_name" --public --source=. --remote=github
git push -u github main

if ! git rev-parse "$tag" >/dev/null 2>&1; then
  git tag "$tag"
fi
git push github "$tag"

# Enable the custom GitHub Actions publishing source. If token permissions do not
# permit it, the code and release workflow are already published and the user can
# enable Pages from Settings > Pages > GitHub Actions.
if ! gh api --method POST "repos/${full_name}/pages" -f build_type=workflow >/dev/null 2>&1; then
  echo "GitHub Pages was not enabled automatically. Enable Source: GitHub Actions in repository Settings > Pages." >&2
fi

echo "Published: https://github.com/${full_name}"
echo "Windows build: https://github.com/${full_name}/actions/workflows/windows-release.yml"
echo "Download page (after Pages deploy): https://${owner}.github.io/${repository_name}/"
