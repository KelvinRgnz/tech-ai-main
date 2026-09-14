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

Preencha `CHROMA_API_KEY` com a mesma chave usada no `tech-ingestao`. O `.env` é
lido automaticamente. Esse ambiente permite validar o manifesto e consultar o
Chroma Cloud sem instalar PyTorch.

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

A interface sobe em `http://127.0.0.1:8080`. O modo padrão consulta o Chroma Cloud e mostra a
evidência mais próxima, as fontes numeradas e o aviso acadêmico. O modo com modelo usa o mesmo
fluxo do comando `ask` e só funciona depois do extra `runtime`.

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
