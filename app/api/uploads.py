from pathlib import Path

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}


class UploadError(Exception):
    """An upload we refuse. status_code is the HTTP code to return."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def safe_filename(raw_name: str | None) -> str:
    """Keep only the last part of the name, so '../../x.md' becomes 'x.md'."""
    # Treat Windows-style backslashes as separators too.
    name = Path((raw_name or "").replace("\\", "/")).name.strip()
    if not name or name.startswith("."):
        raise UploadError(400, f"Invalid filename: {raw_name!r}")
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UploadError(415, f"File type not allowed: {name!r}. Allowed: {allowed}")
    return name


def check_size(content: bytes, max_bytes: int) -> None:
    if len(content) > max_bytes:
        raise UploadError(413, f"File is larger than {max_bytes // (1024 * 1024)} MB")
    if not content:
        raise UploadError(400, "File is empty")


def save_upload(docs_dir: Path, name: str, content: bytes) -> Path:
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = (docs_dir / name).resolve()
    # Defence in depth: safe_filename already removed folders, but check again.
    if target.parent != docs_dir.resolve():
        raise UploadError(400, f"Invalid filename: {name!r}")
    if target.exists():
        raise UploadError(409, f"{name!r} already exists. Delete or rename it first.")
    target.write_bytes(content)
    return target
