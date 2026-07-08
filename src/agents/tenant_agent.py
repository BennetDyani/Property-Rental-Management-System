from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agents.tools import (
    get_tenant_details,
    check_payment_status,
    log_maintenance_issue,
    get_maintenance_overview
)
from src.rag.retriever import MultimodalRetriever, prepare_rag_prompt


class TenantAgent:
    """
    An AI Agent specialized in tenant support using a ReAct graph.
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
            get_tenant_details,
            check_payment_status,
            log_maintenance_issue,
            get_maintenance_overview
        ]

        system_message = (
            "You are a professional Property Management Assistant. "
            "Your goal is to help tenants and landlords with property-related queries. "
            "You have access to a database of tenants, payments, and maintenance requests. "
            "You also have access to the property's official documents (leases, rules). "
            "Always be polite, concise, and cite your sources from documents when applicable."
        )

        # Modern LangGraph agent (Replaces AgentExecutor)
        self.agent = create_react_agent(self.llm, self.tools, prompt=system_message)

    def ask(self, query: str, tenant_id: int | None = None, context_filters: dict | None = None) -> str:
        # 1. RAG Step
        filters = dict(context_filters or {})
        if tenant_id is not None:
            filters["tenant_id"] = tenant_id
        results = self.retriever.search(query, filters=filters or None)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Document Context:\n{rag_context}\n\n"
            f"User Question: {query}\n"
            f"Current Tenant ID: {tenant_id if tenant_id else 'Unknown'}"
        )

        # Invoke the ReAct agent
        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content