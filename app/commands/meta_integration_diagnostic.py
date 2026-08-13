from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

from app.core.config import settings
from app.services.meta_integration_diagnostic import MetaDiagnostic


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose Meta WhatsApp Cloud API integration safely.")
    parser.add_argument("--send-test", action="store_true", help="send a test message to META_TEST_RECIPIENT_PHONE")
    parser.add_argument("--mode", choices=("text", "template"), default="text", help="diagnostic message mode")
    args = parser.parse_args(argv)
    diagnostic = MetaDiagnostic(httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)))
    try:
        return diagnostic.run(send_test=args.send_test, mode=args.mode)
    finally:
        diagnostic.close()


if __name__ == "__main__":
    sys.exit(main())
