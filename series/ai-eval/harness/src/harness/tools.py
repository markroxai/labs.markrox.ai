"""The agent's four tools, with strict argument schemas.

Tools never raise on bad input from the model. Invalid arguments, unknown tools, and
unknown IDs all come back as a structured `ToolError`; Lab 01 reads those errors to
detect hallucinated parameters.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# --- Corpus interface ---------------------------------------------------------------


class Section(BaseModel):
    doc_id: str
    section_id: str
    heading: str
    text: str


class SearchHit(BaseModel):
    doc_id: str
    title: str
    section_id: str
    snippet: str
    score: float


class Corpus(Protocol):
    """What the tools need from the corpus. Implemented by the corpus component."""

    def search(self, query: str, k: int) -> list[SearchHit]: ...

    def sections(self, doc_id: str) -> list[Section] | None:
        """All sections of a document in order, or None if the doc_id is unknown."""
        ...


# --- Argument schemas -------------------------------------------------------------


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchCorpusArgs(_Args):
    """Search the corpus and return the best-matching sections."""

    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=10)


class ListSectionsArgs(_Args):
    """List the sections of one document."""

    doc_id: str = Field(min_length=1)


class ReadDocumentArgs(_Args):
    """Read the full text of one section of a document."""

    doc_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)


class Citation(_Args):
    doc_id: str
    section_id: str


class SubmitAnswerArgs(_Args):
    """Submit the final answer with citations, or abstain. Ends the run."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    abstain: bool = False


ARG_SCHEMAS: dict[str, type[_Args]] = {
    "search_corpus": SearchCorpusArgs,
    "list_sections": ListSectionsArgs,
    "read_document": ReadDocumentArgs,
    "submit_answer": SubmitAnswerArgs,
}

FINAL_TOOL = "submit_answer"


def tool_specs() -> list[dict[str, Any]]:
    """Tool definitions in the OpenAI function-calling format that LiteLLM accepts."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": schema.__doc__ or "",
                "parameters": schema.model_json_schema(),
            },
        }
        for name, schema in ARG_SCHEMAS.items()
    ]


# --- Results ------------------------------------------------------------------------


class ErrorCode(StrEnum):
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGS = "invalid_args"
    UNKNOWN_DOC_ID = "unknown_doc_id"
    UNKNOWN_SECTION_ID = "unknown_section_id"


class ToolError(BaseModel):
    code: ErrorCode
    message: str
    field: str | None = None
    value: Any = None


class ToolResult(BaseModel):
    tool: str
    output: Any = None
    error: ToolError | None = None
    ends_run: bool = False


# --- Implementations ------------------------------------------------------------------


def _unknown_doc(doc_id: str) -> ToolError:
    return ToolError(
        code=ErrorCode.UNKNOWN_DOC_ID,
        message=f"No document with doc_id '{doc_id}'",
        field="doc_id",
        value=doc_id,
    )


def search_corpus(corpus: Corpus, args: SearchCorpusArgs) -> ToolResult:
    hits = corpus.search(args.query, args.k)
    return ToolResult(tool="search_corpus", output=[h.model_dump() for h in hits])


def list_sections(corpus: Corpus, args: ListSectionsArgs) -> ToolResult:
    sections = corpus.sections(args.doc_id)
    if sections is None:
        return ToolResult(tool="list_sections", error=_unknown_doc(args.doc_id))
    output = [{"section_id": s.section_id, "heading": s.heading} for s in sections]
    return ToolResult(tool="list_sections", output=output)


def read_document(corpus: Corpus, args: ReadDocumentArgs) -> ToolResult:
    sections = corpus.sections(args.doc_id)
    if sections is None:
        return ToolResult(tool="read_document", error=_unknown_doc(args.doc_id))
    for section in sections:
        if section.section_id == args.section_id:
            return ToolResult(tool="read_document", output=section.model_dump())
    return ToolResult(
        tool="read_document",
        error=ToolError(
            code=ErrorCode.UNKNOWN_SECTION_ID,
            message=f"Document '{args.doc_id}' has no section_id '{args.section_id}'",
            field="section_id",
            value=args.section_id,
        ),
    )


def submit_answer(corpus: Corpus, args: SubmitAnswerArgs) -> ToolResult:
    """Always ends the run. Citations are recorded as given; checking them is a grader's job."""
    return ToolResult(tool=FINAL_TOOL, output=args.model_dump(), ends_run=True)


_IMPLEMENTATIONS = {
    "search_corpus": search_corpus,
    "list_sections": list_sections,
    "read_document": read_document,
    "submit_answer": submit_answer,
}


def execute_tool(corpus: Corpus, name: str, args: dict[str, Any]) -> ToolResult:
    """Validate arguments and run one tool. Never raises on bad model input."""
    if name not in ARG_SCHEMAS:
        return ToolResult(
            tool=name,
            error=ToolError(
                code=ErrorCode.UNKNOWN_TOOL,
                message=f"Unknown tool '{name}'. Tools: {', '.join(ARG_SCHEMAS)}",
                value=name,
            ),
        )
    try:
        parsed = ARG_SCHEMAS[name].model_validate(args)
    except ValidationError as exc:
        first = exc.errors()[0]
        return ToolResult(
            tool=name,
            error=ToolError(
                code=ErrorCode.INVALID_ARGS,
                message=f"Invalid arguments for '{name}': {exc.error_count()} error(s); "
                f"first: {first['msg']}",
                field=".".join(str(p) for p in first["loc"]) or None,
                value=first.get("input"),
            ),
        )
    return _IMPLEMENTATIONS[name](corpus, parsed)
