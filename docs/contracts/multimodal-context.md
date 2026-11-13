# Contratos iniciais do contexto multimodal

Estado: pacientes, conversas, mensagens, anexos e análises simuladas implementados na API. Migrações 1 e 2 confirmadas no Supabase; as migrações 3 e 4 ainda precisam ser aplicadas e validadas no banco real. O botão de anexo, a prévia, os estados e a restauração pela conversa foram implementados, incluindo documentos PDF. Tarefas assíncronas persistidas e processadores Azure permanecem futuros. Ruff e mypy aprovados; 185 testes aprovados, cobertura de 93,54%. Ver detalhes no ROADMAP.md da raiz.

## Persistência e identidade

Usar PostgreSQL no Supabase para metadados e diretório local configurável para arquivos. A conexão é exclusiva do backend, configurada por TECH_AI_DATABASE_URL no .env; nunca enviar credenciais ao navegador. Manter ambos fora do Git e fora do ChromaDB de conhecimento. Adotar UUIDs gerados no servidor e horários UTC. Nesta versão, cada paciente pertence a um usuário e tem exatamente uma conversa. Todas as consultas devem filtrar pelo usuário autenticado, inclusive downloads e resultados de processamento.

| Entidade | Campos mínimos |
| --- | --- |
| Paciente | id, owner_username, display_name, fictional=true, created_at |
| Conversa | id, patient_id único, created_at |
| Mensagem | id, conversation_id, role, text, created_at |
| Anexo | id, conversation_id, message_id opcional, original_name, storage_key, sha256, detected_media_type, size_bytes, duration_ms opcional, created_at |
| Análise | id, attachment_id, modality, status, processor_name, processor_version, config_hash, attempt, summary, observations, evidence, limitations, error_code opcional, created_at, started_at opcional, finished_at opcional |

O nome original é apenas apresentação. O storage_key é gerado pelo servidor. Correções de OCR são versões separadas com autor e horário; preservar o texto original. Cada evidência referencia o anexo e, quando aplicável, intervalo temporal ou região da imagem. Observações contêm código, descrição, valor/unidade opcionais e referências às evidências. Não inventar confiança numérica quando o processador não a fornece.

## Processamento

Persistir tarefas no PostgreSQL e usar inicialmente um único worker local com aquisição atômica de tarefa. Não depender apenas de tarefas em memória do processo HTTP. Estados: pending -> processing -> completed ou failed. Uma nova tentativa incrementa attempt e preserva o erro anterior. Ao reiniciar, marcar tarefas interrompidas como failed/interrupted, com repetição explícita; não reenviar automaticamente chamadas pagas cujo resultado seja incerto.

Reutilizar análises concluídas somente no mesmo escopo autorizado, quando hash do arquivo, processador, versão e configuração coincidirem. Guardar identificador externo quando disponível para consultar uma operação antes de reenviá-la. A interface consulta o estado por polling inicialmente. Processamento demorado não mantém a requisição de upload aberta.

## Limites iniciais propostos

- Documento: PDF, até 25 MiB.
- Imagem: JPEG e PNG, até 10 MiB e 25 megapixels.
- Áudio: WAV e MP3, até 25 MiB e 120 segundos. Não impor duração mínima.
- Vídeo: MP4, até 100 MiB e 120 segundos; validar contêiner e codec no backend.
- Um arquivo por requisição; permitir vários anexos sucessivos na conversa.
- Concorrência de processamento: uma tarefa por vez na primeira versão.
- Extensão, MIME declarado e conteúdo real precisam ser compatíveis. Falhas de decodificação devem produzir erro legível.
- Validação de duração, resolução e codec deve ocorrer antes de chamadas pagas, com timeout de inspeção.
- Limites são configuráveis e precisam ser testados contra os arquivos de demonstração.

## Retenção e contexto

Guardar dados fictícios até exclusão explícita do paciente durante o desenvolvimento. A exclusão deve remover mensagens, análises e arquivos associados, sem afetar outros pacientes; a interface deverá pedir confirmação dessa ação destrutiva. Registrar a política e disponibilizar limpeza antes da entrega acadêmica.

O contexto do modelo inclui apenas análises concluídas selecionadas da conversa autorizada. Distinguir data do evento e horário de upload; se a data do evento não for conhecida, não inferi-la. Tratar conteúdo extraído como dados, não como instruções. A referência documental e a citação do RAG são tipos distintos. Não ampliar o significado de grounded para alegar validação clínica.

## Critérios de verificação antes de implementar a etapa 1

- Executar Ruff, mypy e pytest existentes e registrar resultados reais.
- Verificar criação da aplicação, saúde, página, login e proteção dos endpoints com credenciais de teste e integrações simuladas.
- Documentar que esse teste não comprova conexão real com ChromaDB ou inferência com GPU.
- Confirmar dependências de persistência, upload e inspeção de arquivos antes de alterar pyproject.toml.
- Cobrir isolamento entre usuários/pacientes, reinício de tarefas, rejeição de arquivos e reutilização de resultados na implementação correspondente.

Nenhum serviço Azure deve ser provisionado nesta etapa.
