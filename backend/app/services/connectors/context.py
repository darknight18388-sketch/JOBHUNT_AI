from contextvars import ContextVar

# Set by the search endpoint so connectors that must send the end-user's IP/user-agent can read them.
client_context: ContextVar[dict] = ContextVar("client_context", default={})
