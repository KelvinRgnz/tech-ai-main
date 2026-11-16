# Tech AI

Runtime RAG responsável por consultar o conhecimento médico indexado no ChromaDB e gerar uma
resposta com o modelo publicado pelo `tech-fine-tuning`.

Este projeto apenas consome artefatos e conhecimento prontos. Leitura do MedQuAD, indexação,
preparação de datasets, treinamento e avaliação pertencem aos outros serviços.

> **Aviso:** o modelo `tech3-v3-pt-br` é experimental, foi rejeitado para uso clínico na avaliação
> humana e foi publicado exclusivamente para aprendizado. As respostas não substituem avaliação
> médica.

## Fluxo

```text
pergunta
  -> ONNX local all-MiniLM-L6-v2
  -> ChromaDB / medquad_knowledge_minilm_v1
  -> filtro de relevância das evidências
  -> unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit + mikaelkanzaki/tech3-v3-pt-br
  -> validação de idioma, citações, repetição e contatos críticos
  -> resposta em português + fontes numeradas + aviso acadêmico
```

## Arquitetura

O serviço segue o mesmo padrão legível para quem vem de Java/Spring adotado no `ms-ai-agent`:

```text
src/tech_ai/
├── models/          DTOs e estruturas internas
├── services/        Casos de uso e orquestração
├── repositories/    Contratos de persistência
├── integrations/    ONNX, ChromaDB e Hugging Face
├── config/          Settings e montagem de dependências
├── api/             HTTP e interface do assistente médico
├── errors.py
└── runner.py
```

Consulte
[`docs/architecture/pragmatic-layered-architecture.md`](docs/architecture/pragmatic-layered-architecture.md)
para a equivalência completa com Java/Spring.

## Requisitos

- Python 3.12;
- [uv](https://docs.astral.sh/uv/);
- Chroma Cloud acessível com a mesma coleção indexada pelo `tech-ingestao`;
- GPU NVIDIA recomendada para executar o Qwen3-4B localmente.

O modelo no Hugging Face é público. `HF_TOKEN` não é necessário para baixá-lo.

## 1. Preparar o ambiente leve

```powershell
uv sync --dev
Copy-Item .env.example .env
```

Preencha `CHROMA_API_KEY` com a mesma chave usada no `tech-ingestao` e defina
`TECH_AI_AUTH_SECRET` e `TECH_AI_AUTH_USERS`. O `.env` é lido automaticamente.
Esse ambiente permite validar o manifesto e consultar o Chroma Cloud sem instalar
PyTorch.

## 2. Conectar ao Chroma Cloud

Os dois serviços usam o mesmo contrato:

- host `api.trychroma.com`;
- database `fiap-tech-challenge-3`;
- coleção `medquad_knowledge_minilm_v1`.

Caso a coleção ainda esteja vazia, execute a indexação pelo `tech-ingestao`
antes de continuar. Docker não é necessário.

## 3. Embedding local

O projeto usa o mesmo contrato da indexação:

- modelo ONNX `all-MiniLM-L6-v2`;
- dimensão `384`;
- coleção `medquad_knowledge_minilm_v1`;
- Chroma Cloud em `api.trychroma.com`.

O modelo de embeddings continua local. Só a persistência dos vetores vai para o
Cloud. Veja todas as opções em [`.env.example`](.env.example).

## 4. Validar o modelo publicado

```powershell
uv run tech-ai inspect-model
```

O manifesto padrão em [`configs/models/tech3-v3-pt-br.json`](configs/models/tech3-v3-pt-br.json) fixa:

- adaptador LoRA `mikaelkanzaki/tech3-v3-pt-br`;
- revisão publicada do adaptador;
- modelo base `unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit`;
- carregamento via `PeftModel.from_pretrained` sobre o base 4-bit;
- revisão do modelo base, tokenizer e procedência do treinamento.

## 5. Abrir o assistente no navegador

```powershell
uv run tech-ai serve
```

A interface sobe em `http://127.0.0.1:8080`. Antes da consulta, entre com um usuário
definido em `TECH_AI_AUTH_USERS`. O modo padrão consulta o Chroma Cloud e mostra a
evidência mais próxima, as fontes numeradas e o aviso acadêmico. O modo com modelo usa o mesmo
fluxo do comando `ask` e só funciona depois do extra `runtime`.

### Análise local do vídeo de fisioterapia

O fluxo acadêmico de vídeo usa o MediaPipe Pose Landmarker para estimar articulações, contar
ciclos de sentar e levantar e registrar eventos com instante verificável. Instale o extra e
baixe o bundle oficial conforme o passo a passo em
[`docs/video-pose-analysis.md`](docs/video-pose-analysis.md). Depois, valide um MP4 fictício:

```powershell
uv run --no-sync tech-ai check-video --file ".data/samples/teste_video.mp4"
```

O relatório é experimental, depende do protocolo de enquadramento e não constitui avaliação
clínica.

## Autenticação

A API HTTP protege `/api/consult`, `/api/ask` e `/api/me`. Saúde, a página e os
arquivos estáticos permanecem públicos. O login grava um cookie HttpOnly assinado
com HMAC; o cliente também pode enviar `Authorization: Bearer`.

```powershell
# .env
TECH_AI_AUTH_SECRET=uma-chave-com-pelo-menos-16-caracteres
TECH_AI_AUTH_USERS=academic:altere-esta-senha
```

Vários usuários são separados por vírgula: `ana:senha-um,bruno:senha-dois`. As
senhas são hasheadas em memória com PBKDF2. Não versione o `.env`.

## 6. Testar apenas a recuperação semântica

```powershell
uv run --env-file .env tech-ai search `
  --question "Quais são os sintomas da diabetes?" `
  --limit 4
```

Este comando não carrega o Qwen e é o primeiro diagnóstico recomendado para a integração com o
ChromaDB. Perguntas em português são traduzidas para inglês só na busca, porque o MiniLM e o
MedQuAD estão em inglês; as evidências voltam traduzidas para português. Por padrão, resultados
com distância maior que `0.55` são descartados.

## 7. Instalar o runtime e responder

```powershell
uv sync --dev --extra runtime
```

Na primeira execução, o Hugging Face pode baixar vários gigabytes do modelo base. Depois:

```powershell
uv run --env-file .env tech-ai ask `
  --question "O que é estresse?" `
  --limit 4
```

O carregamento usa o base Unsloth 4-bit, aplica o adaptador LoRA com PEFT, amostragem leve
(`temperature` entre 0.2 e 0.7), penalidade de repetição e bloqueio de n-gramas repetidos.
Esses parâmetros podem ser ajustados pelas variáveis `TECH_AI_MAX_NEW_TOKENS`,
`TECH_AI_REPETITION_PENALTY`, `TECH_AI_NO_REPEAT_NGRAM_SIZE` e `TECH_AI_TEMPERATURE`.

## Fundamentação e segurança

O comando `ask` não confia apenas no prompt para controlar o modelo:

- cada fonte recebe um número estável (`[1]`, `[2]` etc.) e devolve `record_id` do registro-pai,
  `chunk_id`, `focus`, `source_url` e a distância da busca;
- a resposta precisa citar pelo menos uma fonte existente;
- respostas predominantemente em inglês são refeitas e, se continuarem em inglês, descartadas;
- uma resposta sem citações válidas é refeita uma vez e, se continuar inválida, substituída pelo
  trecho `Answer:` da fonte mais relevante;
- frases repetidas e respostas longas demais são limitadas no runtime;
- contatos numéricos associados a emergência, hotline ou telefone são refeitos e, como última
  proteção, omitidos da saída;
- `grounded` informa se a resposta passou pelo contrato de citações;
- `warnings` torna visível qualquer intervenção da camada de segurança;
- quando nenhum resultado passa pelo filtro de distância, o modelo nem sequer é chamado.

Essas proteções reduzem respostas não fundamentadas, mas não transformam o projeto acadêmico em
um sistema adequado para uso clínico.

## Validação do projeto

```powershell
uv run ruff check .
uv run mypy
uv run pytest
```

## Responsabilidades fora deste repositório

- leitura ou tratamento do MedQuAD;
- criação ou atualização da coleção ChromaDB;
- geração de JSONL conversacional;
- Unsloth, LoRA/QLoRA e treinamento;
- avaliação ou seleção de checkpoint;
- publicação de pesos ou adaptadores.

O contexto estruturado de pacientes poderá entrar em fatias posteriores, sem alterar o núcleo
RAG já testado. A interface HTTP do assistente já consulta essa mesma recuperação.

## PostgreSQL da aplicação (Supabase)

Configure `TECH_AI_DATABASE_URL` no `.env` local com a URI do Session pooler. Codifique caracteres especiais da senha para URL. A variável é privada do backend; não use a chave publicável como senha do banco.

Execute `uv run tech-ai check-db` para validar uma conexão TLS com `SELECT 1` em transação somente-leitura. O comando exige TLS, limita conexão e consulta e omite detalhes privados dos erros. `sslmode=require` exige criptografia, mas não equivale a validar a identidade do servidor com `verify-full`.

Para criar as tabelas de pacientes e conversas, execute na pasta do projeto:

```powershell
uv run tech-ai migrate-db
```

A migração 1 cria o schema `tech_ai`, as tabelas `patients`, `conversations` e
`schema_migrations`. A migração 2 cria `messages` para o histórico das conversas. A migração 3
cria `attachments` e `analyses` para os metadados e o estado do processamento multimodal. A
migração 4 acrescenta documentos PDF às modalidades aceitas. O comando usa uma transação e
tenta adquirir uma trava sem aguardar indefinidamente. Permissões do
schema são configuradas apenas na criação inicial. Repetir o comando após sucesso não recria as
tabelas. A API não executa migrações no startup.

Endpoints autenticados disponíveis (também em `/docs`):

| Método e rota | Comportamento |
| --- | --- |
| `POST /api/patients` | Recebe `{"display_name": "Paciente fictício A"}` e cria paciente/conversa juntos |
| `GET /api/patients?limit=50&offset=0` | Lista somente pacientes do usuário da sessão |
| `GET /api/patients/{id}/conversation` | Retorna o paciente e seu `conversation_id` estável; 404 se não pertencer ao usuário |
| `GET /api/patients/{id}/messages` | Carrega o histórico somente para o proprietário autenticado |
| `POST /api/patients/{id}/attachments?filename=...` | Recebe um arquivo no corpo, valida e cria a análise pendente |
| `GET /api/patients/{id}/attachments` | Lista anexos e resultados do paciente autorizado |
| `POST /api/patients/{id}/attachments/{anexo}/process` | Usa Azure Speech para áudio habilitado; demais modalidades usam o simulador |
| `GET /api/patients/{id}/attachments/{anexo}/content` | Entrega o arquivo somente ao proprietário autorizado |

IDs são gerados no servidor. O cliente não pode escolher proprietário ou registrar
`fictional=false`. O nome tem até 120 caracteres. A paginação aceita até 100 registros.
Os horários são enviados com fuso UTC. O schema é privado, com RLS habilitada e sem
políticas de acesso público nas tabelas de pacientes/conversas. A conexão administrativa
usada nesta POC pode ignorar RLS: o isolamento entre usuários é feito pelas consultas
parametrizadas do backend. Não exponha esse schema pela API pública do Supabase.

O chat permite criar e selecionar pacientes. Consultas que informam `patient_id` registram a
pergunta e a resposta, e a interface restaura o histórico ao recarregar ou trocar de paciente.
Pedidos genéricos iniciam uma entrevista curta antes da busca. A interface consulta
`GET /api/capabilities` e desabilita o modo com modelo quando o runtime opcional não estiver
instalado.

O botão **+** aceita PDF (até 25 MiB), JPEG/PNG (até 10 MiB), WAV/MP3 (até 25 MiB) e MP4
(até 100 MiB). O backend compara extensão, MIME declarado e assinatura do conteúdo, calcula SHA-256
e gera a chave interna; o nome original é apenas apresentação. Os arquivos ficam em
`TECH_AI_ATTACHMENT_DIR` (padrão `.data/attachments`) e somente os metadados ficam no Supabase.
Documentos, imagens e vídeos ainda usam o processador simulado e não extraem conteúdo clínico.
Quando `TECH_AI_AZURE_SPEECH_ENABLED=true`, WAV e MP3 usam transcrição em tempo real do Azure
Speech, preservam marcações temporais por palavra e produzem um relatório experimental de pausas.
O resultado concluído fica persistido e consultar novamente o mesmo anexo não repete a chamada.
O RAG existente continua independente do banco.
Os testes usam repositório em memória e driver simulado; não substituem a validação da migração
e da persistência no PostgreSQL real.

## Azure da POC

As integrações Azure permanecem desativadas por padrão e suas credenciais existem somente no
`.env` local. O cliente opcional do Speech é instalado com
`uv sync --dev --extra azure --no-cache`. Para o primeiro teste real, prefira WAV PCM mono de
16 kHz e menos de 30 segundos. MP3 depende do GStreamer instalado no sistema.

O critério experimental conta uma pausa quando há pelo menos 0,8 s entre palavras reconhecidas.
Pausas isoladas não comprovam desconforto, fadiga ou dificuldade respiratória; ruído, dicção e
múltiplos falantes podem alterar o resultado. Limites conservadores são validados antes das
chamadas.

Depois de configurar a chave, o diagnóstico integrado abaixo sintetiza um relato fictício curto e
o transcreve. Ele realiza duas operações pequenas no Speech F0 e não imprime a credencial:

```powershell
uv run --no-sync --no-cache tech-ai check-speech
```

Para manter o WAV fictício e anexá-lo pelo botão **+** do chat:

```powershell
uv run --no-sync --no-cache tech-ai check-speech --output .data/samples/relato-ficticio.wav
```

O diretório `.data/` é local e ignorado pelo Git. Por segurança, o comando não sobrescreve um
arquivo existente.
Consulte [`docs/azure-poc-plan.md`](docs/azure-poc-plan.md) para serviços, faixas gratuitas,
controle de custos, variáveis e sequência de provisionamento.
