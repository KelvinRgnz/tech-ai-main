"""OCR com o modelo prebuilt-read do Azure Document Intelligence."""

from __future__ import annotations

import importlib
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any

from tech_ai.errors import ConfigurationError, DocumentOcrError
from tech_ai.integrations.documents.client import OcrPage, OcrResult

_SUPPORTED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png"}
_F0_MAX_BYTES = 4 * 1024 * 1024


def _azure_types() -> tuple[Any, Any]:
    try:
        document_module = importlib.import_module("azure.ai.documentintelligence")
        credentials_module = importlib.import_module("azure.core.credentials")
    except ImportError as error:
        raise ConfigurationError(
            "O cliente Azure Document Intelligence não está instalado. "
            "Execute: uv sync --extra azure"
        ) from error
    return document_module.DocumentIntelligenceClient, credentials_module.AzureKeyCredential


class AzureDocumentReader:
    def __init__(
        self,
        *,
        key: str,
        endpoint: str,
        max_pages: int = 2,
        max_concurrent_requests: int = 1,
        max_bytes: int = _F0_MAX_BYTES,
    ) -> None:
        if not key.strip() or not endpoint.startswith("https://"):
            raise ConfigurationError("Credenciais do Azure Document Intelligence inválidas.")
        if max_pages <= 0 or max_pages > 2:
            raise ConfigurationError("O plano F0 permite no máximo duas páginas por análise.")
        if max_concurrent_requests <= 0 or max_bytes <= 0:
            raise ConfigurationError("Limites do OCR devem ser positivos.")
        self._key = key
        self._endpoint = endpoint.rstrip("/")
        self._max_pages = max_pages
        self._max_bytes = max_bytes
        self._semaphore = BoundedSemaphore(max_concurrent_requests)

    def read(self, path: Path, *, content_type: str) -> OcrResult:
        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise DocumentOcrError("Formato não suportado pelo OCR.")
        if not path.is_file():
            raise DocumentOcrError("Documento indisponível para OCR.")
        if path.stat().st_size > self._max_bytes:
            raise DocumentOcrError("O documento excede o limite de 4 MB do plano F0.")
        with self._semaphore:
            return self._read(path)

    def _read(self, path: Path) -> OcrResult:
        client_type, credential_type = _azure_types()
        try:
            client = client_type(
                endpoint=self._endpoint,
                credential=credential_type(self._key),
            )
            with path.open("rb") as document:
                poller = client.begin_analyze_document(
                    "prebuilt-read",
                    body=document,
                    pages=f"1-{self._max_pages}",
                    locale="pt-BR",
                    output_content_format="text",
                )
                result = poller.result()
            pages = tuple(
                OcrPage(
                    number=int(page.page_number),
                    text="\n".join(
                        str(line.content).strip()
                        for line in (page.lines or ())
                        if str(line.content).strip()
                    ),
                )
                for page in (result.pages or ())
            )
            text = str(result.content or "").strip()
            if not text:
                raise DocumentOcrError("Nenhum texto legível foi reconhecido no documento.")
            return OcrResult(text=text, pages=pages)
        except (ConfigurationError, DocumentOcrError):
            raise
        except Exception as error:
            raise DocumentOcrError(
                "O Azure Document Intelligence não concluiu o OCR."
            ) from error
