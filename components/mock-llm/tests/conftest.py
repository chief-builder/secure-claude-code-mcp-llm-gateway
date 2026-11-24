import os

# The app refuses to start without a credential, so set one before it is imported.
os.environ["MOCK_LLM_TOKEN"] = "local-mock-only"
