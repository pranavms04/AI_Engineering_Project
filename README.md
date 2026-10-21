# AI Knowledge Assistant

Loads documents (`.txt`, `.md`, `.pdf`) into cleaned, metadata-tagged text ready for indexing.

## Project structure

```
app/
  ingestion/
    cleaning.py      # text normalisation (hyphenation, page numbers, whitespace)
    loader.py        # file/directory loaders, empty and duplicate skipping
data/
  sample_docs/       # example input documents
scripts/
  inspect_docs.py    # load sample_docs and print a preview
tests/
  test_loader.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Usage

```bash
python -m pytest            # run tests
python -m scripts.inspect_docs
```

Scanned PDFs without a text layer are skipped with a warning (OCR is not supported yet).
