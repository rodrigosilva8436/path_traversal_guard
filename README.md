# Path Traversal Guard

Validates that a resolved path stays within an allowed base directory, blocking directory traversal escapes (including symlink-based escapes).

## Usage

```python
import tempfile
from pathlib import Path
from path_traversal_guard import PathGuard, PathTraversalError

# PathGuard requires the base directory to exist on disk at construction time.
with tempfile.TemporaryDirectory() as tmp:
    # The base directory must exist before constructing the guard:
    uploads = Path(tmp) / "uploads"
    uploads.mkdir()
    guard = PathGuard(uploads)
    # ... or simply, if tmp already exists:
    guard = PathGuard(tmp)

    try:
        safe_path = guard.resolve_safe("user_42/profile.png")
        # safe_path is an absolute pathlib.Path inside the base directory
    except PathTraversalError:
        # reject the request
        ...

    # Non-throwing variant:
    if guard.is_safe("../../etc/passwd"):
        # won't reach here
        ...
```

## Why this exists

Any feature that opens a file from a user-supplied name — attachments, profile images, static asset serving — is one `..` away from a full read of the filesystem. Checking the string for `..` is not enough: symlinks inside the allowed area can point anywhere, and case/normalization differences defeat naive string matching.

This library resolves both the base directory and the candidate path to their real on-disk locations before deciding containment. The trade-off is that the base directory must exist at construction time (it is resolved with `strict=True`), while candidate paths are resolved with `strict=False` so that files about to be written can still be validated.

## Edge cases you will hit

- **Relative paths are anchored at the base.** A relative input like `subdir/file.txt` is treated as `base/subdir/file.txt`, not relative to the process's current working directory. This matches the usual "sandbox" mental model but may surprise callers who expect CWD semantics.
- **Symlinks are followed.** A symlink inside the base that points outside is rejected. A symlink inside the base that points deeper inside the base is allowed.
- **Non-existent paths inside the base are allowed.** This is intentional, so you can validate a destination before writing to it. The containment check uses the resolved parent chain, which is sufficient to prevent escapes via `..`.

## Exported names

- `PathGuard(base_directory)` — constructor; `base_directory` must be an existing directory.
  - `PathGuard.base_directory` — read-only `pathlib.Path` of the resolved base.
  - `PathGuard.resolve_safe(untrusted_path) -> pathlib.Path` — resolves and returns the path if inside the base; raises `PathTraversalError` otherwise.
  - `PathGuard.is_safe(untrusted_path) -> bool` — non-throwing variant.
- `PathTraversalError` — subclass of `ValueError`, raised on escape attempts.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

## Limitations

Values are coerced to floats, so very large integers lose precision. If you need
exact integer aggregates over a window, this is the wrong tool.

## Contributing

Issues and pull requests are welcome. Please keep the dependency list empty —
that constraint is the point of the project, not an oversight.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

