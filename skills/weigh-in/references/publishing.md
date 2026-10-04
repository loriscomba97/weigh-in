# Publishing the analysis

Publishing happens only after the user's approval, only where they say, and only with what they approved. Confidential information they shared at kickoff never reaches a shared page without their explicit confirmation.

## 1. Any destination

1. **Create the pages first,** empty, so their addresses exist for the links between documents.
2. **Convert** the Markdown to what the destination accepts.
3. **Split** long documents into chunks the destination's API accepts, cutting only at headings.
4. **Upload in order:** the first chunk replaces the page content, the others are appended.
5. **Read every page back** and check the start, the joins between chunks, the end, the tables and the links. Fix with targeted edits, not full re-uploads.
6. **Record the page addresses** in the project's memory and in the register.

## 2. The structure that works

- **The main page:**
  - a short box with what it is, the date and the sources;
  - an index of the documents: a table with links and one-line descriptions;
  - a **general summary**: the decision maker's summary rewritten for everyone, with a recommendation in place of "decisions for you";
  - the list of subpages.
- **One subpage per document,** with its numbered title.
- **An "Appendices" page:** a table that links each working report to its content and to the document it supports, and one subpage per report.
- **Links between documents** become links between pages, including links to earlier analyses already published.

## 3. Notion

```bash
python3 scripts/md_to_notion.py --config notion.json --src analyses/acme-2026-10-04 --out <scratch>/notion
python3 scripts/chunk_markdown.py <scratch>/notion/*.nmd --out <scratch>/notion/chunks --limit 18000
```

The config maps each document to its page and says how documents refer to each other:

```json
{
  "pages": {"01": "<page id>", "02": "<page id>", "A": "<page id>"},
  "files": {"01": "01-company-product-business.md", "A": "appendices/A-architecture.md"},
  "references": [{"regex": "\\bdocument (0[1-9])\\b", "group": 1}],
  "literals": [{"text": "the earlier analysis", "page": "<page id>"}],
  "callout_markers": ["Note", "Update"],
  "toc": true,
  "drop_first_h1": true
}
```

Notion's Markdown has rules of its own, and the converter applies them:

- tables become `<table>` blocks with tab-indented rows;
- callouts and the table of contents use their own blocks;
- special characters (`$`, `~`, `<`, `>`, `[`, `]` and others) are escaped, without doubling escapes already in the text;
- never escape a backtick: it breaks everything after it;
- file paths, with their folders and line numbers, go into inline code. Names ending in `.md`, `.sh` or `.py` are real web domains, and Notion would turn them into links;
- nested lists need consistent tabs.

One rule the converter can only warn about: in a table cell, "+ " or "* " after bold or code text becomes a bullet. Reword those cells before you upload.

**Chunks:** about 18,000 characters each, cut only at `##` or `###` headings outside tables, callouts and code. Lower the limit if Notion rejects a chunk.

**Long appendices:** one or two helpers can upload them in parallel. Tell them to copy each chunk byte for byte, never to retype it.

## 4. Other destinations

- **A wiki or a docs site** that accepts standard Markdown: copy the documents as they are; check tables and links after publishing.
- **Shared documents** (word processors): export to their format, then check tables, headings and links by reading the result back.
- **A public comparison page** is not a copy of the analysis. It is a new page, written under the rules in [communication.md](communication.md), and it goes to counsel first.
