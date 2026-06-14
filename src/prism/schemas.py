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


class ReviewComment(BaseModel):
    """
    represents a review comment to be posted on GitHub
    """

    filename: str
    line: int
    comment: str
    severity: str  # critical, suggestion or nitpick
    model_config = ConfigDict(extra="forbid")


class ClassificationResult(BaseModel):
    diff_type: str
    reasoning: str
    model_config = ConfigDict(extra="forbid")


class ReviewCommentList(BaseModel):
    comments: list[ReviewComment]
    model_config = ConfigDict(extra="forbid")
