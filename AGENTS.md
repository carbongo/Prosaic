# Prosaic (fork)

Fork of [DimwitLabs/Prosaic](https://github.com/DimwitLabs/Prosaic) (remote `upstream`), a Textual terminal writing app. Fork-only changes: `git log upstream/main..main`.

| | |
|---|---|
| Set up | `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'` |
| Test | `.venv/bin/python -m pytest -q` |
| Run | `.venv/bin/prosaic` |
| Sync | `git fetch upstream && git merge upstream/main` |

## Docs

- `README.md`: features, keys, usage.
- `CHANGELOG.md`: upstream release notes.
