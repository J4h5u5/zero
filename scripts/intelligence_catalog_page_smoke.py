#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


PRIVATE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\btrace_id\b",
        r"\bidempotency_key\b",
        r"\bwallet_address\b",
        r"\bprivate_key\b",
        r"\bexchange_order_id\b",
        r"api:/execute",
        r"strategy:",
        r"\bBTC\b",
        r"\bETH\b",
        r"\bSOL\b",
        r"0x1{16,}",
    ]
]

EXPECTED_LINKS = {
    "catalog.json",
    "commercial.json",
    "snapshot.json",
    "model_gateway.json",
}

EXPECTED_TEXT = {
    "Public Catalog",
    "Commercial Metering",
    "Never Metered",
    "Checked Contracts",
    "does not imply hosted realtime availability",
}


@dataclass
class ParsedPage:
    title: str = ""
    h1: str = ""
    links: set[str] = field(default_factory=set)
    scripts: int = 0
    remote_refs: list[str] = field(default_factory=list)
    event_handlers: list[str] = field(default_factory=list)
    _stack: list[str] = field(default_factory=list)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page = ParsedPage()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.page._stack.append(tag)
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag == "script":
            self.page.scripts += 1
        for name, value in attr_map.items():
            if name.startswith("on"):
                self.page.event_handlers.append(f"{tag}.{name}")
            if name in {"href", "src", "poster"} and is_remote_or_script_ref(value):
                self.page.remote_refs.append(value)
        href = attr_map.get("href")
        if tag == "a" and href:
            self.page.links.add(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.page._stack:
            self.page._stack = self.page._stack[: self.page._stack.index(tag)]

    def handle_data(self, data: str) -> None:
        current = self.page._stack[-1] if self.page._stack else ""
        text = " ".join(data.split())
        if not text:
            return
        if current == "title":
            self.page.title = f"{self.page.title} {text}".strip()
        elif current == "h1":
            self.page.h1 = f"{self.page.h1} {text}".strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test checked ZERO Intelligence catalog HTML."
    )
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    root = Path(args.root)
    intelligence_dir = root / "contracts" / "intelligence"
    page_path = intelligence_dir / "catalog.html"
    if not page_path.exists():
        print("FAIL: catalog.html missing", file=sys.stderr)
        return 1

    body = page_path.read_text(encoding="utf-8")
    parsed = parse_page(body)
    failures = validate_page(body, parsed, intelligence_dir)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("intelligence catalog page smoke passed")
    return 0


def parse_page(body: str) -> ParsedPage:
    parser = PageParser()
    parser.feed(body)
    return parser.page


def validate_page(body: str, parsed: ParsedPage, intelligence_dir: Path) -> list[str]:
    failures: list[str] = []
    if parsed.title != "ZERO Intelligence Catalog":
        failures.append(f"title {parsed.title!r} != 'ZERO Intelligence Catalog'")
    if parsed.h1 != "Public Catalog":
        failures.append(f"h1 {parsed.h1!r} != 'Public Catalog'")
    if parsed.scripts:
        failures.append(f"contains {parsed.scripts} script tag(s)")
    if parsed.event_handlers:
        failures.append(f"contains event handlers {sorted(parsed.event_handlers)}")
    if parsed.remote_refs:
        failures.append(f"contains remote/script refs {sorted(parsed.remote_refs)}")

    missing_links = EXPECTED_LINKS - parsed.links
    if missing_links:
        failures.append(f"missing links {sorted(missing_links)}")
    for href in parsed.links:
        if is_remote_or_script_ref(href):
            failures.append(f"link is not local-safe: {href}")
            continue
        target = (intelligence_dir / href).resolve()
        if not target.exists() or intelligence_dir.resolve() not in target.parents:
            failures.append(
                f"local link target missing or outside contracts/intelligence: {href}"
            )

    for text in EXPECTED_TEXT:
        if text not in body:
            failures.append(f"missing expected text {text!r}")
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(body):
            failures.append(f"private runtime token matched {pattern.pattern!r}")
    return failures


def is_remote_or_script_ref(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    if lowered.startswith(("javascript:", "data:", "//")):
        return True
    parsed = urlparse(stripped)
    return parsed.scheme in {"http", "https"}


if __name__ == "__main__":
    raise SystemExit(main())
