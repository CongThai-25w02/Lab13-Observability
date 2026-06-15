"""Quick connectivity test — run directly: python scripts/test_langfuse.py"""
from dotenv import load_dotenv
load_dotenv()

import os

host = os.getenv("LANGFUSE_HOST", "NOT SET")
pub  = os.getenv("LANGFUSE_PUBLIC_KEY", "NOT SET")
sec  = os.getenv("LANGFUSE_SECRET_KEY", "NOT SET")

print(f"HOST: {host}")
print(f"PUBLIC_KEY: {pub[:12]}..." if pub != "NOT SET" else "PUBLIC_KEY: NOT SET")
print(f"SECRET_KEY: {sec[:12]}..." if sec != "NOT SET" else "SECRET_KEY: NOT SET")
print()

from langfuse import Langfuse, get_client, observe

# Initialize singleton explicitly
lf = Langfuse(public_key=pub, secret_key=sec, host=host)
print(f"auth_check: {lf.auth_check()}")

# Test 1: low-level span
print("\n--- Test 1: low-level span ---")
try:
    with get_client().start_as_current_span("test-low-level") as span:
        get_client().update_current_trace(name="test-low-level", input={"test": True})
        print(f"trace_id: {get_client().get_current_trace_id()}")
    lf.flush()
    print("Flush OK — check Langfuse in 10s")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# Test 2: @observe() decorator
print("\n--- Test 2: @observe() decorator ---")
try:
    @observe()
    def ping():
        get_client().update_current_trace(name="test-observe")
        tid = get_client().get_current_trace_id()
        print(f"trace_id: {tid}")
        return "pong"

    result = ping()
    print(f"result: {result}")
    lf.flush()
    print("Flush OK")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
