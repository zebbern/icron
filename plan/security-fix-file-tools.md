# Security Fix: File Tool Workspace Validation

## Problem
The following file tools lack workspace boundary enforcement, allowing potential path traversal attacks:
- `RenameFileTool` (line 325)
- `MoveFileTool` (line 375)
- `CopyFileTool` (line 429)
- `CreateDirTool` (line 487)

## Solution
Add the same workspace validation pattern used by `ReadFileTool` and `WriteFileTool`:

1. Add `__init__` with `workspace` and `restrict_to_workspace` parameters
2. Call `validate_workspace_path()` for all path inputs
3. Handle `WorkspaceSecurityError` exceptions

## Tasks

- [x] Task 1: Add workspace validation to RenameFileTool
- [x] Task 2: Add workspace validation to MoveFileTool  
- [x] Task 3: Add workspace validation to CopyFileTool
- [x] Task 4: Add workspace validation to CreateDirTool
- [ ] Task 5: Test security validation
- [ ] Task 6: Commit and push changes

## Pattern to Apply

```python
class ToolName(Tool):
    def __init__(
        self,
        workspace: Optional[Path] = None,
        restrict_to_workspace: bool = True,
    ):
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace

    async def execute(self, path: str, **kwargs: Any) -> str:
        try:
            validated_path = validate_workspace_path(
                path,
                self.workspace,
                self.restrict_to_workspace,
            )
            # ... rest of logic
        except WorkspaceSecurityError as e:
            return f"Error: {e}"
```
