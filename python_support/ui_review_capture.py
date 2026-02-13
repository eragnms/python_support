"""UI review capture module.

Captures screenshots at multiple viewports and runs Lighthouse audits
for use by the ui-reviewer Claude Code subagent. Install with
``pipx install .`` and use with ``ui-review-capture <url>``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_VIEWPORTS: list[tuple[int, int]] = [
    (1920, 1080),
    (768, 1024),
    (375, 812),
]

PROFILE_DIR: Path = Path.home() / ".local" / "share" / "ui-review-capture" / "profile"


def login_interactive(
    url: str,
    browser_type: str = "firefox",
    profile_dir: Path = PROFILE_DIR,
    ignore_ssl: bool = False,
) -> None:
    """Open a headed browser for manual login.

    The session is persisted to *profile_dir* so subsequent headless runs
    can access authenticated pages.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        launcher = getattr(pw, browser_type)
        context = launcher.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=ignore_ssl,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        print("Log in manually, then close the browser window to save the session.")
        page.wait_for_event("close", timeout=0)
        context.close()
    print(f"Session saved to {profile_dir}")


def capture_screenshots(
    url: str,
    viewports: list[tuple[int, int]],
    output_dir: Path,
    browser_type: str = "firefox",
    ignore_ssl: bool = False,
    profile_dir: Path | None = None,
) -> list[Path]:
    """Take full-page screenshots at each viewport size.

    When *profile_dir* is given, uses a persistent context that shares
    cookies/localStorage from a previous ``--login`` session.

    Returns the list of saved screenshot paths.
    """
    paths: list[Path] = []
    with sync_playwright() as pw:
        launcher = getattr(pw, browser_type)

        if profile_dir and profile_dir.is_dir():
            # Persistent context — reuses login session
            context = launcher.launch_persistent_context(
                str(profile_dir),
                headless=True,
                viewport={"width": viewports[0][0], "height": viewports[0][1]},
                device_scale_factor=1,
                ignore_https_errors=ignore_ssl,
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(500)

            dest = output_dir / f"screenshot-{viewports[0][0]}x{viewports[0][1]}.png"
            page.screenshot(path=str(dest), full_page=True)
            paths.append(dest)

            # Remaining viewports — resize the same page
            for width, height in viewports[1:]:
                page.set_viewport_size({"width": width, "height": height})
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(500)
                dest = output_dir / f"screenshot-{width}x{height}.png"
                page.screenshot(path=str(dest), full_page=True)
                paths.append(dest)

            context.close()
        else:
            # Ephemeral contexts — no saved session
            browser = launcher.launch(headless=True)
            for width, height in viewports:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,
                    ignore_https_errors=ignore_ssl,
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(500)

                filename = f"screenshot-{width}x{height}.png"
                dest = output_dir / filename
                page.screenshot(path=str(dest), full_page=True)
                paths.append(dest)
                context.close()
            browser.close()
    return paths


def _find_chrome() -> str | None:
    """Locate a Chrome/Chromium binary for Lighthouse.

    Checks the system PATH first, then falls back to the Playwright-managed
    Chromium installation.
    """
    for name in ("google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path

    # Fall back to Playwright-managed Chromium
    pw_dir = Path.home() / ".cache" / "ms-playwright"
    if pw_dir.is_dir():
        candidates = sorted(pw_dir.glob("chromium-*/chrome-linux64/chrome"))
        if candidates:
            return str(candidates[-1])
    return None


def run_lighthouse(url: str, output_dir: Path, ignore_ssl: bool = False) -> Path | None:
    """Run Lighthouse CLI and save the JSON report.

    Returns the report path, or ``None`` if lighthouse is not installed.
    """
    lighthouse_bin = shutil.which("lighthouse")
    if lighthouse_bin is None:
        print("Warning: lighthouse not found in PATH, skipping audit.")
        return None

    env = dict(os.environ)
    if "CHROME_PATH" not in env:
        chrome = _find_chrome()
        if chrome:
            env["CHROME_PATH"] = chrome
        else:
            print("Warning: no Chrome/Chromium binary found, skipping audit.")
            return None

    chrome_flags = "--headless=new --no-sandbox"
    if ignore_ssl:
        chrome_flags += " --ignore-certificate-errors"

    report_path = output_dir / "lighthouse-report.json"
    cmd: list[str] = [
        lighthouse_bin,
        url,
        "--output=json",
        f"--output-path={report_path}",
        f"--chrome-flags={chrome_flags}",
        "--only-categories=performance,accessibility,best-practices,seo",
        "--quiet",
    ]
    try:
        subprocess.run(cmd, check=True, timeout=120, env=env)
    except FileNotFoundError:
        print("Warning: lighthouse not found, skipping audit.")
        return None
    except subprocess.TimeoutExpired:
        print("Warning: lighthouse timed out after 120s, skipping audit.")
        return None
    except subprocess.CalledProcessError as exc:
        print(f"Warning: lighthouse exited with code {exc.returncode}.")
        return None

    if report_path.exists():
        return report_path
    return None


def _lighthouse_summary(report_path: Path) -> str:
    """Extract category scores from a Lighthouse JSON report."""
    data = json.loads(report_path.read_text())
    categories = data.get("categories", {})
    lines: list[str] = []
    for key in ("performance", "accessibility", "best-practices", "seo"):
        cat = categories.get(key)
        if cat:
            score = cat.get("score")
            display = f"{int(score * 100)}" if score is not None else "n/a"
            lines.append(f"  {cat.get('title', key)}: {display}")
    return "\n".join(lines)


def write_summary(
    output_dir: Path,
    url: str,
    screenshot_paths: list[Path],
    lighthouse_path: Path | None,
) -> Path:
    """Write a human-readable summary.txt to the output directory."""
    lines: list[str] = [
        f"UI Review Capture — {url}",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "Screenshots:",
    ]
    for p in screenshot_paths:
        lines.append(f"  {p}")

    if lighthouse_path and lighthouse_path.exists():
        lines.append("")
        lines.append("Lighthouse scores:")
        lines.append(_lighthouse_summary(lighthouse_path))
    else:
        lines.append("")
        lines.append("Lighthouse: skipped (not installed or failed)")

    lines.append("")
    summary_path = output_dir / "summary.txt"
    summary_path.write_text("\n".join(lines))
    return summary_path


def main() -> None:
    """CLI entry point for ui-review-capture."""
    parser = argparse.ArgumentParser(
        description="Capture screenshots and run Lighthouse for UI review.",
    )
    parser.add_argument("url", help="URL to capture")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: /tmp/ui-review-<timestamp>)",
    )
    parser.add_argument(
        "--viewports",
        nargs="+",
        default=None,
        help="Viewport sizes as WxH (e.g. 1920x1080 768x1024)",
    )
    parser.add_argument(
        "--browser",
        choices=["firefox", "chromium", "webkit"],
        default="firefox",
        help="Browser engine to use (default: firefox)",
    )
    parser.add_argument(
        "--ignore-ssl",
        action="store_true",
        help="Ignore SSL certificate errors (useful for self-signed certs)",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open a headed browser to log in manually and save the session",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=PROFILE_DIR,
        help=f"Profile directory for persistent sessions (default: {PROFILE_DIR})",
    )
    parser.add_argument(
        "--no-lighthouse",
        action="store_true",
        help="Skip the Lighthouse audit",
    )
    args = parser.parse_args()

    try:
        _run(args)
    except Exception as exc:
        msg = str(exc)
        if "SSL_ERROR" in msg or "ERR_CERT" in msg:
            print(f"Error: SSL certificate problem — {msg.splitlines()[0]}")
            print()
            print("Try adding --ignore-ssl to bypass certificate checks:")
            cmd = " ".join(sys.argv) + " --ignore-ssl"
            print(f"  {cmd}")
            sys.exit(1)
        raise


def _run(args: argparse.Namespace) -> None:
    """Execute the capture workflow."""
    # Login mode — open headed browser and exit
    if args.login:
        login_interactive(
            args.url,
            browser_type=args.browser,
            profile_dir=args.profile,
            ignore_ssl=args.ignore_ssl,
        )
        return

    # Resolve output directory
    output_dir: Path = args.output_dir or Path(f"/tmp/ui-review-{int(time.time())}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse viewports
    viewports = DEFAULT_VIEWPORTS
    if args.viewports:
        viewports = []
        for v in args.viewports:
            parts = v.lower().split("x")
            if len(parts) != 2:
                print(f"Invalid viewport format: {v} (expected WxH)")
                sys.exit(1)
            viewports.append((int(parts[0]), int(parts[1])))

    print(f"Output directory: {output_dir}")

    # Screenshots
    print(f"Capturing screenshots at {len(viewports)} viewport(s)...")
    screenshot_paths = capture_screenshots(
        args.url,
        viewports,
        output_dir,
        browser_type=args.browser,
        ignore_ssl=args.ignore_ssl,
        profile_dir=args.profile,
    )
    for p in screenshot_paths:
        print(f"  Saved {p.name}")

    # Lighthouse
    lighthouse_path: Path | None = None
    if not args.no_lighthouse:
        print("Running Lighthouse audit...")
        lighthouse_path = run_lighthouse(
            args.url, output_dir, ignore_ssl=args.ignore_ssl
        )
        if lighthouse_path:
            print(f"  Saved {lighthouse_path.name}")

    # Summary
    summary = write_summary(output_dir, args.url, screenshot_paths, lighthouse_path)
    print(f"Summary written to {summary}")
    print("Done.")


if __name__ == "__main__":
    main()
