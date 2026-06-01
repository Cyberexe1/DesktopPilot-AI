"""Test: Open Notepad and type a letter into it."""
import asyncio
import sys
import time
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from automation.executor import execute_task

async def main():
    # Step 1: Open Notepad
    print("Opening Notepad...")
    r1 = await execute_task({"tool": "open_application", "name": "notepad"})
    print(f"  Result: {r1}")

    # Wait for Notepad to open and gain focus
    time.sleep(2)

    # Step 2: Type text
    letter = "Dear Boss,\n\nI will be on leave tomorrow due to personal reasons.\nPlease approve my leave request.\n\nThank you,\nRegards"
    print("Typing letter...")
    r2 = await execute_task({"tool": "type_text", "text": letter})
    print(f"  Result: {r2}")

    print("\nDone! Check Notepad on your screen.")

asyncio.run(main())
