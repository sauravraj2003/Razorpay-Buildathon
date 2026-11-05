"""LangGraph StateGraph compilation for Multi-Agent Commerce Platform."""
from typing import Optional, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgenticCommerceState
from graph.edges import route_from_orchestrator
from agents.orchestrator import orchestrator_node
from agents.buyer import buyer_node
from agents.checkout import checkout_node
from agents.upsell import upsell_node

def build_commerce_graph(interrupt_nodes: Optional[List[str]] = None):
    """
    Constructs the 4-agent LangGraph StateGraph:
    User Input -> Orchestrator -> (Buyer | Checkout | Upsell) -> END
    """
    workflow = StateGraph(AgenticCommerceState)

    # Register Nodes
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("buyer", buyer_node)
    workflow.add_node("checkout", checkout_node)
    workflow.add_node("upsell", upsell_node)

    # Define Edges
    workflow.add_edge(START, "orchestrator")
    
    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "buyer": "buyer",
            "checkout": "checkout",
            "upsell": "upsell",
            "__end__": END
        }
    )

    workflow.add_edge("buyer", END)
    workflow.add_edge("checkout", END)
    workflow.add_edge("upsell", END)

    checkpointer = MemorySaver()
    
    compile_kwargs = {"checkpointer": checkpointer}
    if interrupt_nodes:
        compile_kwargs["interrupt_before"] = interrupt_nodes

    app = workflow.compile(**compile_kwargs)
    return app

# Singleton compiled app instance with thread memory
commerce_graph = build_commerce_graph()
