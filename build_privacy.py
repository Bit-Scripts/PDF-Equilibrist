#!/usr/bin/env python3
"""Generate /privacy/index.html from the repository's PRIVACY.md.

The renderer intentionally supports the Markdown constructs used by this policy
and has no third-party dependency, so GitHub Pages receives complete static HTML.
"""

from __future__ import annotations

import html
import os
import re
import unicodedata


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(ROOT_DIR, "PRIVACY.md")
TEMPLATE_PATH = os.path.join(ROOT_DIR, "multilingual", "privacy.template.html")
OUTPUT_PATH = os.path.join(ROOT_DIR, "privacy", "index.html")


def slugify(value: str) -> str:
    """Match the readable heading anchors expected by links in PRIVACY.md."""
    value = unicodedata.normalize("NFC", value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", value).strip("-")


def render_inline(value: str) -> str:
    rendered = html.escape(value, quote=False)

    def link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html.escape(match.group(2), quote=True)
        return f'<a href="{href}">{label}</a>'

    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, rendered)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_markdown(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            output.append(
                f'<h{level} id="{html.escape(slugify(title), quote=True)}">'
                f"{render_inline(title)}</h{level}>"
            )
            index += 1
            continue

        if stripped == "---":
            flush_paragraph()
            output.append("<hr>")
            index += 1
            continue

        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and is_table_separator(lines[index + 1].strip())
        ):
            flush_paragraph()
            headers = table_cells(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(table_cells(lines[index]))
                index += 1

            output.append('<div class="table-scroll" tabindex="0">')
            output.append("<table><thead><tr>")
            output.extend(f"<th scope=\"col\">{render_inline(cell)}</th>" for cell in headers)
            output.append("</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>")
                output.extend(f"<td>{render_inline(cell)}</td>" for cell in row)
                output.append("</tr>")
            output.append("</tbody></table></div>")
            continue

        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    return "\n".join(output)


def build() -> str:
    with open(SOURCE_PATH, encoding="utf-8") as source_file:
        markdown = source_file.read()
    with open(TEMPLATE_PATH, encoding="utf-8") as template_file:
        template = template_file.read()

    sections = re.split(r"\n---\s*\n", markdown, maxsplit=1)
    if len(sections) != 2:
        raise ValueError("PRIVACY.md must contain English and French sections separated by ---")

    content = "\n".join(
        (
            '<section lang="en" aria-labelledby="privacy-policy-pdf-equilibrist">',
            render_markdown(sections[0]),
            "</section>",
            '<section lang="fr" aria-labelledby="politique-de-confidentialité">',
            render_markdown(sections[1]),
            "</section>",
        )
    )
    rendered = template.replace("{{privacy.content}}", content)
    if "{{privacy.content}}" in rendered:
        raise ValueError("Privacy content placeholder was not replaced")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as output_file:
        output_file.write(rendered)
    return os.path.relpath(OUTPUT_PATH, ROOT_DIR)


if __name__ == "__main__":
    print(f"Generated {build()} from PRIVACY.md")
