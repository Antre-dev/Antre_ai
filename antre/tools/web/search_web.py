import os

from dotenv import load_dotenv
from tavily import TavilyClient
from playwright.async_api import async_playwright

load_dotenv()

# ============================================================
# Tavily Web Search
# ============================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None


def search_web(query: str, max_results: int = 5):
    if not TAVILY_API_KEY or client is None:
        return {
            "success": False,
            "error": "TAVILY_API_KEY is not configured",
        }

    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
        )

        results = []

        for item in response.get("results", []):
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                }
            )

        return {
            "success": True,
            "query": query,
            "results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================
# Playwright Browser Agent
# ============================================================

_pw = None
_browser = None
_page = None


async def _get_page():
    """
    Lazily start the browser and keep the session alive
    between calls.
    """

    global _pw, _browser, _page

    if _page is None:
        _pw = await async_playwright().start()

        _browser = await _pw.chromium.launch(
            headless=True
        )

        _page = await _browser.new_page()

    return _page


async def _page_text(page, max_chars: int):
    """
    Extract visible text from the current page.
    """

    text = await page.evaluate(
        "() => document.body.innerText"
    ) or ""

    return (
        text[:max_chars],
        len(text) > max_chars,
    )


def _screenshot_path() -> str:
    """Unique timestamped path inside the web-served screenshots dir."""
    import time as _t
    stamp = _t.strftime("%Y%m%d_%H%M%S")
    return f"screenshots/browse_{stamp}.png"


async def browse_web(
    action: str,
    url: str = None,
    selector: str = None,
    text: str = None,
    max_content: int = 8000,
):
    """
    Agent-style browser control.

    Actions:

    goto
        Navigate to a URL.

    click
        Click an element using CSS/XPath selector.

    type
        Fill a text field.

    extract
        Extract text from the current page.

    links
        List links on the current page.

    screenshot
        Save a screenshot.
        Uses `url` as the output path.

    close
        Shut down the browser session.
    """

    global _pw, _browser, _page

    try:
        page = await _get_page()

        # ====================================================
        # GOTO
        # ====================================================

        if action == "goto":

            if not url:
                return {
                    "success": False,
                    "error": "url is required for goto",
                }

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            text_content, truncated = await _page_text(
                page,
                max_content,
            )

            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "content": text_content,
                "truncated": truncated,
            }

        # ====================================================
        # CLICK
        # ====================================================

        elif action == "click":

            if not selector:
                return {
                    "success": False,
                    "error": "selector is required for click",
                }

            await page.click(
                selector,
                timeout=10000,
            )

            # Give the page a moment to update
            await page.wait_for_timeout(500)

            text_content, truncated = await _page_text(
                page,
                max_content,
            )

            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "content": text_content,
                "truncated": truncated,
            }

        # ====================================================
        # TYPE
        # ====================================================

        elif action == "type":

            if not selector:
                return {
                    "success": False,
                    "error": "selector is required for type",
                }

            if text is None:
                return {
                    "success": False,
                    "error": "text is required for type",
                }

            await page.fill(
                selector,
                text,
            )

            return {
                "success": True,
                "filled": selector,
            }

        # ====================================================
        # EXTRACT
        # ====================================================

        elif action == "extract":

            text_content, truncated = await _page_text(
                page,
                max_content,
            )

            return {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "content": text_content,
                "truncated": truncated,
            }

        # ====================================================
        # LINKS
        # ====================================================

        elif action == "links":

            links = await page.eval_on_selector_all(
                "a",
                """
                els => els.map(e => ({
                    text: e.innerText.trim(),
                    href: e.href
                }))
                """,
            )

            return {
                "success": True,
                "links": links[:100],
            }

        # ====================================================
        # SCREENSHOT
        # ====================================================

        elif action == "screenshot":

            if url:
                # Normalize any user-supplied output path into the
                # web-served screenshots dir so the UI can display it.
                out_name = os.path.basename(str(url)) or _screenshot_path()
            else:
                out_name = _screenshot_path()

            output_path = os.path.join("screenshots", out_name)

            await page.screenshot(
                path=output_path,
                full_page=True,
            )

            return {
                "success": True,
                "screenshot": output_path,
                "screenshot_url": "/screenshots/" + os.path.basename(output_path),
            }

        # ====================================================
        # CLOSE
        # ====================================================

        elif action == "close":

            if _browser:
                await _browser.close()

            if _pw:
                await _pw.stop()

            _pw = None
            _browser = None
            _page = None

            return {
                "success": True,
                "message": "Browser session closed",
            }

        # ====================================================
        # UNKNOWN ACTION
        # ====================================================

        else:

            return {
                "success": False,
                "error": f"Unknown action: {action}",
            }

    except Exception as e:

        return {
            "success": False,
            "error": str(e),
        }