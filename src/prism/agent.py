from textwrap import dedent
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from prism.config import settings
from prism.schemas import ClassificationResult, ReviewComment


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
        model="llama-3.3-70b-versatile", api_key=settings.groq_api_key, temperature=0
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
