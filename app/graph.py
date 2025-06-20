from app.generator import Generator
from app.retriever import Retriever
from app.state import ContextState, InputState, OutputState, OverallState
from app.utils import NUMBER_OF_CONTEXT_DOCS, convert_document_to_additional_source
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

retriever = Retriever()
generator = Generator()


async def retriever_node(state: InputState) -> ContextState:
    retrieved_docs = await retriever().ainvoke(state["question"])
    return {
        "question": state["question"],
        "context": retrieved_docs[:NUMBER_OF_CONTEXT_DOCS],
        "additional_sources": retrieved_docs[NUMBER_OF_CONTEXT_DOCS:],
    }


async def generator_node(context_state: ContextState) -> OutputState:
    prompt = await generator.get_prompt().ainvoke(
        {
            "question": context_state["question"],
            "context": generator.format_docs_as_context(context_state["context"]),
        }
    )
    response = await generator.get_llm().ainvoke(prompt)
    additional_sources_from_context_state = [
        convert_document_to_additional_source(doc)
        for doc in context_state["additional_sources"]
    ]
    return {
        "answer": response.get("answer"),
        "citations": response.get("citations", []),
        "additional_sources": response.get("additional_sources", [])
        + additional_sources_from_context_state,
    }


builder = StateGraph(OverallState, input=InputState, output=OutputState)
builder.add_node("retriever", retriever_node)
builder.add_node("generator", generator_node)
builder.add_edge(START, "retriever")
builder.add_edge("retriever", "generator")
builder.add_edge("generator", END)
graph = builder.compile()
graph.name = "QA System for Business Case"
