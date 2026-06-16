from textwrap import dedent
from typing import cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from evals.cases import EvalCase, EvalResult
from prism.config import settings


class JudgeResult(BaseModel):
    score: int = Field(..., ge=0, le=100)
    caught_issues: list[str] = Field(default_factory=list)
    missed_issues: list[str] = Field(default_factory=list)
    false_positives: list[str] = Field(default_factory=list)
    reasoning: str
    model_config = ConfigDict(extra="forbid")


class ScoredResult(BaseModel):
    run_id: str
    id: str
    diff_type: str
    actual_diff_type: str
    score: int = Field(..., ge=0, le=100)
    caught_issues: list[str]
    missed_issues: list[str]
    false_positives: list[str]
    reasoning: str
    model_config = ConfigDict(extra="forbid")


def judge_eval_case(case: EvalCase, result: EvalResult, run_id: str) -> ScoredResult:
    model = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=settings.groq_api_key,
        temperature=0,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                dedent("""
                    You are an impartial judge evaluating the output of an AI code reviewer.

                    You will be given three lists:
                    - EXPECTED ISSUES: real bugs or problems a good reviewer must catch
                    - SHOULD NOT FLAG: things that are not problems — flagging these is a false positive
                    - ACTUAL COMMENTS: the comments the AI reviewer produced

                    Instructions:
                    1. For each expected issue, check whether any actual comment covers it.
                       Be generous with wording — a comment counts as caught if it identifies
                       the same root problem, even if phrased differently.
                    2. For each actual comment, check whether it flags something from SHOULD NOT FLAG.
                       If so, it is a false positive.
                    3. Score from 0 to 100:
                       - Start at 100
                       - Subtract 20 for each missed expected issue
                       - Subtract 10 for each false positive
                       - If EXPECTED ISSUES is empty and there are no false positives, score is 100
                    4. reasoning must be one sentence.
                """).strip(),
            ),
            (
                "human",
                dedent("""
                    EXPECTED ISSUES:
                    {expected_issues}

                    SHOULD NOT FLAG:
                    {should_not_flag}

                    ACTUAL COMMENTS:
                    {actual_comments}
                """).strip(),
            ),
        ]
    )

    structured_model = model.with_structured_output(JudgeResult)
    chain = prompt | structured_model
    judge_result = cast(
        JudgeResult,
        chain.invoke(
            {
                "expected_issues": "\n".join(f"- {i}" for i in case.expected_issues) or "(none)",
                "should_not_flag": "\n".join(f"- {s}" for s in case.should_not_flag) or "(none)",
                "actual_comments": "\n".join(
                    f"- [{c['severity']}] {c['filename']} line {c['line']}: {c['comment']}"
                    for c in result.comments
                )
                or "(none)",
            }
        ),
    )

    return ScoredResult(
        run_id=run_id,
        id=result.id,
        diff_type=result.diff_type,
        actual_diff_type=result.actual_diff_type,
        score=judge_result.score,
        caught_issues=judge_result.caught_issues,
        missed_issues=judge_result.missed_issues,
        false_positives=judge_result.false_positives,
        reasoning=judge_result.reasoning,
    )
