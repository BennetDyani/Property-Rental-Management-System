from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agents.tools import (
    check_payment_status,
    get_overdue_payment_overview,
    mark_rent_as_paid,
    get_tenant_details
)
from src.rag.retriever import MultimodalRetriever, prepare_rag_prompt


class PaymentAgent:
    """
    AI Agent specialized in rent collection and financial tracking using a ReAct graph.
    """

    def __init__(
            self,
            retriever: MultimodalRetriever,
            model_name: str | None = None,
    ):
        self.retriever = retriever
        model_name = model_name or settings.groq_model
        self.llm = ChatGroq(model=model_name, groq_api_key=settings.groq_api_key)

        self.tools = [
            check_payment_status,
            get_overdue_payment_overview,
            mark_rent_as_paid,
            get_tenant_details
        ]

        system_message = (
            "You are the Financial Controller for the property management system. "
            "Your expertise is in rent collection, payment tracking, and financial auditing. "
            "You are precise, professional, and firm but polite regarding overdue payments. "
            "When asked about payments, always verify the current status using tools before answering. "
            "For landlord or portfolio-wide overdue questions, use the overdue payment overview tool instead of asking for a tenant identifier."
        )

        self.agent = create_react_agent(self.llm, self.tools, prompt=system_message)

    def process_query(self, query: str, tenant_id: int | None = None) -> str:
        normalized_query = query.lower()
        if tenant_id is None and "overdue" in normalized_query and any(
            phrase in normalized_query for phrase in ("who", "how much", "owed", "owe")
        ):
            return get_overdue_payment_overview.invoke({})

        filters = {"tenant_id": tenant_id} if tenant_id is not None else None
        results = self.retriever.search(query, filters=filters)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Financial Policy Context:\n{rag_context}\n\n"
            f"User Query: {query}\n"
            f"Target Tenant ID: {tenant_id if tenant_id else 'General'}"
        )

        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content