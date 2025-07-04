import os
from typing import List

from app.state import OutputState
from app.utils import MAX_RETRY, NUMBER_OF_CONTEXT_DOCS, TEMPERATURE, TIMEOUT
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from openai import APIError, APITimeoutError, BadRequestError

load_dotenv()

NO_ANSWER_PROMPT = (
    '"I don\'t know the answer to that question due to insufficient context."'
)
GENERATOR_FALLBACK = {
    "answer": "Unable to answer the question due to API error. Please check the logs for details.",
    "citations": [],
    "additional_sources": [],
}


class Generator:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"You are a reliable document analysis assistant that answers questions strictly based on the {NUMBER_OF_CONTEXT_DOCS} provided context documents. If the context is missing, empty, or insufficient, reply with: {NO_ANSWER_PROMPT}. Avoid assumptions, hallucination, and harmful content. Stay factual, clear, and grounded in the context. IMPORTANT: Return only valid JSON.",
                ),
                ("human", "Contexts: {context}\nQuestion: {question}"),
            ],
        )

        llm_provider = (os.getenv("LLM_PROVIDER", "")).upper()
        match llm_provider:
            case "OPENAI":
                self.llm = ChatOpenAI(
                    model="gpt-4.1",
                    timeout=TIMEOUT,
                    max_retries=MAX_RETRY,
                    tags=[llm_provider.lower()],
                    temperature=TEMPERATURE,
                )
            case "DEEPSEEK":
                self.llm = ChatDeepSeek(
                    model="deepseek-chat",  # DeepSeek V3
                    timeout=TIMEOUT,
                    max_retries=MAX_RETRY,
                    tags=[llm_provider.lower()],
                    temperature=TEMPERATURE,
                )
            case _:
                raise ValueError(f"Unsupported LLM provider: {llm_provider}")

    # TODO: Manage doc positioning based on research
    def format_docs_as_context(self, docs: List[Document]):
        return (
            "\n"
            + "\n\n---\n\n".join(
                f"Source: {doc.metadata.get('source')}\nPage: {doc.metadata.get('page')}\nInformation: {doc.page_content}"
                for doc in docs
            )
            + "\n"
        )

    def __call__(self):
        return self.get_prompt() | self.get_llm()

    def get_prompt(self):
        return self.prompt

    def get_llm(self):
        return self.llm.with_structured_output(OutputState).with_fallbacks(
            self.__generator_fallback(),
            exceptions_to_handle=(APIError, APITimeoutError, BadRequestError),
        )

    def __generator_fallback(self):
        return [RunnableLambda(lambda x: GENERATOR_FALLBACK)]
