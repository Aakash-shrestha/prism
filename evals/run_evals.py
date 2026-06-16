from datetime import datetime

from rich.console import Console
from rich.rule import Rule

from evals.cases import EVAL_CASES, EvalCase, EvalResult
from evals.judge import ScoredResult, judge_eval_case
from prism.agent import run_review

console = Console()


def run_eval_case(case: EvalCase) -> EvalResult:
    classification, filtered_comments = run_review("eval/test", 0, case.diff)

    return EvalResult(
        id=case.id,
        diff_type=case.diff_type,
        actual_diff_type=classification.diff_type,
        comments=[comment.model_dump() for comment in filtered_comments],
    )


def print_scored_result(result: ScoredResult) -> None:
    score_color = "green" if result.score >= 80 else "yellow" if result.score >= 50 else "red"

    id_col = f"{result.id:<32}"
    diff_col = f"{result.diff_type:<12}→ {result.actual_diff_type:<12}"
    score_col = f"{result.score}/100"

    console.print(f"  {id_col}  {diff_col}  [bold {score_color}]{score_col}[/bold {score_color}]")
    console.print(f"  {'':<32}  [dim]{result.reasoning}[/dim]")

    for issue in result.missed_issues:
        console.print(f"  [red]✗[/red] [dim]{issue}[/dim]")
    for fp in result.false_positives:
        console.print(f"  [yellow]![/yellow] [dim]false positive: {fp}[/dim]")


def main():
    run_id = datetime.now().isoformat()
    scored: list[ScoredResult] = []

    console.print(Rule(f"[dim]run {run_id}[/dim]", style="dim"))
    header_id = f"{'case':<32}"
    header_diff = f"{'expected':<12}  {'actual':<12}"
    console.print(f"  [dim]{header_id}  {header_diff}  score[/dim]")
    console.print(Rule(style="dim"))

    with open("evals/results.jsonl", "a") as f:
        for eval_cases in EVAL_CASES:
            eval_result = run_eval_case(eval_cases)
            judge_result: ScoredResult = judge_eval_case(eval_cases, eval_result, run_id)
            f.write(judge_result.model_dump_json() + "\n")
            scored.append(judge_result)
            print_scored_result(judge_result)

    avg = sum(r.score for r in scored) / len(scored)
    score_color = "green" if avg >= 80 else "yellow" if avg >= 50 else "red"
    console.print(Rule(style="dim"))
    console.print(
        f"  {'average':<32}  {'':<26}  [bold {score_color}]{avg:.0f}/100[/bold {score_color}]"
    )


if __name__ == "__main__":
    main()
