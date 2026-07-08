"""Shared test configuration.

Settings requires env vars at import time in some modules; provide safe
dummies so pure-logic tests can import app code without a real environment.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("SMTP_HOST", "smtp.test")
os.environ.setdefault("SMTP_USERNAME", "test@test")
os.environ.setdefault("SMTP_PASSWORD", "test")
os.environ.setdefault("NOTIFICATION_EMAIL", "test@test")
os.environ.setdefault("LLM_API_KEY", "test-key")
