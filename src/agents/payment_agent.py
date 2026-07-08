from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.agents.tools import (
    check_payment_status,
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
            model_name: str = "gpt-oss-120b",
    ):
        self.retriever = retriever
        self.llm = ChatGroq(model=model_name)

        self.tools = [
            check_payment_status,
            mark_rent_as_paid,
            get_tenant_details
        ]

        system_message = (
            "You are the Financial Controller for the property management system. "
            "Your expertise is in rent collection, payment tracking, and financial auditing. "
            "You are precise, professional, and firm but polite regarding overdue payments. "
            "When asked about payments, always verify the current status using tools before answering."
        )

        self.agent = create_react_agent(self.llm, self.tools, state_modifier=system_message)

    def process_query(self, query: str, tenant_id: int | None = None) -> str:
        results = self.retriever.search(query)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Financial Policy Context:\n{rag_context}\n\n"
            f"User Query: {query}\n"
            f"Target Tenant ID: {tenant_id if tenant_id else 'General'}"
        )

        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content