"""Core logic for validating that a path stays within an allowed base directory."""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["PathGuard", "PathTraversalError"]


class PathTraversalError(ValueError):
    """Raised when a resolved path would escape its allowed base directory.

    Subclasses ValueError because callers frequently handle bad input as a
    ValueError already; making this a distinct type lets them be more
    specific when they want to.
    """


class PathGuard:
    """Validate that user-supplied paths stay within a fixed base directory.

    The base directory is resolved to a real, absolute path at construction
    time (using Path.resolve()). Any symlink inside the base is also
    resolved, so a symlink that points outside the base is rejected — even
    if the literal user string looked like it stayed inside. This is the
    central security property: the decision is made on the final on-disk
    location, not on the text of the request.

    Only the base directory itself is required to exist. Individual paths
    being validated do not need to exist; we resolve them lexically so that
    a not-yet-created file can still be checked before it is written. This
    matters for upload-then-write workflows.
    """

    def __init__(self, base_directory: str | os.PathLike[str]) -> None:
        base = Path(base_directory).resolve(strict=True)
        if not base.is_dir():
            # resolve(strict=True) already raises FileNotFoundError for
            # missing paths, but is_dir() also rejects the case where the
            # path exists as a file. We keep both for clarity.
            raise NotADirectoryError(f"base directory is not a directory: {base}")
        self._base = base

    @property
    def base_directory(self) -> Path:
        """The resolved base directory this guard was constructed with."""
        return self._base

    def resolve_safe(self, untrusted_path: str | os.PathLike[str]) -> Path:
        """Resolve ``untrusted_path`` and return it if it is inside the base.

        The returned path is absolute and normalized. It is guaranteed to be
        the base directory itself or a descendant of it.

        Raises:
            PathTraversalError: if the resolved path is outside the base.

        Notes:
            ``strict=False`` is used so that non-existent paths (e.g. a file
            about to be written) can still be validated. The trade-off is
            that the final component cannot be verified against the real
            filesystem; we accept that because our containment check uses
            the resolved parent chain, which is sufficient to prevent
            escapes via ``..``.
        """
        candidate = Path(untrusted_path)

        # If the user gives us a relative path, anchor it at the base
        # before resolving. This matches the common mental model:
        # "relative means relative to the sandbox".
        if not candidate.is_absolute():
            candidate = self._base / candidate

        resolved = candidate.resolve(strict=False)
        self._check_containment(resolved)
        return resolved

    def _check_containment(self, resolved: Path) -> None:
        # Path.is_relative_to would be cleaner, but it only exists from
        # Python 3.9 onward and silently returns False for unrelated
        # paths rather than distinguishing "outside" from "not comparable".
        # We compare the resolved path against the base using os.path's
        # commonpath, which normalizes both sides and gives a single,
        # unambiguous answer.
        base_str = str(self._base)
        resolved_str = str(resolved)
        common = os.path.commonpath([base_str, resolved_str])
        if common != base_str:
            raise PathTraversalError(
                f"path escapes base directory: {resolved} is not under {self._base}"
            )

    def is_safe(self, untrusted_path: str | os.PathLike[str]) -> bool:
        """Return True if ``untrusted_path`` resolves inside the base.

        Non-throwing variant of :meth:`resolve_safe`.
        """
        try:
            self.resolve_safe(untrusted_path)
            return True
        except PathTraversalError:
            return False
