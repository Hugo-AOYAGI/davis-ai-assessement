import os

# The Agent Server graph module sets tracing up at import; tests must not send spans to Phoenix.
os.environ["AGENT_TRACING"] = "false"
