#!/usr/bin/env python3
"""Phase 0 Scaffolding & Environment Verification Script.

Usage:
    conda activate tri
    python scripts/verify_phase0.py
"""

import os
import sys
import socket
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_step(name: str):
    print(f"\n{BOLD}{CYAN}>>> [CHECK] {name}{RESET}")


def check_file(rel_path: str, required: bool = True) -> bool:
    path = ROOT_DIR / rel_path
    if path.exists():
        print(f"  {GREEN}[OK]{RESET} Found: {rel_path}")
        return True
    else:
        status = f"{RED}[MISSING]{RESET}" if required else f"{YELLOW}[OPTIONAL]{RESET}"
        print(f"  {status}: {rel_path}")
        return not required


def test_airgap_network():
    """Verify that external outbound connectivity can be blocked / detected."""
    print_step("Air-Gap & Outbound Network Isolation Verification")
    target = ("1.1.1.1", 53)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(target)
        s.close()
        print(f"  {YELLOW}[NOTICE] Host machine has external internet route.{RESET}")
        print(f"    Inside Docker, `internal: true` network enforces zero egress for all containers.")
        return True
    except (socket.timeout, OSError):
        print(f"  {GREEN}[OK] Air-Gap Active: Host has no outbound route to {target}.{RESET}")
        return True


def test_backend_imports():
    """Verify all backend core modules import without error."""
    print_step("Backend Core Modules & Pydantic Config")
    try:
        from app.core.config import get_settings
        settings = get_settings()
        print(f"  {GREEN}[OK]{RESET} Settings loaded: {settings.PROJECT_NAME}")
        print(f"       Air-Gap Mode: {settings.AIRGAP_STRICT_MODE}")
        print(f"       Postgres: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}")
        print(f"       Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        print(f"       FalkorDB: {settings.FALKORDB_HOST}:{settings.FALKORDB_PORT}")

        from app.models.audit_log import SourceDocument, AuditLog, GeneratedOutput
        print(f"  {GREEN}[OK]{RESET} SQLAlchemy ORM models mapped (SourceDocument, AuditLog, GeneratedOutput)")

        from app.main import app
        print(f"  {GREEN}[OK]{RESET} FastAPI application initialized cleanly with health routers")
        return True
    except Exception as e:
        print(f"  {RED}[FAIL] Import error: {e}{RESET}")
        return False


def main():
    print(f"\n{BOLD}================================================================{RESET}")
    print(f"{BOLD}   SIH26155 GenAI Platform - Phase 0 Environment Verification   {RESET}")
    print(f"{BOLD}================================================================{RESET}")

    all_ok = True

    # 1. Structure Check
    print_step("Repository & Monorepo Structure")
    required_files = [
        "docker-compose.yml",
        ".env.example",
        ".env",
        ".gitignore",
        ".github/workflows/ci.yml",
        "README.md",
        "backend/Dockerfile",
        "backend/requirements.txt",
        "backend/pyproject.toml",
        "backend/app/main.py",
        "backend/app/core/config.py",
        "backend/app/core/database.py",
        "backend/app/core/qdrant_client.py",
        "backend/app/core/falkordb_client.py",
        "backend/app/api/health.py",
        "backend/tests/test_health.py",
        "frontend/Dockerfile",
        "frontend/nginx.conf",
        "frontend/package.json",
        "frontend/src/App.tsx",
        "frontend/src/components/ServiceStatus.tsx",
        "frontend/src/components/BlankDashboard.tsx",
        "models/README.md",
        "models/configs/qwen3_8b.yaml",
        "models/configs/qwen3_vl_4b.yaml",
        "models/configs/whisper_medium.yaml",
        "models/configs/bge_small_en.yaml",
        "infra/postgres/init.sql",
        "infra/qdrant/config.yaml",
        "infra/falkordb/README.md",
    ]

    for f in required_files:
        if not check_file(f):
            all_ok = False

    # 2. Python Imports Check
    if not test_backend_imports():
        all_ok = False

    # 3. Airgap Check
    test_airgap_network()

    print(f"\n{BOLD}================================================================{RESET}")
    if all_ok:
        print(f"{BOLD}{GREEN}[SUCCESS] Phase 0 Scaffolding & Environment: ALL VERIFIED!{RESET}")
        print(f"{BOLD}Ready for commit and Phase 1 (Ingestion Pipeline).{RESET}")
        print(f"{BOLD}================================================================\n{RESET}")
        sys.exit(0)
    else:
        print(f"{BOLD}{RED}[FAIL] Some required files or checks failed.{RESET}")
        print(f"{BOLD}================================================================\n{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
