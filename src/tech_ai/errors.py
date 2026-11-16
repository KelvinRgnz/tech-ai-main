"""Erros estáveis apresentados pelo runtime do tech-ai."""


class DatabaseConnectionError(RuntimeError):
    """Falha de conexão sem detalhes privados do driver."""


class PatientNotFoundError(LookupError):
    """Paciente inexistente ou pertencente a outro usuário."""


class PatientValidationError(ValueError):
    """Dados de paciente inválidos."""


class AttachmentNotFoundError(LookupError):
    """Anexo inexistente ou fora do escopo do usuário/paciente."""


class AttachmentValidationError(ValueError):
    """Arquivo incompatível, vazio ou acima dos limites permitidos."""


class AttachmentStorageError(RuntimeError):
    """Falha sanitizada ao gravar ou recuperar o arquivo local."""


class SpeechTranscriptionError(RuntimeError):
    """Falha sanitizada ao transcrever um áudio no provedor configurado."""


class LanguageAnalysisError(RuntimeError):
    """Falha sanitizada ao analisar texto no provedor configurado."""


class DocumentOcrError(RuntimeError):
    """Falha sanitizada ao extrair texto de um documento."""


class VideoAnalysisError(RuntimeError):
    """Falha sanitizada ao analisar movimentos em um vídeo."""


class ConfigurationError(ValueError):
    """Indica uma configuração ausente ou inválida."""


class ModelArtifactReadError(ValueError):
    """Indica que o manifesto de um modelo pronto não pôde ser lido."""


class ModelArtifactValidationError(ValueError):
    """Indica que um artefato publicado não atende ao contrato do runtime."""


class ModelRuntimeError(RuntimeError):
    """Indica que o modelo publicado não pôde ser carregado ou executado."""


class EmbeddingError(RuntimeError):
    """Indica falha ao gerar o vetor de uma consulta."""


class KnowledgeStoreError(RuntimeError):
    """Indica falha ao consultar a base vetorial."""


class KnowledgeRetrievalError(ValueError):
    """Indica uma consulta semântica inválida ou inconsistente."""


class TranslationError(RuntimeError):
    """Indica falha ao traduzir pergunta ou evidências para o português."""


class AssistantError(RuntimeError):
    """Indica que o assistente não conseguiu produzir uma resposta válida."""


class AuthenticationError(RuntimeError):
    """Indica credenciais inválidas ou sessão ausente."""
