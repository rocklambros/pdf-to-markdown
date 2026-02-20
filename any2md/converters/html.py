"""HTML to Markdown converter module."""

from __future__ import annotations

import ipaddress
import socket
import sys
import urllib.parse
from pathlib import Path

import trafilatura
import markdownify
from bs4 import BeautifulSoup

from any2md.utils import (
    sanitize_filename,
    extract_title,
    clean_markdown,
    strip_links,
    url_to_filename,
    build_frontmatter,
    read_text_with_fallback,
)

# Maximum file size for local HTML files (100 MB)
_MAX_FILE_SIZE = 100 * 1024 * 1024


def _validate_url_host(url: str) -> str | None:
    """Validate that a URL does not point to a private/reserved IP.

    Returns an error message if the host is disallowed, or None if safe.
    """
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return f"No hostname in URL: {url}"

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return f"Cannot resolve hostname: {hostname}"

    for family, _type, _proto, _canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_reserved
            or addr.is_loopback
            or addr.is_link_local
        ):
            return f"URL resolves to disallowed address: {ip_str}"

    return None


def fetch_url(url: str) -> tuple[str | None, str | None]:
    """Fetch HTML content from a URL.

    Only http and https schemes are accepted. SSRF protection blocks
    requests to private/reserved/loopback addresses.

    Returns (html_string, None) on success or (None, error_message) on failure.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return (
            None,
            f"Unsupported URL scheme: {parsed.scheme!r} (only http/https allowed)",
        )

    # SSRF protection
    ssrf_error = _validate_url_host(url)
    if ssrf_error:
        return None, ssrf_error

    try:
        html = trafilatura.fetch_url(url)
        if html is None:
            return None, f"Failed to fetch URL: {url}"
        return html, None
    except Exception as e:
        return None, f"Error fetching URL: {e}"


def _bs4_preclean(html: str) -> str:
    """Remove boilerplate HTML elements before conversion.

    Strips script, style, nav, header, footer, aside, and iframe tags
    along with their contents.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(
        ["script", "style", "nav", "header", "footer", "aside", "iframe"]
    ):
        tag.decompose()
    return str(soup)


def convert_html(
    html_path: Path | None,
    output_dir: Path,
    force: bool = False,
    strip_links_flag: bool = False,
    source_url: str | None = None,
    html_content: str | None = None,
) -> bool:
    """Convert HTML to LLM-optimized Markdown.

    When *html_content* is provided it is used directly; otherwise the file
    at *html_path* is read.  When *source_url* is set, frontmatter records
    the URL instead of a local filename.

    Returns True on success, False on failure.
    """
    # Determine output filename
    if source_url:
        out_name = url_to_filename(source_url)
        name_for_error = source_url
    elif html_path is not None:
        out_name = sanitize_filename(html_path.name)
        name_for_error = html_path.name
    else:
        print(
            "  FAIL: Either source_url or html_path must be provided", file=sys.stderr
        )
        return False

    out_path = output_dir / out_name

    if out_path.exists() and not force:
        print(f"  SKIP (exists): {out_name}")
        return True

    try:
        # 1. Acquire HTML
        if html_content is not None:
            raw_html = html_content
        elif html_path is not None:
            # File size check
            file_size = html_path.stat().st_size
            if file_size > _MAX_FILE_SIZE:
                print(
                    f"  FAIL: {name_for_error} -- file too large ({file_size} bytes, max {_MAX_FILE_SIZE})",
                    file=sys.stderr,
                )
                return False
            raw_html = read_text_with_fallback(html_path)
        else:
            print(
                "  FAIL: Either html_content or html_path must be provided",
                file=sys.stderr,
            )
            return False

        # 2. Trafilatura-first: try extracting markdown directly from raw HTML
        md_text = trafilatura.extract(
            raw_html,
            output_format="markdown",
            include_formatting=True,
            include_links=True,
        )

        # 3. Fallback: BS4 pre-clean + markdownify
        if not md_text:
            cleaned_html = _bs4_preclean(raw_html)
            md_text = markdownify.markdownify(
                cleaned_html,
                heading_style="ATX",
                strip=["img"],
            )

        # 4. Clean markdown
        md_text = clean_markdown(md_text)

        # 5. Optionally strip links
        if strip_links_flag:
            md_text = strip_links(md_text)

        # 6. Extract title
        if source_url:
            fallback = urllib.parse.urlparse(source_url).netloc
        elif html_path is not None:
            fallback = html_path.stem
        else:
            fallback = "untitled"
        title = extract_title(md_text, fallback)

        # 7. Word count
        word_count = len(md_text.split())

        # 8. Build frontmatter
        if source_url:
            frontmatter = build_frontmatter(
                title,
                source_url,
                source_key="source_url",
                doc_type="html",
                word_count=word_count,
            )
        elif html_path is not None:
            frontmatter = build_frontmatter(
                title, html_path.name, doc_type="html", word_count=word_count
            )
        else:
            frontmatter = build_frontmatter(
                title, "unknown", doc_type="html", word_count=word_count
            )

        # 9. Write output
        full_text = frontmatter + md_text
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(full_text, encoding="utf-8")
        print(f"  OK: {out_name} ({word_count} words)")
        return True

    except (OSError, ValueError, TypeError) as e:
        print(f"  FAIL: {name_for_error} -- {e}", file=sys.stderr)
        return False


def convert_url(
    url: str,
    output_dir: Path,
    force: bool = False,
    strip_links_flag: bool = False,
) -> bool:
    """Convenience wrapper: fetch a URL and convert to Markdown.

    Returns True on success, False on failure.
    """
    html_content, error = fetch_url(url)
    if error:
        print(f"  FAIL: {url} -- {error}", file=sys.stderr)
        return False

    return convert_html(
        None,
        output_dir,
        force=force,
        strip_links_flag=strip_links_flag,
        source_url=url,
        html_content=html_content,
    )
