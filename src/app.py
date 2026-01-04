from langchain_core.messages import ToolMessage

def _invoke_tool(tool, args):
    """
    Invoke a tool with given arguments.
    Supports both LangChain tools and simple callables.
    """
    try:
        if hasattr(tool, "invoke"):
            return tool.invoke(args)
        elif callable(tool):
            return tool(**args)
        else:
            return f"Error: Tool {tool} is not callable"
    except Exception as e:
        return f"Error executing tool: {str(e)}"
