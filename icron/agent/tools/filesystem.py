"""File system tools: read, write, edit."""

import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from icron.agent.tools.base import Tool


class WorkspaceSecurityError(Exception):
    """Raised when a path operation violates workspace boundaries."""
    pass


def validate_workspace_path(
    path_str: str,
    workspace: Path | None,
    restrict_to_workspace: bool = True,
) -> Path:
    """
    Validate and resolve a path, ensuring it stays within the workspace.

    Args:
        path_str: The path string to validate (may contain ~, .., etc.)
        workspace: The workspace root directory
        restrict_to_workspace: If True, enforce path containment

    Returns:
        Resolved absolute Path object

    Raises:
        WorkspaceSecurityError: If path escapes workspace boundaries
        FileNotFoundError: If workspace is required but not configured
    """
    # Input validation - reject empty paths
    if not path_str or not path_str.strip():
        raise WorkspaceSecurityError("Empty path is not allowed")

    # Reject null bytes (defense in depth)
    if "\x00" in path_str:
        raise WorkspaceSecurityError("Invalid characters in path")

    # Expand user home
    path = Path(path_str).expanduser()

    # If restriction is disabled, return resolved path
    if not restrict_to_workspace:
        return path.resolve()

    # Workspace must be configured when restriction is enabled
    if workspace is None:
        raise FileNotFoundError("Workspace not configured but restrict_to_workspace is enabled")

    # Resolve workspace
    workspace_resolved = workspace.resolve()

    # If path is relative, resolve it against the workspace
    if not path.is_absolute():
        path = workspace_resolved / path

    # Now resolve to absolute path
    resolved = path.resolve()

    try:
        # This raises ValueError if not relative
        resolved.relative_to(workspace_resolved)
    except ValueError:
        logger.warning(f"SECURITY: Path escape blocked - input={path_str!r} resolved={resolved} workspace={workspace_resolved}")
        raise WorkspaceSecurityError("Access denied: path is outside the allowed workspace")

    return resolved


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to read"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            file_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )

            if not file_path.exists():
                return f"Error: File not found: {path}"
            if not file_path.is_file():
                return f"Error: Not a file: {path}"

            content = file_path.read_text(encoding="utf-8")
            return content
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to write to"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            file_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )

            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {path}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "The text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }

    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            file_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )

            if not file_path.exists():
                return f"Error: File not found: {path}"

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return "Error: old_text not found in file. Make sure it matches exactly."

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return f"Warning: old_text appears {count} times. Please provide more context to make it unique."

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return f"Successfully edited {path}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to list"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            dir_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )

            if not dir_path.exists():
                return f"Error: Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Error: Not a directory: {path}"

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "[FILE] "
                items.append(f"{prefix}{item.name}")

            if not items:
                return f"Directory {path} is empty"

            return "\n".join(items)
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error listing directory: {str(e)}"


class RenameFileTool(Tool):
    """Tool to rename a file or directory."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "rename_file"

    @property
    def description(self) -> str:
        return "Rename a file or directory to a new name in the same location."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "old_path": {
                    "type": "string",
                    "description": "The current path of the file or directory"
                },
                "new_name": {
                    "type": "string",
                    "description": "The new name (not full path, just the name)"
                }
            },
            "required": ["old_path", "new_name"]
        }

    async def execute(self, old_path: str, new_name: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            old_file = validate_workspace_path(
                old_path,
                self.workspace,
                self.restrict_to_workspace,
            )
            if not old_file.exists():
                return f"Error: File or directory not found: {old_path}"

            # Ensure new_name is just a name, not a path
            if "/" in new_name or "\\" in new_name:
                return "Error: new_name should be just a name, not a path"

            new_file = old_file.parent / new_name
            
            # Validate destination is also within workspace
            try:
                validate_workspace_path(
                    str(new_file),
                    self.workspace,
                    self.restrict_to_workspace,
                )
            except WorkspaceSecurityError:
                return "Error: Destination would be outside workspace"
            
            if new_file.exists():
                return f"Error: Target already exists: {new_file}"

            old_file.rename(new_file)
            return f"Successfully renamed {old_path} to {new_name}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as e:
            return f"Error renaming: {str(e)}"


class MoveFileTool(Tool):
    """Tool to move a file or directory to a new location."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return "Move a file or directory to a new location. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The source path to move"
                },
                "destination": {
                    "type": "string",
                    "description": "The destination path"
                }
            },
            "required": ["source", "destination"]
        }

    async def execute(self, source: str, destination: str, **kwargs: Any) -> str:
        try:
            # Validate source path against workspace boundaries
            src_path = validate_workspace_path(
                source,
                self.workspace,
                self.restrict_to_workspace,
            )
            if not src_path.exists():
                return f"Error: Source not found: {source}"

            # Validate destination path against workspace boundaries
            dest_path = validate_workspace_path(
                destination,
                self.workspace,
                self.restrict_to_workspace,
            )

            # If destination is a directory, move source into it
            if dest_path.is_dir():
                dest_path = dest_path / src_path.name
                # Re-validate the new destination
                validate_workspace_path(
                    str(dest_path),
                    self.workspace,
                    self.restrict_to_workspace,
                )

            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if dest_path.exists():
                return f"Error: Destination already exists: {destination}"

            shutil.move(str(src_path), str(dest_path))
            return f"Successfully moved {source} to {destination}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as e:
            return f"Error moving: {str(e)}"


class CopyFileTool(Tool):
    """Tool to copy a file or directory."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "copy_file"

    @property
    def description(self) -> str:
        return "Copy a file or directory to a new location. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "The source path to copy"
                },
                "destination": {
                    "type": "string",
                    "description": "The destination path"
                }
            },
            "required": ["source", "destination"]
        }

    async def execute(self, source: str, destination: str, **kwargs: Any) -> str:
        try:
            # Validate source path against workspace boundaries
            src_path = validate_workspace_path(
                source,
                self.workspace,
                self.restrict_to_workspace,
            )
            if not src_path.exists():
                return f"Error: Source not found: {source}"

            # Validate destination path against workspace boundaries
            dest_path = validate_workspace_path(
                destination,
                self.workspace,
                self.restrict_to_workspace,
            )

            # If destination is a directory, copy source into it
            if dest_path.is_dir():
                dest_path = dest_path / src_path.name
                # Re-validate the new destination
                validate_workspace_path(
                    str(dest_path),
                    self.workspace,
                    self.restrict_to_workspace,
                )

            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if dest_path.exists():
                return f"Error: Destination already exists: {destination}"

            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dest_path))
            else:
                shutil.copy2(str(src_path), str(dest_path))

            return f"Successfully copied {source} to {destination}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return "Error: Permission denied"
        except Exception as e:
            return f"Error copying: {str(e)}"


class CreateDirTool(Tool):
    """Tool to create a new directory."""

    def __init__(
        self,
        workspace: Path | None = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "create_dir"

    @property
    def description(self) -> str:
        return "Create a new directory. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The directory path to create"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            # Validate path against workspace boundaries
            dir_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )
            if dir_path.exists():
                if dir_path.is_dir():
                    return f"Directory already exists: {path}"
                else:
                    return f"Error: A file with this name already exists: {path}"

            dir_path.mkdir(parents=True, exist_ok=True)
            return f"Successfully created directory: {path}"
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
        except PermissionError:
            return f"Error: Permission denied: {path}"
        except Exception as e:
            return f"Error creating directory: {str(e)}"
