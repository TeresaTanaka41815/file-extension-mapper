from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class RenameResult:
    """One rename operation's outcome.

    `original` is the file's name before renaming; `renamed` is its name
    after. If `skipped` is True the file was not renamed and `renamed`
    equals `original`.
    """

    original: str
    renamed: str
    skipped: bool = False
    reason: Optional[str] = None


@dataclass
class ExtensionMapper:
    """Rename files by mapping old extensions to new ones.

    The mapper walks a directory and renames every file whose extension
    (the part after the final dot, case-insensitive) appears in `mapping`.
    If a candidate new name already exists on disk and is not the file
    being renamed itself, the mapper inserts a numeric suffix before the
    extension until a free name is found (`photo.jpg` -> `photo_1.jpg`).

    A clock function is accepted so callers (notably tests) can control
    any behaviour that would otherwise depend on the environment. The
    default uses `time.monotonic`.
    """

    directory: str
    mapping: dict
    overwrite: bool = False
    dry_run: bool = False
    clock: Callable[[], float] = field(default=None)

    def __post_init__(self) -> None:
        if not isinstance(self.directory, str):
            raise TypeError("directory must be a string path")
        if not isinstance(self.mapping, dict):
            raise TypeError("mapping must be a dict of {old_ext: new_ext}")
        if self.clock is None:
            import time

            self.clock = time.monotonic
        # Normalise keys to lowercase so matching is case-insensitive.
        self.mapping = {
            (k.lstrip(".").lower() if isinstance(k, str) else k): v
            for k, v in self.mapping.items()
        }

    def _split_ext(self, name: str):
        return posixpath.splitext(name)

    def _candidate_names(self, base: str, new_ext: str):
        """Yield candidate filenames, resolving collisions by suffix.

        First yields `base + new_ext`. If that collides, yields
        `base_1<ext>`, `base_2<ext>`, and so on. The suffix counter is
        seeded from the clock so two runs in the same directory do not
        pick the same sequence; this matters when mapping many files at
        once and the first free suffix from one run should not collide
        with names created in a later run.
        """

        yield base + new_ext
        start = int(self.clock()) % 1000 + 1
        i = start
        seen = set()
        while True:
            cand = f"{base}_{i}{new_ext}"
            if cand not in seen:
                seen.add(cand)
                yield cand
            i += 1

    def _os_path_join(self, *parts: str) -> str:
        # Use os.path, not posixpath, so the library works on the host
        # filesystem regardless of platform. posixpath above is only for
        # splitting extension strings, which is platform-independent.
        return os.path.join(*parts)

    def run(self) -> List[RenameResult]:
        if not os.path.isdir(self.directory):
            raise NotADirectoryError(self.directory)

        results: List[RenameResult] = []
        # Track names we intend to create this run, so two files in the
        # same batch that both want `data.json` do not both pick it.
        planned: set = set()
        entries = sorted(os.listdir(self.directory))

        for name in entries:
            full = self._os_path_join(self.directory, name)
            if not os.path.isfile(full):
                continue
            base, ext = self._split_ext(name)
            old_ext = ext.lstrip(".").lower()
            if old_ext not in self.mapping:
                continue
            value = self.mapping[old_ext]
            if not isinstance(value, str):
                raise TypeError(
                    f"mapping value for {old_ext!r} must be a string, got {type(value).__name__}"
                )
            new_ext = value if value.startswith(".") else "." + value
            new_ext_lower = new_ext.lower()
            same_ext = ext.lower() == new_ext_lower

            chosen: Optional[str] = None
            skip_reason: Optional[str] = None

            for cand in self._candidate_names(base, new_ext):
                cand_full = self._os_path_join(self.directory, cand)
                on_disk = os.path.exists(cand_full)
                same_file = (cand_full == full) or (
                    os.path.exists(cand_full)
                    and os.path.samefile(cand_full, full)
                )
                in_planned = cand in planned
                if on_disk and not same_file:
                    if self.overwrite:
                        chosen = cand
                        break
                    continue
                if in_planned:
                    continue
                chosen = cand
                break
            else:  # pragma: no cover - guarded by unbounded generator
                skip_reason = "no free name found"

            if chosen is None:
                results.append(
                    RenameResult(original=name, renamed=name, skipped=True, reason=skip_reason)
                )
                continue

            if same_ext and chosen == name:
                results.append(
                    RenameResult(
                        original=name,
                        renamed=name,
                        skipped=True,
                        reason="extension unchanged",
                    )
                )
                continue

            planned.add(chosen)
            chosen_full = self._os_path_join(self.directory, chosen)
            if not self.dry_run:
                if self.overwrite and os.path.exists(chosen_full) and chosen_full != full:
                    os.remove(chosen_full)
                os.rename(full, chosen_full)
            results.append(RenameResult(original=name, renamed=chosen))

        return results


def map_extensions(
    directory: str,
    mapping: dict,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    clock: Optional[Callable[[], float]] = None,
) -> List[RenameResult]:
    """Convenience wrapper around `ExtensionMapper.run`.

    Renames files in `directory` according to `mapping` and returns the
    list of per-file outcomes.
    """
    return ExtensionMapper(
        directory=directory,
        mapping=mapping,
        overwrite=overwrite,
        dry_run=dry_run,
        clock=clock,
    ).run()
