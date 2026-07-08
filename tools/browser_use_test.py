#!/usr/bin/env python3
"""Browser-use smoke test for AirAsia AK1511 flight status.

Run with the browser-use virtualenv that already exists on the machine:
  DEEPSEEK_API_KEY=... ~/browser-use-env/bin/python tools/browser_use_test.py

The script prints the page-visible status text returned by the browser-use
agent, or a clear "查無資料" result if the page does not show a flight record.
"""

from __future__ import annotations

import asyncio
import os
import sys


AIRASIA_STATUS_URL = "https://www.airasia.com/flightstatus/zh/tw"
DEFAULT_FLIGHT_NO = "AK1511"
DEFAULT_FLIGHT_DATE = "2026-07-10"


async def run_browser_use(flight_no: str, flight_date: str) -> str:
    os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

    from browser_use import Agent, BrowserProfile
    from browser_use.llm.deepseek.chat import ChatDeepSeek

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required")

    llm = ChatDeepSeek(
        model="deepseek-chat",
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=0,
        timeout=90,
    )
    browser_profile = BrowserProfile(
        headless=True,
        allowed_domains=["https://www.airasia.com/*", "https://flightstatusv5.airasia.com/*"],
        viewport={"width": 1366, "height": 900},
        keep_alive=False,
    )
    task = f"""
開啟 {AIRASIA_STATUS_URL}。
查詢 AirAsia 航班 {flight_no}，日期 {flight_date}。

請只回覆頁面查詢結果中顯示的航班狀態文字，例如 On Time、Delayed、Cancelled。
如果頁面沒有結果或無法確認，請只回覆「查無資料」。
不要解釋流程，不要輸出 JSON。
"""
    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=browser_profile,
        use_vision=False,
        max_failures=2,
        max_actions_per_step=3,
        llm_timeout=90,
        step_timeout=90,
    )
    history = await agent.run(max_steps=12)
    return (history.final_result() or "查無資料").strip()


def main() -> int:
    flight_no = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FLIGHT_NO
    flight_date = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_FLIGHT_DATE
    result = asyncio.run(run_browser_use(flight_no.upper(), flight_date))
    print(result or "查無資料")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
