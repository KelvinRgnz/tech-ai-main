# Roadmap — Tech Challenge Fase 4

Guia de evolução do assistente médico acadêmico para análise multimodal e monitoramento simulado de pacientes.

**Estado:** contratos iniciais documentados e validação automatizada da base aprovada; preparação para a etapa 1.

Este arquivo está na raiz versionada da aplicação e acompanha a evolução do desafio acadêmico.

## 1. Objetivo e decisões acordadas

Permitir que uma conversa represente um paciente fictício e reúna perguntas, anexos, análises e alertas. O usuário poderá anexar arquivos pelo botão **+**. Cada modalidade produzirá resultados estruturados que poderão ser explicados pelo assistente com apoio do RAG.

| Tema | Escopo inicial |
| --- | --- |
| Pacientes | Dados fictícios; uma conversa por paciente |
| Vídeo | Fisioterapia: exercício encenado de levantar e sentar de uma cadeira |
| Áudio | Gravações encenadas de 30 segundos a 2 minutos; transcrição e análise de pausas |
| Imagens | OCR de laudos e prescrições; interpretação de radiografias fora desta versão |
| Monitoramento | Reprodução de séries de sinais vitais como transmissão ao vivo |
| Alertas | Painel na aplicação, com revisão pelo usuário |
| Nuvem | Azure Speech to Text e Azure Text Analytics, conforme o PDF |
| Orçamento | Teto de planejamento de R$ 200; crédito e validade de 30 dias informados pelo usuário, a confirmar no portal |
| Modelo | Candidato atual: `mikaelkanzaki/tech3-v3-pt-br`, sobre o modelo base configurado no manifesto |

O limite inicial de duração do áudio é uma escolha de implementação, não um parâmetro clínico. Pausas, movimentos e anomalias serão apresentados como observações experimentais, com suas limitações. O adaptador precisa ser avaliado para o novo contexto multimodal convertido em texto.

## 2. Base existente e limites arquiteturais

O `tech-ai-main` contém FastAPI, interface web, autenticação, busca semântica no ChromaDB, embeddings ONNX locais, tradução e geração com modelo Hugging Face/LoRA. A leitura inicial não incluiu execução da aplicação ou dos testes.

Respeitar `AGENTS.md` e a arquitetura em camadas:

- `models/`: contratos de pacientes, conversas, anexos, análises e alertas.
- `services/`: casos de uso e orquestração do processamento.
- `integrations/`: Azure, OCR, áudio, vídeo e demais sistemas externos.
- `repositories/`: contratos de persistência quando houver necessidade real.
- `config/`: configurações e composição das dependências.
- `api/`: endpoints e interface.

O ChromaDB de conhecimento permanece somente para leitura. Dados de pacientes e anexos precisam de persistência própria; não devem ser indexados nessa coleção. Treinamento pertence ao `tech-fine-tuning` e ingestão da base ao `tech-ingestao`.

## 3. Fluxo pretendido

1. Usuário autenticado seleciona um paciente fictício e abre sua conversa.
2. Anexa um arquivo; o backend valida extensão, tipo declarado e conteúdo real.
3. O sistema registra o anexo e inicia o processamento específico da modalidade.
4. A interface exibe progresso, resultado, limitações ou erro recuperável.
5. O usuário pode revisar o texto extraído antes de utilizá-lo em uma pergunta.
6. O assistente recebe pergunta, achados selecionados e evidências do RAG.
7. A reprodução de sinais vitais produz eventos e alertas vinculados ao paciente.
8. O painel permite consultar a evidência que originou cada alerta e marcá-lo como revisado.

## 4. Etapas e tarefas

As caixas indicam trabalho concluído, não apenas código escrito. Ao concluir cada etapa, registrar validação e limitações. Implementar primeiro um fluxo pequeno de ponta a ponta, depois ampliar as modalidades.

### Etapa 0 — Confirmar a base e os contratos

- [x] Executar os checks e a aplicação via TestClient com integrações simuladas; registrar o estado inicial.
- [ ] Conferir novamente o PDF e manter a matriz de requisitos deste guia atualizada.
- [x] Definir identificadores e relação entre usuário, paciente, conversa e anexo.
- [x] Definir PostgreSQL no Supabase para metadados e disco local para arquivos, sem reutilizar o ChromaDB médico.
- [x] Definir contrato comum de análise: modalidade, estado, resumo, observações, evidências, limitações, versão do processador e horários.
- [x] Definir estados de processamento: pendente, processando, concluído e falhou.
- [x] Definir formatos aceitos, limites de tamanho/duração e política de retenção dos arquivos.
- [x] Definir processamento em segundo plano e comportamento após reinício da aplicação.

Decisões registradas em `docs/contracts/multimodal-context.md`. São contratos para implementação, não funcionalidades já disponíveis. Após instalação das dependências pelo usuário: Ruff aprovado; mypy aprovado em 57 arquivos; pytest com 129 testes aprovados e cobertura de 95,07% (mínimo exigido: 90%). A suíte inclui 14 testes de API, com criação da aplicação, página, saúde, login, sessão e endpoints protegidos usando integrações simuladas. Não foi validada a conexão real com ChromaDB, a inferência na GPU ou a interface em navegador. Dois avisos de depreciação vêm das dependências Starlette/httpx e AnyIO. Para contornar permissões locais, os comandos usaram `uv run --no-sync --no-cache`; pytest também usou `--basetemp` apontando para um diretório novo e exclusivo dentro de `.venv`. Não houve alteração do código da aplicação.

**Concluída quando:** contratos e decisões estiverem documentados e o comportamento atual tiver sido verificado.

### Etapa 1 — Paciente, conversa e botão de anexos

Depende da etapa 0.

- [x] Criar persistência e endpoints de pacientes fictícios e suas conversas.
- [x] Vincular mensagens e anexos ao paciente e ao usuário autorizado.
- [x] Adicionar o botão **+**, seleção de arquivo e prévia do anexo.
- [x] Implementar upload com validação do conteúdo e armazenamento seguro do nome/caminho.
- [x] Mostrar estado, erro e opção de repetir o processamento.
- [x] Implementar um processador simulado para testar o fluxo sem consumo Azure.
- [x] Verificar isolamento: anexos e mensagens de um paciente não entram no contexto de outro.

**Concluída quando:** um usuário consegue anexar um arquivo à conversa correta, acompanhar seu processamento simulado e recuperar o resultado após recarregar a página.

**Status:** concluída e validada pelo usuário com upload real de PDF, processamento simulado e recuperação vinculada ao paciente no Supabase.

### Etapa 2 — Azure e controle de consumo

Depende da etapa 0; deve preceder testes com serviços reais.

- [x] Confirmar crédito, moeda, data de expiração e condições da assinatura no portal.
- [x] Consultar preços, regiões e disponibilidade atuais dos serviços necessários.
- [x] Estimar consumo para o conjunto de demonstração antes de provisionar recursos.
- [x] Provisionar Speech to Text F0 em Brazil South.
- [x] Provisionar o serviço correspondente ao Text Analytics requerido pelo PDF.
- [x] Configurar credenciais por ambiente, sem incluí-las no Git, no navegador ou nos logs.
- [x] Criar clientes intercambiáveis: simulado para desenvolvimento e Azure para integração.
- [x] Configurar limites locais de duração, volume de arquivos e concorrência.
- [x] Registrar chamadas e reutilizar resultados por arquivo/configuração/versão do processador.
- [x] Configurar alertas de orçamento e um procedimento para interromper o processamento pago.
- [x] Documentar que alertas de orçamento não equivalem, por si só, a bloqueio automático de gastos.

**Concluída quando:** uma chamada pequena funciona, o resultado é reutilizado e o consumo pode ser acompanhado. Não presumir que todo recurso ficará dentro do crédito gratuito.

**Validação real em 15/11/2026:** budget mensal de R$ 20 configurado; recurso
`speech-tech-ai-poc-mikael` criado no grupo `rg-tech-ai-poc`; `tech-ai check-speech` sintetizou e
transcreveu um relato fictício de 12,23 s em `pt-BR`, devolvendo 24 palavras com marcações
temporais. O recurso F0 `language-tech-ai-poc-mikael` também foi provisionado e o diagnóstico
fictício devolveu sentimento negativo com 92% de confiança e três frases-chave. A estimativa para
até 20 áudios de demonstração é de no máximo 40 minutos de Speech e 40 registros do Language,
antes de repetições. Document Intelligence permanece pendente, portanto a etapa ainda não está
concluída.

### Etapa 3 — Imagens de laudos e prescrições

Depende da etapa 1 e, caso o OCR escolhido seja em nuvem, da etapa 2.

- [ ] Criar documentos fictícios legíveis para a demonstração.
- [ ] Escolher a implementação de OCR considerando qualidade, custo e integração.
- [ ] Extrair texto preservando a referência à imagem original.
- [ ] Sinalizar trechos ilegíveis ou incertos; não completar valores ausentes por suposição.
- [ ] Permitir revisão e correção do texto, preservando o resultado original.
- [ ] Estruturar informações disponíveis: data, medicamento, dose, unidade, frequência e demais campos pertinentes.
- [ ] Exibir texto, campos extraídos e limitações na conversa.

**Concluída quando:** um laudo e uma prescrição fictícios podem ser anexados, lidos, revisados e vinculados ao paciente com rastreabilidade.

### Etapa 4 — Áudio: transcrição e observações temporais

Depende das etapas 1 e 2.

- [ ] Preparar gravações encenadas de fala contínua, pausas intencionais e ruído de fundo.
- [x] Implementar transcrição com Azure Speech to Text e preservar marcações temporais disponíveis.
- [ ] Analisar o áudio original para detectar segmentos de fala e silêncio.
- [x] Definir e documentar os critérios experimentais para contabilizar pausas.
- [ ] Produzir duração total, tempo de fala, pausas e seus intervalos; indicar limitações de ruído e múltiplos falantes.
- [x] Usar Azure Text Analytics para termos relevantes e sentimentos no texto transcrito.
- [ ] Definir uma abordagem experimental adicional para alterações vocais; pausas e sentimento textual, isoladamente, não validam detecção de fadiga ou dificuldade respiratória.
- [ ] Comparar os eventos detectados com anotações manuais das gravações.
- [x] Exibir transcrição e relatório com instantes verificáveis no áudio.

**Validação integrada em 15/11/2026:** um WAV fictício de 12,23 s foi gerado pelo comando de
diagnóstico, anexado pelo botão **+** e transcrito pelo Azure Speech em `pt-BR`. A interface exibiu
a transcrição, 24 palavras temporizadas, uma pausa estimada de pelo menos 0,8 s e o maior intervalo
estimado de 2,2 s, além das limitações experimentais. O resultado persistiu após recarregar a
página e permaneceu associado somente ao paciente de origem durante as trocas de paciente. O
processamento repetido reutiliza o resultado persistido. Um OGG/Opus fictício de 13,4 s gerado no
WhatsApp também foi convertido localmente para WAV PCM temporário, transcrito e analisado. A
interface exibiu as frases-chave `sessão`, `exercício`, `cansaço`, `fisioterapia` e `segundos`, além
de sentimento textual negativo com 100% de confiança e ressalvas clínicas. A detecção direta de
silêncio no sinal e os cenários com ruído e múltiplos falantes continuam pendentes.

**Concluída quando:** a transcrição e os eventos temporais são demonstráveis, os serviços Azure exigidos estão integrados e a cobertura de alterações vocais está explicitamente avaliada ou registrada como limitação pendente.

### Etapa 5 — Vídeo de fisioterapia

Depende da etapa 1.

- [ ] Definir protocolo de gravação do exercício de levantar e sentar: câmera fixa, corpo visível e condições de enquadramento.
- [ ] Gravar exemplos encenados e anotar manualmente repetições e eventos esperados.
- [ ] Selecionar modelo de estimativa de pose; avaliar OpenPose ou alternativa e justificar a escolha. O PDF apresenta modelos como exemplos.
- [ ] Extrair pontos corporais e tratar frames sem detecção confiável.
- [ ] Identificar fases do movimento e contar repetições.
- [ ] Medir tempos e interrupções; definir critérios experimentais de desvio adequados ao enquadramento.
- [ ] Gerar relatório com eventos, instantes, medidas e limitações.
- [ ] Mostrar trechos ou frames que permitam verificar os achados.
- [ ] Avaliar como o fluxo cobre padrões de movimentação; registrar que exercício gravado não demonstra monitoramento contínuo durante internação.

**Concluída quando:** o vídeo gera um relatório verificável de repetições e desvios definidos para a demonstração, sem apresentar os critérios como avaliação clínica validada.

### Etapa 6 — Sinais vitais, prescrições e alertas

Depende das etapas 1 e 3; utiliza eventos da etapa 5 quando disponíveis.

- [ ] Criar séries fictícias com horário, batimentos, pressão arterial e oxigenação.
- [ ] Criar cenários conhecidos: estável, alteração pontual, alteração persistente e ausência de dados.
- [ ] Implementar reprodução com iniciar, pausar, reiniciar e velocidade configurável.
- [ ] Definir técnica de detecção e parâmetros experimentais; distinguir ausência de medição de anomalia fisiológica.
- [ ] Comparar prescrições sucessivas do mesmo paciente e destacar mudanças de medicamento, dose ou frequência.
- [ ] Tratar mudanças como eventos para revisão, sem concluir automaticamente que constituem erro de tratamento.
- [ ] Incorporar eventos de movimentação ao mecanismo de alertas.
- [ ] Criar alertas com origem, evidência, horário, regra/versão e estado de revisão.
- [ ] Evitar duplicação contínua do mesmo alerta e registrar sua resolução/revisão.
- [ ] Exibir alertas no painel do paciente e manter histórico.

**Concluída quando:** a reprodução gera os alertas esperados, uma mudança de prescrição aparece para revisão e o usuário consegue rastrear e revisar cada evento.

### Etapa 7 — Fusão multimodal e integração com o assistente

Depende dos resultados das etapas 3 a 6. Pode começar com uma modalidade e ser ampliada.

- [ ] Normalizar resultados em uma linha temporal por paciente, diferenciando data do evento e data de upload.
- [ ] Definir quais análises e intervalos entram em cada pergunta; limitar o contexto enviado ao modelo.
- [ ] Separar observações dos processadores, texto documental e evidências recuperadas no RAG.
- [ ] Tratar texto de anexos como dados, impedindo que instruções contidas neles substituam as regras do assistente.
- [ ] Criar referências para anexos e eventos além das citações da base médica.
- [ ] Adaptar o contrato de fundamentação: o `grounded` atual verifica citações e não comprova correção factual.
- [ ] Avaliar o adaptador atual com perguntas sobre os relatórios estruturados.
- [ ] Exibir resultados determinísticos dos processadores mesmo quando o modelo não consegue produzir explicação adequada.
- [ ] Definir tratamento de dados contraditórios, ausentes ou temporalmente incompatíveis.
- [ ] Demonstrar uma pergunta que combine pelo menos duas modalidades do mesmo paciente com rastreabilidade.

**Concluída quando:** o assistente utiliza achados reais do processamento, cita suas origens e não mistura pacientes; limitações do adaptador estão registradas com exemplos.

### Etapa 8 — Validação e entrega acadêmica

Depende das etapas anteriores.

- [ ] Criar roteiro reproduzível com paciente fictício, documentos, áudio, vídeo e série de sinais vitais.
- [ ] Medir erros de extração/transcrição, acerto de eventos, falsos alertas, latência e consumo quando aplicável.
- [ ] Verificar falhas: arquivo incompatível, serviço indisponível, timeout, ausência de evidência e reinício durante processamento.
- [ ] Executar `uv run ruff check .`, `uv run mypy` e `uv run pytest` dentro de `tech-ai-main`.
- [x] Fazer teste integrado real com Azure Speech usando volume controlado e dados fictícios.
- [ ] Atualizar README com instalação, execução, configuração e reprodução dos exemplos.
- [ ] Produzir relatório técnico: fluxo multimodal, modelos, critérios, resultados, exemplos e limitações.
- [ ] Preparar vídeo de até 15 minutos com áudio, vídeo, anomalias, Azure e fluxo final de alertas.
- [ ] Conferir credenciais e dados antes de publicar materiais.
- [ ] Publicar vídeo no YouTube ou Vimeo e preparar entrega do código mediante autorização do usuário.

**Concluída quando:** a demonstração é reproduzível e cada requisito possui evidência de implementação ou uma lacuna explicitamente reconhecida.

## 5. Matriz de aderência ao PDF

| Requisito | Etapas | Evidência esperada |
| --- | --- | --- |
| Vídeo clínico e eventos fora do padrão | 5 | Vídeo de fisioterapia, detecções e relatório com instantes |
| Áudio e alterações vocais | 4 | Transcrição, análise do sinal, avaliação e limitações |
| Azure Speech to Text | 2 e 4 | Transcrição real pela integração |
| Azure Text Analytics: termos e sentimentos | 2 e 4 | Resultado real vinculado à transcrição |
| Anomalias em sinais vitais | 6 | Série reproduzida e alertas verificáveis |
| Evolução de prescrições | 3 e 6 | Comparação temporal de documentos do mesmo paciente |
| Padrões de movimentação durante internação | 5 e 6 | Cenário simulado a detalhar; fisioterapia sozinha é cobertura parcial |
| Alertas automáticos à equipe | 6 | Painel com origem, histórico e revisão |
| Fusão de texto, áudio e vídeo | 7 | Pergunta com múltiplas modalidades e contexto do paciente |
| Monitoramento em tempo real | 6 | Eventos emitidos durante reprodução; latência medida, sem alegar tempo real clínico |
| Código e relatório técnico | 8 | Repositório e documentação reproduzível |
| Vídeo de até 15 minutos | 8 | Demonstração e link de entrega |

## 6. Próxima tarefa e acompanhamento

**Próxima tarefa:** provisionar e integrar o Azure Document Intelligence F0 para iniciar o OCR de
laudos e prescrições fictícios, mantendo cache, limites de consumo e as ressalvas de que extração e
classificação textual não constituem diagnóstico clínico.

Para cada tarefa implementada, registrar:

- O que foi entregue e quais arquivos foram alterados.
- Como foi verificado e qual foi o resultado.
- Limitações e decisões que afetem etapas seguintes.
- Consumo de serviços pagos, quando houver.

Não marcar uma integração como concluída apenas porque existe um cliente simulado. Novas tecnologias e serviços devem ser confirmados na documentação atual durante a implementação. Commit, push e PR dependem de autorização explícita, conforme as instruções do repositório.

## Decisão posterior — Supabase

Por decisão do usuário, PostgreSQL no Supabase substitui SQLite para pacientes, conversas, mensagens, análises, tarefas e alertas. Arquivos permanecem no disco nesta primeira versão. A conexão será exclusivamente pelo backend, usando TECH_AI_DATABASE_URL no .env, já excluído do Git.

O driver psycopg foi instalado pelo usuário. A conexão TLS e a consulta somente-leitura foram confirmadas pelo usuário em seu terminal com check-db. Credenciais permanecem no .env local.

### Atualização da integração PostgreSQL

Implementados modelos, serviço e repositório PostgreSQL para pacientes fictícios e uma conversa por paciente. A API permite criar, listar com paginação e consultar a conversa, sempre no escopo do usuário autenticado. Criação de paciente/conversa é transacional, com consultas parametrizadas. Criado comando migrate-db, com versão, trava transacional, schema próprio e RLS sem políticas públicas. O uso da conexão administrativa exige manter a autorização no backend.

Validação local: Ruff aprovado; mypy aprovado em 69 arquivos; 150 testes aprovados, cobertura de 95,28%. Testes incluem isolamento, validação de entrada, parâmetros SQL, tratamento de falha na segunda inserção e caminhos de migração. O driver foi simulado; isso não comprova durabilidade no Supabase real. O usuário confirmou conexão e execução real de `migrate-db` no seu terminal, com a mensagem `Migração 1 aplicada.`. Cadastro e consulta pela API no banco real ainda precisam de validação.

A tentativa de `migrate-db` neste ambiente falhou, mas a execução posterior pelo usuário confirmou a aplicação da migração 1. Próximo passo: integrar a seleção de pacientes ao chat e validar cadastro/consulta no banco real. A primeira caixa de persistência da etapa 1 permanece aberta até essa validação. Interface de seleção, mensagens e anexos ainda não implementados. Sem alterações em Azure e sem commit/push.

### Seleção de paciente e histórico - migração 2

Implementados seleção/criação de pacientes no chat, tabela `messages`, histórico por conversa e registro de perguntas/respostas. A API filtra paciente e mensagens pelo usuário autenticado. Ruff e mypy aprovados; 159 testes aprovados, cobertura de 94,90%; JavaScript validado sintaticamente.

Na primeira tentativa real da migração 2, o comando ficou aguardando em uma repetição de `REVOKE ALL ON SCHEMA tech_ai FROM PUBLIC` e foi interrompido. A migração foi corrigida: a permissão do schema agora pertence somente à migração 1 e a trava usa `pg_try_advisory_xact_lock`, retornando erro imediatamente quando outra migração estiver ativa. O usuário confirmou que a nova execução funcionou e a migração 2 foi aplicada no Supabase. Próxima ação: validar cadastro, consulta e recarga do histórico na aplicação real.

### Melhoria da interação do chat

O teste real confirmou cadastro e persistência, mas mostrou uma resposta pouco útil para perguntas vagas e um erro técnico ao selecionar o modo com modelo sem o runtime instalado. Foi adicionada uma entrevista inicial determinística para pedidos genéricos, solicitando sintoma, início, intensidade e sinais associados antes de consultar o RAG. Quando uma busca específica não encontra evidências, a resposta também orienta quais detalhes informar.

A API agora expõe as capacidades do ambiente. A interface desabilita o modo com modelo quando Torch, Transformers, PEFT ou bitsandbytes não estiverem disponíveis, evitando expor instruções técnicas ao usuário. O histórico preserva as respostas de entrevista. A conversa foi limitada a uma coluna central para aproximar visualmente pergunta e resposta. Validação: JavaScript sem erro de sintaxe; Ruff e mypy aprovados; 169 testes aprovados, cobertura de 94,97%. O usuário confirmou em teste visual real que a entrevista inicial, a resposta fundamentada e a nova organização da conversa funcionaram como esperado.

### Botão de anexos e processador simulado - migração 3

Implementados upload autenticado por paciente, botão **+**, prévia de imagem/áudio/vídeo, armazenamento local com chave gerada pelo servidor e metadados PostgreSQL. O backend aceita JPEG/PNG, WAV/MP3 e MP4 dentro dos limites definidos, compara extensão, MIME e assinatura do conteúdo, calcula SHA-256 e não expõe chave física ou hash na API. O acesso ao arquivo, a listagem e o processamento sempre filtram proprietário e paciente.

O primeiro processador é simulado: registra estado, tentativa, resumo, observações e limitações, sem extrair informação clínica e sem consumir Azure. A migração 3 cria `attachments` e `analyses`. O usuário confirmou as migrações 3 e 4 no Supabase por meio de um upload real de PDF, com processamento e recuperação funcionando na interface. Tarefas persistidas em segundo plano permanecem para uma fatia posterior. Validação local: JavaScript sem erro de sintaxe; Ruff e mypy aprovados; 182 testes aprovados, cobertura acima de 93%.

PDF foi incluído como modalidade `document`, com limite de 25 MiB, validação da assinatura `%PDF`, persistência e visualização embutida. A migração 4 amplia a restrição de modalidades e funciona tanto para quem já aplicou a migração 3 quanto para uma instalação nova. O OCR real do PDF permanece na etapa de laudos e prescrições. Validação atual: 185 testes aprovados e cobertura de 93,54%.

### Início da etapa Azure

Preços, faixas gratuitas, regiões e comportamento de budget/spending limit foram conferidos na documentação oficial em 15 de novembro de 2026. Criada configuração separada por serviço, desativada por padrão, com segredos ocultos da representação e limites conservadores de duração, páginas, registros de texto e concorrência. O plano está em `docs/azure-poc-plan.md`. Nenhum recurso foi provisionado e nenhuma chamada Azure foi realizada.
