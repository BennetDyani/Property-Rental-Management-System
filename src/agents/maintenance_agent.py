from __future__ import annotations

from typing import Any
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

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
            model_name: str = "gpt-oss-120b",
    ):
        self.retriever = retriever
        self.llm = ChatGroq(model=model_name)

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

        self.agent = create_react_agent(self.llm, self.tools, state_modifier=system_message)

    def process_query(self, query: str, tenant_id: int | None = None) -> str:
        results = self.retriever.search(query)
        rag_context = prepare_rag_prompt(query, results)

        enhanced_input = (
            f"Maintenance Procedure Context:\n{rag_context}\n\n"
            f"User Query: {query}\n"
            f"Target Tenant ID: {tenant_id if tenant_id else 'General'}"
        )

        response = self.agent.invoke({"messages": [("user", enhanced_input)]})
        return response["messages"][-1].content