#!/usr/bin/env bash
set -euo pipefail

repository_name="${1:-thistinti-staging}"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is required: https://cli.github.com/" >&2
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

if gh repo view "$full_name" >/dev/null 2>&1; then
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "https://github.com/${full_name}.git"
  else
    git remote add origin "https://github.com/${full_name}.git"
  fi
else
  gh repo create "$full_name" --private --source=. --remote=origin
fi

git push -u origin "$(git branch --show-current)"
echo "Published privately to https://github.com/${full_name}"
