import os

# Set a consistent test secret for all JWT-related tests
os.environ.setdefault("NEXTAUTH_SECRET", "test-secret")
