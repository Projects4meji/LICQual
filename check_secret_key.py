#!/usr/bin/env python
"""
Quick script to check SECRET_KEY configuration
"""
from decouple import Config, RepositoryEnv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
config = Config(RepositoryEnv(str(BASE_DIR / '.env')))

ENV = config("ENV", default="dev")
SECRET_KEY = config('SECRET_KEY', default=None)

print("=" * 60)
print("SECRET_KEY DIAGNOSTIC")
print("=" * 60)
print(f"ENV from .env: {ENV}")
print(f"SECRET_KEY from .env: {'SET' if SECRET_KEY else 'NOT SET'}")
if SECRET_KEY:
    print(f"  First 20 chars: {SECRET_KEY[:20]}...")
else:
    print("  Using fallback: 'dev-insecure-key-for-local-only'")
print()
print("To fix: Add SECRET_KEY to your .env file with the production value")
print("=" * 60)

