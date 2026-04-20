"""Interactive browser session for UI testing.

Provides a persistent browser session that an AI agent can drive step-by-step:
open pages, click elements, fill forms, take screenshots, and inspect state.

Each command writes a screenshot to the session output directory so the agent
can observe the result. Install with ``pipx install .`` and use with
``ui-browser <command> [options]``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import cast

from playwright.sync_api import Browser, BrowserContext, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

SESSION_DIR: Path = Path("/tmp/ui-browser-session")
STATE_FILE: str = "session-state.json"
PROFILE_DIR: Path = Path.home() / ".local" / "share" / "ui-review-capture" / "profile"
DEFAULT_TIMEOUT: int = 10_000


def _state_path(session_dir: Path) -> Path:
    return session_dir / STATE_FILE


def _load_state(session_dir: Path) -> dict[str, object]:
    p = _state_path(session_dir)
    if p.exists():
        return json.loads(p.read_text())  # type: ignore[no-any-return]
    return {}


def _save_state(session_dir: Path, state: dict[str, object]) -> None:
    _state_path(session_dir).write_text(json.dumps(state, indent=2))


def _screenshot_path(session_dir: Path, step: int) -> Path:
    return session_dir / f"step-{step:04d}.png"


def _run_with_page(
    session_dir: Path,
    browser_type: str,
    ignore_ssl: bool,
    viewport: tuple[int, int],
    callback: object,
) -> None:
    """Launch browser, restore state, run callback, save state, close."""
    session_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(session_dir)
    step = cast(int, state.get("step", 0)) + 1

    profile_dir = PROFILE_DIR if PROFILE_DIR.is_dir() else None

    with sync_playwright() as pw:
        launcher = getattr(pw, browser_type)

        context: BrowserContext
        browser: Browser | None = None

        if profile_dir:
            context = launcher.launch_persistent_context(
                str(profile_dir),
                headless=True,
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=1,
                ignore_https_errors=ignore_ssl,
            )
        else:
            browser = launcher.launch(headless=True)
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                device_scale_factor=1,
                ignore_https_errors=ignore_ssl,
            )

        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        # Restore last URL if we have one and callback doesn't navigate itself
        last_url = state.get("url")
        if last_url and not state.get("_skip_restore"):
            try:
                page.goto(str(last_url), wait_until="networkidle", timeout=15_000)
            except PlaywrightTimeout:
                page.goto(str(last_url), wait_until="load", timeout=15_000)

        # Run the actual command
        assert callable(callback)
        result_info = callback(page, state, step)

        # Take screenshot
        ss_path = _screenshot_path(session_dir, step)
        page.screenshot(path=str(ss_path), full_page=True)

        # Update state
        state["step"] = step
        state["url"] = page.url
        state["title"] = page.title()
        state["screenshot"] = str(ss_path)
        state["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
        if isinstance(result_info, dict):
            state["last_result"] = result_info
        else:
            state.pop("last_result", None)
        state.pop("_skip_restore", None)
        _save_state(session_dir, state)

        # Print result for agent to parse
        print(f"Step: {step}")
        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        print(f"Screenshot: {ss_path}")
        if isinstance(result_info, dict):
            for k, v in result_info.items():
                print(f"{k}: {v}")

        context.close()
        if browser:
            browser.close()


def cmd_open(args: argparse.Namespace) -> None:
    """Open a URL."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        try:
            page.goto(args.url, wait_until="networkidle", timeout=15_000)
        except PlaywrightTimeout:
            page.goto(args.url, wait_until="load", timeout=15_000)

    state = _load_state(args.session_dir)
    state["_skip_restore"] = True
    _save_state(args.session_dir, state)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_click(args: argparse.Namespace) -> None:
    """Click an element."""

    def _action(
        page: Page, state: dict[str, object], step: int
    ) -> dict[str, str] | None:
        try:
            page.click(args.selector, timeout=DEFAULT_TIMEOUT)
            page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeout:
            pass
        page.wait_for_timeout(300)
        return None

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_fill(args: argparse.Namespace) -> None:
    """Fill a form field."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        page.fill(args.selector, args.value, timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(200)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_select(args: argparse.Namespace) -> None:
    """Select an option from a dropdown."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        page.select_option(args.selector, args.value, timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(200)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_screenshot(args: argparse.Namespace) -> None:
    """Take a screenshot without interaction."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        page.wait_for_timeout(300)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_text(args: argparse.Namespace) -> None:
    """Extract visible text from the page or a specific element."""

    def _action(page: Page, state: dict[str, object], step: int) -> dict[str, str]:
        if args.selector:
            el = page.query_selector(args.selector)
            text = el.inner_text() if el else "(element not found)"
        else:
            text = page.inner_text("body")
        # Truncate to avoid flooding the agent context
        if len(text) > 4000:
            text = text[:4000] + "\n... (truncated)"
        return {"text": text}

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_links(args: argparse.Namespace) -> None:
    """List all links on the page."""

    def _action(page: Page, state: dict[str, object], step: int) -> dict[str, str]:
        links = page.eval_on_selector_all(
            "a[href]",
            """els => els.map(e => ({
                text: e.innerText.trim().substring(0, 80),
                href: e.href
            }))""",
        )
        lines = []
        for link in links:
            text = link.get("text", "").replace("\n", " ").strip()
            href = link.get("href", "")
            if text or href:
                lines.append(f"  {text or '(no text)'} -> {href}")
        return {"links": "\n".join(lines) if lines else "(no links found)"}

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_forms(args: argparse.Namespace) -> None:
    """List all form elements on the page."""

    def _action(page: Page, state: dict[str, object], step: int) -> dict[str, str]:
        elements = page.eval_on_selector_all(
            "input, select, textarea, button",
            """els => els.map(e => ({
                tag: e.tagName.toLowerCase(),
                type: e.type || '',
                name: e.name || '',
                id: e.id || '',
                placeholder: e.placeholder || '',
                value: e.value || '',
                text: e.tagName === 'BUTTON' || e.tagName === 'SELECT'
                    ? e.innerText.trim().substring(0, 60) : '',
                disabled: e.disabled
            }))""",
        )
        lines = []
        for el in elements:
            parts = [el["tag"]]
            if el.get("type"):
                parts.append(f'type="{el["type"]}"')
            if el.get("name"):
                parts.append(f'name="{el["name"]}"')
            if el.get("id"):
                parts.append(f'id="{el["id"]}"')
            if el.get("placeholder"):
                parts.append(f'placeholder="{el["placeholder"]}"')
            if el.get("value"):
                parts.append(f'value="{el["value"]}"')
            if el.get("text"):
                parts.append(f'text="{el["text"]}"')
            if el.get("disabled"):
                parts.append("DISABLED")
            lines.append("  " + " ".join(parts))
        return {
            "form_elements": "\n".join(lines) if lines else "(no form elements found)"
        }

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_eval(args: argparse.Namespace) -> None:
    """Evaluate JavaScript in the page context."""

    def _action(page: Page, state: dict[str, object], step: int) -> dict[str, str]:
        result = page.evaluate(args.expression)
        return {"result": str(result)}

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_hover(args: argparse.Namespace) -> None:
    """Hover over an element."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        page.hover(args.selector, timeout=DEFAULT_TIMEOUT)
        page.wait_for_timeout(500)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_press(args: argparse.Namespace) -> None:
    """Press a keyboard key."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        if args.selector:
            page.press(args.selector, args.key, timeout=DEFAULT_TIMEOUT)
        else:
            page.keyboard.press(args.key)
        page.wait_for_timeout(300)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_wait(args: argparse.Namespace) -> None:
    """Wait for an element to appear."""

    def _action(page: Page, state: dict[str, object], step: int) -> dict[str, str]:
        try:
            page.wait_for_selector(
                args.selector, state="visible", timeout=args.timeout_ms
            )
            return {"waited_for": args.selector, "found": "true"}
        except PlaywrightTimeout:
            return {"waited_for": args.selector, "found": "false"}

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_back(args: argparse.Namespace) -> None:
    """Go back in browser history."""

    def _action(page: Page, state: dict[str, object], step: int) -> None:
        page.go_back(wait_until="networkidle", timeout=10_000)
        page.wait_for_timeout(300)

    _run_with_page(
        args.session_dir,
        args.browser,
        args.ignore_ssl,
        args.viewport_tuple,
        _action,
    )


def cmd_reset(args: argparse.Namespace) -> None:
    """Reset the session (delete state and screenshots)."""
    import shutil

    if args.session_dir.exists():
        shutil.rmtree(args.session_dir)
        print(f"Session cleared: {args.session_dir}")
    else:
        print("No active session to clear.")


def _parse_viewport(s: str) -> tuple[int, int]:
    parts = s.lower().split("x")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Invalid viewport: {s} (expected WxH)")
    return (int(parts[0]), int(parts[1]))


def main() -> None:
    """CLI entry point for ui-browser."""
    parser = argparse.ArgumentParser(
        description="Interactive browser session for AI-driven UI testing.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=SESSION_DIR,
        help=f"Session directory (default: {SESSION_DIR})",
    )
    parser.add_argument(
        "--browser",
        choices=["firefox", "chromium", "webkit"],
        default="firefox",
        help="Browser engine (default: firefox)",
    )
    parser.add_argument(
        "--ignore-ssl",
        action="store_true",
        help="Ignore SSL certificate errors",
    )
    parser.add_argument(
        "--viewport",
        default="1920x1080",
        help="Viewport size as WxH (default: 1920x1080)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # open
    p_open = sub.add_parser("open", help="Navigate to a URL")
    p_open.add_argument("url", help="URL to open")

    # click
    p_click = sub.add_parser("click", help="Click an element")
    p_click.add_argument(
        "selector", help="CSS selector, text selector, or Playwright locator"
    )

    # fill
    p_fill = sub.add_parser("fill", help="Fill a form field")
    p_fill.add_argument("selector", help="Field selector")
    p_fill.add_argument("value", help="Value to type")

    # select
    p_select = sub.add_parser("select", help="Select dropdown option")
    p_select.add_argument("selector", help="Select element selector")
    p_select.add_argument("value", help="Option value to select")

    # screenshot
    sub.add_parser("screenshot", help="Take a screenshot")

    # text
    p_text = sub.add_parser("text", help="Extract visible text")
    p_text.add_argument(
        "selector", nargs="?", default=None, help="Element selector (default: body)"
    )

    # links
    sub.add_parser("links", help="List all links on the page")

    # forms
    sub.add_parser("forms", help="List all form elements")

    # eval
    p_eval = sub.add_parser("eval", help="Evaluate JavaScript")
    p_eval.add_argument("expression", help="JS expression to evaluate")

    # hover
    p_hover = sub.add_parser("hover", help="Hover over an element")
    p_hover.add_argument("selector", help="Element selector")

    # press
    p_press = sub.add_parser("press", help="Press a keyboard key")
    p_press.add_argument("key", help="Key to press (e.g. Enter, Tab, Escape)")
    p_press.add_argument(
        "selector", nargs="?", default=None, help="Optional element to focus first"
    )

    # wait
    p_wait = sub.add_parser("wait", help="Wait for element to appear")
    p_wait.add_argument("selector", help="Element selector")
    p_wait.add_argument(
        "--timeout", dest="timeout_ms", type=int, default=10000, help="Timeout in ms"
    )

    # back
    sub.add_parser("back", help="Go back in browser history")

    # reset
    sub.add_parser("reset", help="Clear session state and screenshots")

    args = parser.parse_args()
    args.viewport_tuple = _parse_viewport(args.viewport)

    # Ensure session dir exists for state operations
    args.session_dir.mkdir(parents=True, exist_ok=True)

    cmd_map = {
        "open": cmd_open,
        "click": cmd_click,
        "fill": cmd_fill,
        "select": cmd_select,
        "screenshot": cmd_screenshot,
        "text": cmd_text,
        "links": cmd_links,
        "forms": cmd_forms,
        "eval": cmd_eval,
        "hover": cmd_hover,
        "press": cmd_press,
        "wait": cmd_wait,
        "back": cmd_back,
        "reset": cmd_reset,
    }

    handler = cmd_map.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
