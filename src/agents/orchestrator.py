from __future__ import annotations

from typing import Annotated, Literal, TypedDict
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from src.rag.retriever import MultimodalRetriever
from src.agents.tenant_agent import TenantAgent
from src.agents.payment_agent import PaymentAgent
from src.agents.maintenance_agent import MaintenanceAgent
from src.agents.forecasting_agent import ForecastingAgent


# 1. Define the State
# This is the "shared memory" that flows through the graph
class AgentState(TypedDict):
    # add_messages allows the graph to append new messages to history
    messages: Annotated[list, add_messages]
    tenant_id: int | None
    unit_id: str | None
    intent: str | None
    final_response: str | None


# 2. The Orchestrator Class
class PropertyOrchestrator:
    """
    The central brain that routes user queries to the correct
    specialized agent based on intent analysis.
    """

    def __init__(
        self,
        retriever: MultimodalRetriever,
        model_name: str = "gpt-oss-120b",
    ):
        # Use Groq for the router for instant classification
        self.llm = ChatGroq(model=model_name)

        # Initialize all specialized agents (now using Groq internally)
        self.tenant_agent = TenantAgent(retriever, model_name=model_name)
        self.payment_agent = PaymentAgent(retriever, model_name=model_name)
        self.maintenance_agent = MaintenanceAgent(retriever, model_name=model_name)
        self.forecaster_agent = ForecastingAgent(retriever, model_name=model_name)

        # Build the graph
        self.graph = self._build_graph()
        self.memory = MemorySaver()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # Define the nodes
        workflow.add_node("router", self.route_intent)
        workflow.add_node("tenant_specialist", self.call_tenant_agent)
        workflow.add_node("payment_specialist", self.call_payment_agent)
        workflow.add_node("maintenance_specialist", self.call_maintenance_agent)
        workflow.add_node("forecasting_specialist", self.call_forecasting_agent)

        # Set the entry point
        workflow.set_entry_point("router")

        # Define the routing logic (Conditional Edges)
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "tenant": "tenant_specialist",
                "payment": "payment_specialist",
                "maintenance": "maintenance_specialist",
                "forecasting": "forecasting_specialist",
                "unknown": "tenant_specialist",  # Default to general support
            },
        )

        # All specialists lead to the end
        workflow.add_edge("tenant_specialist", END)
        workflow.add_edge("payment_specialist", END)
        workflow.add_edge("maintenance_specialist", END)
        workflow.add_edge("forecasting_specialist", END)

        return workflow.compile(checkpointer=self.memory)

    # --- Node Implementations ---

    def route_intent(self, state: AgentState):
        """Analyzes the last message to determine the best specialist agent."""
        last_message = state["messages"][-1].content if state["messages"] else ""

        prompt = (
            "You are an intent router for a property management system. "
            "Analyze the user's message and classify it into one of these categories:\n"
            "- 'tenant': General questions, lease details, or identity info.\n"
            "- 'payment': Rent payments, invoices, overdue balances, or late fees.\n"
            "- 'maintenance': Repair requests, leaking pipes, broken appliances, or scheduling.\n"
            "- 'forecasting': Future income, trends, or financial projections.\n\n"
            f"User Message: {last_message}\n\n"
            "Respond with ONLY the category name."
        )

        response = self.llm.invoke(prompt)
        intent = response.content.strip().lower()

        # Validation to ensure the LLM doesn't hallucinate a category
        valid_intents = ["tenant", "payment", "maintenance", "forecasting"]
        final_intent = intent if intent in valid_intents else "unknown"

        return {"intent": final_intent}

    def _route_decision(self, state: AgentState) -> str:
        """Edge function that tells LangGraph where to go next."""
        return state["intent"] or "unknown"

    def call_tenant_agent(self, state: AgentState):
        query = state["messages"][-1].content
        response = self.tenant_agent.ask(
            query=query,
            tenant_id=state.get("tenant_id")
        )
        return {"final_response": response}

    def call_payment_agent(self, state: AgentState):
        query = state["messages"][-1].content
        response = self.payment_agent.process_query(
            query=query,
            tenant_id=state.get("tenant_id")
        )
        return {"final_response": response}

    def call_maintenance_agent(self, state: AgentState):
        query = state["messages"][-1].content
        response = self.maintenance_agent.process_query(
            query=query,
            tenant_id=state.get("tenant_id")
        )
        return {"final_response": response}

    def call_forecasting_agent(self, state: AgentState):
        query = state["messages"][-1].content
        response = self.forecaster_agent.process_query(
            query=query
        )
        return {"final_response": response}

    def run(self, query: str, thread_id: str, tenant_id: int | None = None) -> str:
        """
        The main entry point for the system.
        thread_id: Used to remember the conversation for a specific user.
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Initial state
        initial_state = {
            "messages": [("user", query)],
            "tenant_id": tenant_id,
            "unit_id": None,
            "intent": None,
            "final_response": None
        }

        result = self.graph.invoke(initial_state, config=config)
        return result["final_response"]