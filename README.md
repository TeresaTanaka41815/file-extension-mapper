# File Extension Mapper

Renames files in a directory by mapping old extensions to new ones, resolving name conflicts with a numeric suffix instead of silently overwriting.

## Usage

```python
import os, tempfile
from file_extension_mapper import ExtensionMapper, map_extensions

tmp = tempfile.mkdtemp()
open(os.path.join(tmp, "photo.jpeg"), "w").close()
open(os.path.join(tmp, "photo.jpg"), "w").close()

# Returns a list of RenameResult(original, renamed, skipped, reason)
results = map_extensions(tmp, {"jpeg": "jpg", "tif": "tiff"})

# Same thing with options
mapper = ExtensionMapper(
    directory=tmp,
    mapping={"jpeg": "jpg"},
    overwrite=False,
    dry_run=True,
    clock=lambda: 1.0,
)
results = mapper.run()
```

## Why

Bulk-renaming files by extension looks trivial until two files want the same target name. The common failure mode is an implicit `os.rename` that clobbers the loser; the second is a rename loop that tries to move `photo.jpeg` to `photo.jpg` while `photo.jpg` already exists and there is no obvious place to put it. This library exists to make that one decision explicit: never overwrite by default, insert `_<n>` before the new extension until a free name is found.

The trade-off is determinism over intelligence. The suffix counter is seeded from a clock function so two runs in the same directory do not collide on the same sequence; in tests you pass a fake clock so results do not depend on wall-clock time.

## Edges you will hit

- Subdirectories are ignored. `ExtensionMapper` renames plain files only, so `sub/a.txt` is left alone even if you map `txt`.
- Extension matching is case-insensitive on the old extension (`Photo.JPG` matches `jpg`), but the new extension is used verbatim, including its case.
- A file whose old and new extension resolve to the same name is skipped, not renamed, with `reason="extension unchanged"`.
- `overwrite=True` deletes an existing target file before renaming. This is the only path that touches data outside the file being renamed.

## Layout

```
PYTHONPATH=src python -m unittest discover -s tests
```

Exports: `ExtensionMapper`, `RenameResult`, `map_extensions`.
