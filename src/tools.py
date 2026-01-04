from langchain_core.tools import tool

@tool
def strlen(text: str) -> int:
    """Returns the length of the input text."""
    return len(text)
