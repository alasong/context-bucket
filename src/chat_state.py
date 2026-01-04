from typing import TypedDict, Annotated, List, Any
from langchain_core.messages import BaseMessage
import operator

def merge_messages(left: list[BaseMessage], right: list[BaseMessage]) -> list[BaseMessage]:
    """Append messages."""
    return left + right

class ChatState(TypedDict):
    # Standard LangGraph message history
    messages: Annotated[List[BaseMessage], merge_messages]
    
    # System prompt
    system: str
    
    # Context buckets
    context_policies: List[str]
    context_facts: List[str]
    context_instructions: List[str]
    context_examples: List[str]
    context_priority: List[str]
    
    # Legacy flat context support
    context: List[str]
    
    # Procedure control
    procedure_enabled: bool
    procedure_steps: List[str]
    procedure_step: int
