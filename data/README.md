# Source snapshots

These JSON files are the audited inputs used by `scripts/build_catalog.py`.
They are public metadata snapshots, not package archives.

Before committing, `scripts/sanitize_snapshots.py` removes:

- share passwords;
- `pwd` and similar credential query parameters;
- temporary signed URL parameters such as `e`;
- token-like fields.

The normalized catalog records the remaining access mode (`public`, `password`,
or `signed`) without publishing the removed value. Snapshot timestamps are
source evidence, not a promise that every link is currently reachable.
