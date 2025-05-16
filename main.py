#!/usr/bin/env python3
"""
PumpFun Bot - Main entry point for command-line application
"""
import sys
import asyncclick as click
import asyncio

from app.cli import main

if __name__ == "__main__":
    # Support Windows event loop policy
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if len(sys.argv) > 1 and sys.argv[1] == "start":
        asyncio.run(main())
    else:
        main()
