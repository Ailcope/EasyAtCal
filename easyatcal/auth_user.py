from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easyatcal.config import EasyAtWorkAuth


class PlaywrightMissingError(RuntimeError):
    """Raised when auth_mode=user is configured but Playwright is not installed."""


class LoginError(RuntimeError):
    """Raised when headless login fails (wrong selector, creds, etc.)."""


def do_login(
    cfg: EasyAtWorkAuth,
    password: str,
    storage_path: Path,
    extra_wait_selector: str | None = None,
) -> None:
    """Drive a headless browser through the easy@work login form,
    then persist the storage_state to ``storage_path``.

    ``extra_wait_selector`` is an optional CSS selector to wait for after
    form submit — useful when the post-login page has a known landmark
    (e.g. ``nav[data-testid='app-shell']``). Defaults to a generic
    ``networkidle`` wait.
    """
    try:
        from playwright.sync_api import (
            TimeoutError as PWTimeout,
        )
        from playwright.sync_api import (
            sync_playwright,
        )
    except ImportError as e:  # pragma: no cover — platform guard
        raise PlaywrightMissingError(
            "Playwright not installed. Run: pip install 'easyatcal[playwright]' "
            "&& playwright install chromium"
        ) from e

    if cfg.email is None:
        raise LoginError("no email configured in easyatwork.email")

    storage_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=cfg.headless)
        try:
            context = browser.new_context()
            page = context.new_page()
            
            discovered_meta: dict[str, str | int] = {}
            import re

            def on_request(request):
                match = re.search(r"^(https?://[^/]+)/customers/(\d+)/employees/(\d+)", request.url)
                if match:
                    discovered_meta["api_url"] = match.group(1)
                    discovered_meta["customer_id"] = int(match.group(2))
                    discovered_meta["employee_id"] = int(match.group(3))

            page.on("request", on_request)

            page.goto(cfg.login_url, wait_until="domcontentloaded")

            try:
                page.wait_for_selector(cfg.email_selector, timeout=cfg.login_timeout_ms)
            except PWTimeout as e:
                raise LoginError(
                    f"login form not found at {cfg.login_url} "
                    f"(selector {cfg.email_selector!r}). "
                    f"Set easyatwork.email_selector to match your tenant."
                ) from e

            page.fill(cfg.email_selector, cfg.email)
            page.fill(cfg.password_selector, password)
            page.click(cfg.submit_selector)

            try:
                if extra_wait_selector:
                    page.wait_for_selector(
                        extra_wait_selector, timeout=cfg.login_timeout_ms
                    )
                else:
                    page.wait_for_load_state(
                        "networkidle", timeout=cfg.login_timeout_ms
                    )
            except PWTimeout as e:
                raise LoginError(
                    f"login did not complete (timeout waiting post-submit). "
                    f"Current URL: {page.url}"
                ) from e

            # Heuristic: if we're still on login-ish URL, assume failure.
            final_url = page.url.lower()
            if any(x in final_url for x in ("login", "signin", "sign-in")):
                raise LoginError(
                    f"login did not advance off login page. URL: {page.url}. "
                    f"Check credentials or selectors."
                )

            # Wait a little longer just in case the API request hasn't fired yet
            if not discovered_meta:
                with contextlib.suppress(PWTimeout):
                    page.wait_for_timeout(3000)

            state = context.storage_state()
            if discovered_meta:
                state["eaw_meta"] = discovered_meta
            
            import json
            import os
            tmp = storage_path.with_suffix(storage_path.suffix + ".tmp")
            tmp.write_text(json.dumps(state))
            os.replace(tmp, storage_path)
            with contextlib.suppress(OSError):
                os.chmod(storage_path, 0o600)
        finally:
            browser.close()
