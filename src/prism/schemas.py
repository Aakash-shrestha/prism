from pydantic import BaseModel, ConfigDict


class FileDiff(BaseModel):
    """
    represents one file in the diff
    """

    filename: str
    status: str  # "added", "modified", "removed"
    patch: str  # raw +/- lines for this file
    model_config = ConfigDict(extra="forbid")


class ParsedDiff(BaseModel):
    """
    represents the parsed diff for a PR, which is a list of file diffs
    """

    files: list[FileDiff]
    total_files: int
    model_config = ConfigDict(extra="forbid")
