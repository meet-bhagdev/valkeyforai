# Jupyter Notebooks

Every Valkey for AI cookbook is available as a Jupyter notebook under
`notebooks/`. The notebooks provide an interactive alternative to reading the
same cookbook on the website.

## Why we provide notebooks

Cookbooks often combine explanation, setup commands, and Python code. A
notebook keeps those pieces together while letting readers:

- run a cookbook one step at a time;
- inspect values and results between steps;
- change examples without first creating a separate application;
- use the material in JupyterLab, VS Code, or another notebook client; and
- keep personal experiments separate from the cookbook source.

The Markdown files remain the source of truth. HTML pages and notebooks are
generated from the same source so the two formats do not need to be maintained
independently.

## Source and output layout

Each cookbook is declared in its track's `meta.json` file and maps to one
Markdown source, one generated HTML page, and one generated notebook.

| Purpose | Example |
| --- | --- |
| Track metadata | `content/semantic-caching/meta.json` |
| Cookbook source | `content/semantic-caching/01-getting-started.md` |
| Website page | `cookbooks/semantic-caching/01-getting-started.html` |
| Jupyter notebook | `notebooks/semantic-caching/01-getting-started.ipynb` |

Do not edit an `.ipynb` file directly. The next build will replace manual
changes with content generated from the corresponding Markdown file.

## Opening the notebooks

Install the Python environment and launch JupyterLab from the repository root:

```bash
uv sync
uv run jupyter lab notebooks/
```

You can also open an individual `.ipynb` file directly in VS Code or another
notebook client.

Saving a notebook after running or rearranging cells changes the generated
file. Use **Save As** to place personal experiments outside `notebooks/` if you
want to keep them. Running `npm run build:notebooks` restores the generated
version and replaces changes made directly to that file. Jupyter checkpoint
directories are ignored by Git and by notebook validation.

Generated notebooks do not contain saved execution results. Run their setup
cells first and provide any services, dependencies, or environment variables
required by the original cookbook. Never save API keys or other secrets in a
notebook.

For cookbooks that need Valkey Search or JSON, verify the bundle container
directly:

```bash
docker exec valkey valkey-cli INFO modules
```

This avoids accidentally checking another Valkey process that is using the
same host port.

## How notebooks are generated

The `build-notebooks.js` script reads every track directory under `content/`.
For each cookbook listed in `meta.json`, it reads the Markdown source and writes
an `.ipynb` file with the same track and base filename:

```text
content/<track>/<cookbook>.md
              │
              ├── build.js ────────────> cookbooks/<track>/<cookbook>.html
              │
              └── build-notebooks.js ──> notebooks/<track>/<cookbook>.ipynb
```

The notebook starts with a generated title cell containing the cookbook title,
difficulty, estimated time, and track name. The remaining content is converted
as follows:

| Markdown source | Notebook output |
| --- | --- |
| Prose, headings, lists, and tables | Markdown cells |
| `python` or `py` fenced blocks | Executable Python cells |
| `bash`, `sh`, or `shell` fenced blocks | Executable `%%bash` cells |
| Environment-variable snippets | Fenced Markdown cells |
| TypeScript, JSON, YAML, Mermaid, and untagged blocks | Fenced Markdown cells |

Environment snippets remain Markdown because placeholder values such as
`API_KEY=<your-key>` should not execute automatically. Non-Python examples
remain fenced Markdown because the generated notebooks use the Python kernel.

Each generated notebook uses nbformat 4 with minor version 5, identifies Python
3.12 as its kernel language, records its original Markdown path in notebook
metadata, and uses deterministic cell IDs. Rebuilding unchanged content
therefore produces the same notebook.

## Build and validation commands

Run these commands from the repository root:

```bash
# Generate every notebook
npm run build:notebooks

# Generate one track
npm run build:notebooks -- semantic-caching

# Generate both cookbook HTML and notebooks
npm run build

# Verify that generated notebooks are current
npm run check:notebooks
```

The validation command fails when it finds:

- invalid or missing track metadata;
- duplicate or missing cookbook sources;
- a Markdown cookbook that is not listed in `meta.json`;
- an unclosed fenced code block;
- a missing or stale notebook; or
- a notebook with no corresponding cookbook.

The full build keeps the `notebooks/` tree synchronized with the cookbook
catalog. Pull requests are checked for uncommitted generated changes, and the
main-branch workflow regenerates both HTML pages and notebooks.

## Contributor workflow

When changing or adding a cookbook:

1. Edit `content/<track>/<cookbook>.md`.
2. Add or update its entry in `content/<track>/meta.json`.
3. Run `npm run build`.
4. Review both the generated HTML page and notebook.
5. Run `npm run check:notebooks`.
6. Commit the source and generated artifacts together.

This keeps the website and notebook experience aligned while preserving one
editable source for every cookbook.
