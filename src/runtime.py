from langchain_core.messages import HumanMessage
from src.chat_state import ChatState

def send_user_message(app, thread_id: str, text: str):
    """
    Send a user message to the LangGraph app.
    """
    config = {"configurable": {"thread_id": thread_id}}
    app.invoke(
        {"messages": [HumanMessage(content=text)]},
        config=config
    )

def get_state(app, thread_id: str):
    """
    Get the current state of the thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    return app.get_state(config)
