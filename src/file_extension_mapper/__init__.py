"""File Extension Mapper.

Rename files in a directory by mapping old extensions to new ones,
with conflict resolution for name collisions that would otherwise
silently overwrite an existing file.
"""

from .core import ExtensionMapper, RenameResult, map_extensions

__all__ = ["ExtensionMapper", "RenameResult", "map_extensions"]
