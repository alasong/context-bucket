import os
import sys
from contextmgr import load_context_app, SessionManager
from src.runtime import send_user_message, get_state
from src.tools import strlen
GLOBAL_DS = None

def print_context(values: dict):
    print("\n" + "="*20 + " CURRENT CONTEXT " + "="*20)
    
    print(f"[System]: {values.get('system', 'N/A')}")
    priority = values.get('context_priority') or ["policies", "facts", "instructions", "examples"]
    print(f"[Priority]: {', '.join(priority)}")
    proc_enabled = bool(values.get('procedure_enabled') or False)
    steps = values.get('procedure_steps') or []
    step_idx = values.get('procedure_step') or 0
    print(f"[Procedure]: enabled={proc_enabled}, step={step_idx}/{len(steps)}")
    
    for bucket in ['policies', 'facts', 'instructions', 'examples']:
        key = f'context_{bucket}'
        items = values.get(key, [])
        if items:
            print(f"\n[{bucket.capitalize()}]:")
            for item in items:
                print(f"  - {str(item)}")
    merged = values.get('context') or []
    if merged:
        print("\n[Merged Context]:")
        for item in merged:
            print(f"  - {str(item)}")
    if GLOBAL_DS is not None:
        sticky = GLOBAL_DS.sticky()
        if sticky:
            print("\n[Sticky Docs]:")
            for s in sticky:
                print(f"  - {str(s)}")
                
    print("\n[History (Last 5 Messages)]:")
    msgs = values.get('messages', [])
    for m in msgs[-5:]:
        role = getattr(m, 'type', 'unknown')
        content = getattr(m, 'content', str(m))
        print(f"  {role}: {content}")
    
    print("="*57 + "\n")

def main():
    print("Initializing Chat CLI...")
    
    # 1. Load the app
    try:
        # Use a default model if not configured, e.g., 'qwen-plus'
        # Ensure 'DASHSCOPE_API_KEY' is set in environment or .env
        app, seed, ds = load_context_app("configs/context.yaml", tools=[strlen])
        globals()['GLOBAL_DS'] = ds
    except Exception as e:
        print(f"Error loading app: {e}")
        print("Make sure 'configs/context.yaml' exists and dependencies are installed.")
        return

    # 2. Setup session
    sm = SessionManager()
    user_id = "cli_user"
    tid = sm.thread_for(user_id)
    
    # 3. Seed initial state
    seed(tid)
    print(f"Session started for user: {user_id} (Thread ID: {tid})")
    print("Type 'exit' or 'quit' to end session.")
    print("Type '/context' to view current context state.")
    print("-" * 50)

    # 4. Chat loop
    while True:
        try:
            user_input = input("User> ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break
            
            if user_input.lower() == "/context":
                st = get_state(app, tid)
                if st and st.values:
                    print_context(st.values)
                else:
                    print("Context is empty or state unavailable.")
                continue
                
            # Send message
            send_user_message(app, tid, user_input)
            
            # Get response
            st = get_state(app, tid)
            if st and st.values and "messages" in st.values:
                msgs = st.values["messages"]
                if msgs:
                    last_msg = msgs[-1]
                    content = getattr(last_msg, "content", str(last_msg))
                    print(f"AI> {content}")
                else:
                    print("AI> (No response messages)")
            else:
                print("AI> (No state returned)")
                
        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error during chat: {e}")

if __name__ == "__main__":
    main()
