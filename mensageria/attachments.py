import mimetypes
from pathlib import Path

from django.core.exceptions import ValidationError


MAX_ATTACHMENT_COUNT = 10
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL_SIZE = 20 * 1024 * 1024


def safe_attachment_name(name: str) -> str:
    return Path((name or "anexo").replace("\\", "/")).name[:255] or "anexo"


def attachment_content_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def validate_email_attachments(attachments) -> list:
    files = list(attachments or [])
    if len(files) > MAX_ATTACHMENT_COUNT:
        raise ValidationError(f"Envie no máximo {MAX_ATTACHMENT_COUNT} anexos.")

    total_size = 0
    for attachment in files:
        size = int(getattr(attachment, "size", 0) or 0)
        name = safe_attachment_name(getattr(attachment, "name", ""))
        if size <= 0:
            raise ValidationError(f'O anexo "{name}" está vazio.')
        if size > MAX_ATTACHMENT_SIZE:
            raise ValidationError(f'O anexo "{name}" excede o limite de 10 MB.')
        total_size += size

    if total_size > MAX_ATTACHMENTS_TOTAL_SIZE:
        raise ValidationError("O conjunto de anexos excede o limite total de 20 MB.")
    return files
