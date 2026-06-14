from textwrap import dedent
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from prism.config import settings
from prism.schemas import ClassificationResult, ReviewComment, ReviewCommentList, FilteredCommentList


class AgentState(TypedDict):
    repo: str
    pr_number: int
    raw_diff: str
    classification: ClassificationResult | None
    comments: list[ReviewComment]
    filtered_comments: list[ReviewComment]


def classify_node(state: AgentState) -> dict:
    raw_diff = state["raw_diff"]
    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key.get_secret_value(),
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                dedent("""
            Classify this PR diff. Identify the type of change and your reasoning.
        """).strip(),
            ),
            ("human", "{raw_diff}"),
        ]
    )

    structured_model = model.with_structured_output(ClassificationResult)
    chain = prompt | structured_model
    result = chain.invoke({"raw_diff": raw_diff})

    return {"classification": result}


FOCUS_BY_TYPE: dict[str, str] = {
    "bug_fix": "Focus on whether the fix is correct and complete. Look for edge cases, missing null checks, off-by-one errors, and whether the root cause is actually addressed.",
    "feature": "Focus on correctness, error handling, and security. Flag missing input validation, auth gaps, and untested code paths.",
    "refactor": "Focus on whether behavior is truly preserved. Look for subtle logic changes, removed error handling, or renamed symbols that break callers.",
    "style": "This is a low-risk diff. Only flag issues that would cause actual problems — skip formatting and naming preferences.",
    "docs": "Check for accuracy and completeness. Flag outdated examples or incorrect descriptions.",
    "test": "Check that tests actually assert meaningful behavior and cover edge cases, not just happy paths.",
}

_DEFAULT_FOCUS = "Review the diff carefully. Flag bugs, security issues, and missing error handling. Skip minor style issues."


def generate_node(state: AgentState) -> dict:
    raw_diff = state["raw_diff"]
    diff_type = state["classification"].diff_type

    focus = FOCUS_BY_TYPE.get(diff_type, _DEFAULT_FOCUS)

    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key.get_secret_value(),
        temperature=0.2,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                dedent(f"""
                    You are a senior code reviewer. This PR is classified as: {diff_type}.

                    {focus}

                    Return only comments worth acting on. Be specific — reference the exact line or block.
                    Severity guide: critical = must fix before merge, suggestion = should fix, nitpick = optional.
                """).strip(),
            ),
            ("human", "PR Diff:\n{raw_diff}"),
        ]
    )

    structured_model = model.with_structured_output(ReviewCommentList)
    chain = prompt | structured_model
    result = chain.invoke({"raw_diff": raw_diff})

    return {"comments": result.comments}


def critic_node(state: AgentState) -> dict:
    comments = state["comments"]
    raw_diff = state["raw_diff"]

    if not comments:
        return {"filtered_comments": []}

    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key.get_secret_value(),
        temperature=0,
    )

    structured_model = model.with_structured_output(FilteredCommentList)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                dedent("""
                    You are a senior engineer reviewing AI-generated PR comments before they are posted.
                    Your job is to filter out comments that are wrong, vague, or not worth the author's time.

                    Keep a comment if:
                    - It identifies a real bug, security issue, or correctness problem (always keep critical)
                    - It is a clear, actionable suggestion grounded in the actual diff
                    - It is a nitpick only if it is clearly valid and specific — not a style preference

                    Drop a comment if:
                    - It is vague or could apply to any codebase ("consider adding error handling")
                    - It references code that does not exist in the diff (hallucinated)
                    - It is a nitpick about naming, formatting, or style with no real impact
                    - It is borderline — when in doubt, discard it

                    Severity rule: keep all critical and suggestion comments that pass the above checks.
                    For nitpicks, keep only if the issue is clearly valid and specific.
                """).strip(),
            ),
            ("human", "PR Diff:\n{raw_diff}\n\nAI-Generated Comments:\n{comments}"),
        ]
    )

    formatted_comments = "\n".join(
        f"{i}. [{c.severity.upper()}] {c.filename} (line {c.line}): {c.comment}"
        for i, c in enumerate(comments, 1)
    )
    chain = prompt | structured_model
    result = chain.invoke({"raw_diff": raw_diff, "comments": formatted_comments})
    return {"filtered_comments": result.comments}
