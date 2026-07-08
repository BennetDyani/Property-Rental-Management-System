from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agents.tools import get_income_forecast
from src.rag.retriever import MultimodalRetriever, prepare_rag_prompt


class ForecastingAgent:
    """
    AI Agent specialized in financial projections and income forecasting using a ReAct graph.
    """

    def __init__(
            self,
            retriever: MultimodalRetriever,
            model_name: str | None = None,
    ):
        self.retriever = retriever
        model_name = model_name or settings.groq_model
        self.llm = ChatGroq(model=model_name, groq_api_key=settings.groq_api_key)

        self.tools = [get_income_forecast]

        system_message = (
            "You are a Senior Financial Analyst. Your expertise is in rental yield "
            "projections and income forecasting. You provide data-driven insights, "
            "identifying trends and potential financial risks. "
            "Be precise with numbers and provide clear, professional summaries."
        )

        self.agent = create_react_agent(self.llm, self.tools, prompt=system_message)

    def process_query(self, query: str, property_id: int | None = None) -> str:
        results = self.retriever.search(query)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Financial Strategy Context:\n{rag_context}\n\n"
            f"User Query: {query}\n"
            f"Target Property ID: {property_id if property_id else 'Portfolio-wide'}"
        )

        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content