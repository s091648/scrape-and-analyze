import os

# Set a consistent test secret for all JWT-related tests
os.environ["NEXTAUTH_SECRET"] = "test-secret"
