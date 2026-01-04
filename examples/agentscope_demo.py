try:
    import agentscope as ags
except ImportError:
    ags = None
from contextmgr import load_context_app, SessionManager
from src.runtime import send_user_message, get_state
from src.tools import strlen

def main():
    if ags is None:
        print("agentscope not installed; run: python -m pip install agentscope")
        return
    app, seed, ds = load_context_app("configs/context.yaml", tools=[strlen])
    sm = SessionManager()

    class ContextAwareAgent(ags.Agent):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
        def reply(self, x):
            user_id = x.get("user_id", "anon")
            tid = sm.thread_for(user_id)
            seed(tid)
            send_user_message(app, tid, str(x.get("text", "")))
            st = get_state(app, tid)
            msgs = st.values.get("messages") or []
            ai = msgs[-1]
            return {"text": str(getattr(ai, "content", ai))}

    agent = ContextAwareAgent(name="assistant")
    env = ags.Environment()
    env.register(agent)
    print(env.step({"agent_name": "assistant", "messages": [{"text": "你好", "user_id": "u1"}]}))
    print(env.step({"agent_name": "assistant", "messages": [{"text": "who are u", "user_id": "u2"}]}))

if __name__ == "__main__":
    main()

