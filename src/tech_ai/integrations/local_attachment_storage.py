"""Armazenamento local com arquivos temporários e chaves geradas pelo servidor."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import AsyncIterable
from contextlib import suppress
from pathlib import Path

from tech_ai.errors import AttachmentStorageError, AttachmentValidationError
from tech_ai.repositories.attachment_repository import TemporaryAttachment


class LocalAttachmentStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    async def write_temporary(
        self, chunks: AsyncIterable[bytes], *, max_bytes: int
    ) -> TemporaryAttachment:
        self._root.mkdir(parents=True, exist_ok=True)
        temporary_dir = self._root / ".tmp"
        temporary_dir.mkdir(exist_ok=True)
        file_descriptor, raw_path = tempfile.mkstemp(prefix="upload-", dir=temporary_dir)
        path = Path(raw_path)
        size = 0
        digest = hashlib.sha256()
        header = bytearray()
        try:
            with os.fdopen(file_descriptor, "wb") as target:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise AttachmentValidationError("O arquivo excede o limite permitido.")
                    digest.update(chunk)
                    if len(header) < 32:
                        header.extend(chunk[: 32 - len(header)])
                    target.write(chunk)
            if size == 0:
                raise AttachmentValidationError("O arquivo está vazio.")
            return TemporaryAttachment(path, size, digest.hexdigest(), bytes(header))
        except AttachmentValidationError:
            path.unlink(missing_ok=True)
            with suppress(OSError):
                os.close(file_descriptor)
            raise
        except OSError:
            path.unlink(missing_ok=True)
            with suppress(OSError):
                os.close(file_descriptor)
            raise AttachmentStorageError("Não foi possível armazenar o arquivo.") from None

    def promote(self, temporary: TemporaryAttachment, *, storage_key: str) -> None:
        destination = self._safe_path(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            temporary.path.replace(destination)
        except OSError:
            temporary.path.unlink(missing_ok=True)
            raise AttachmentStorageError("Não foi possível armazenar o arquivo.") from None

    def remove(self, storage_key: str) -> None:
        try:
            self._safe_path(storage_key).unlink(missing_ok=True)
        except OSError:
            raise AttachmentStorageError("Não foi possível remover o arquivo.") from None

    def resolve(self, storage_key: str) -> Path:
        path = self._safe_path(storage_key)
        if not path.is_file():
            raise AttachmentStorageError("Arquivo do anexo indisponível.")
        return path

    def _safe_path(self, storage_key: str) -> Path:
        candidate = (self._root / storage_key).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            raise AttachmentStorageError("Chave de armazenamento inválida.") from None
        return candidate
