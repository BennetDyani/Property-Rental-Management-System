from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.agents.tools import (
    log_maintenance_issue,
    get_maintenance_overview,
    get_tenant_details
)
from src.rag.retriever import MultimodalRetriever, prepare_rag_prompt


class MaintenanceAgent:
    """
    AI Agent specialized in repair coordination and issue tracking using a ReAct graph.
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
            log_maintenance_issue,
            get_maintenance_overview,
            get_tenant_details
        ]

        system_message = (
            "You are the Maintenance Coordinator. Your goal is to ensure "
            "property issues are logged quickly and resolved efficiently. "
            "You are proactive, helpful, and focused on urgency (e.g., water leaks are high priority). "
            "Always confirm the details of the issue before logging it."
        )

        self.agent = create_react_agent(self.llm, self.tools, prompt=system_message)

    def process_query(self, query: str, tenant_id: int | None = None) -> str:
        filters = {"tenant_id": tenant_id} if tenant_id is not None else None
        results = self.retriever.search(query, filters=filters)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Maintenance Procedure Context:\n{rag_context}\n\n"
            f"User Query: {query}\n"
            f"Target Tenant ID: {tenant_id if tenant_id else 'General'}"
        )

        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content