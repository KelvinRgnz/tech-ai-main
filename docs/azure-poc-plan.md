# Plano Azure da POC

Atualizado em 15 de novembro de 2026. A assinatura gratuita foi confirmada, um budget mensal de
R$ 20 foi criado e os recursos F0 `speech-tech-ai-poc-mikael` e
`language-tech-ai-poc-mikael` foram provisionados no grupo `rg-tech-ai-poc`, em Brazil South. Os
diagnósticos reais validaram Speech, análise de sentimento e extração de frases-chave com dados
fictícios.

## Serviços e faixas gratuitas verificadas

| Necessidade | Serviço | Faixa para a demonstração |
| --- | --- | --- |
| Transcrição | Azure Speech in Foundry Tools | F0: 5 horas/mês de transcrição em tempo real |
| Sentimento, termos e entidades | Azure Language in Foundry Tools | 5.000 registros de texto/mês compartilhados entre funcionalidades |
| OCR de laudos e prescrições | Azure Document Intelligence | F0: até 500 páginas/mês segundo a página de preços |

`brazilsouth` está listado para transcrição em tempo real, rápida e em lote. Para a
POC, usar transcrição em tempo real, porque o Speech F0 não oferece processamento em lote.
A disponibilidade do SKU F0 deve ser confirmada no portal durante a criação de cada recurso.

Fontes oficiais:

- <https://azure.microsoft.com/pricing/details/speech/>
- <https://azure.microsoft.com/pt-br/pricing/details/language/>
- <https://azure.microsoft.com/pricing/details/document-intelligence/>
- <https://learn.microsoft.com/pt-br/azure/ai-services/speech-service/regions>
- <https://learn.microsoft.com/azure/ai-services/speech-service/speech-services-quotas-and-limits>

## Proteção de custos

O spending limit de uma conta gratuita impede gastos acima do crédito enquanto estiver ativo.
Ele não permite escolher outro teto: ou permanece no valor do crédito ou é removido. Alertas de
orçamento apenas notificam e não interrompem recursos; custos podem aparecer com atraso.

Antes de provisionar:

1. Confirmar no portal o tipo da assinatura, saldo, moeda, expiração e spending limit ativo.
2. Criar um budget da assinatura com alertas em 25%, 50%, 75% e 90% do crédito.
3. Manter todos os serviços em F0 enquanto houver disponibilidade.
4. Não remover o spending limit nem migrar para pagamento conforme o uso para esta POC.
5. Verificar consumo no portal após os testes; a telemetria de custo não é instantânea.

Fontes oficiais:

- <https://learn.microsoft.com/azure/cost-management-billing/manage/spending-limit>
- <https://learn.microsoft.com/azure/cost-management-billing/costs/tutorial-acm-create-budgets>
- <https://learn.microsoft.com/azure/cost-management-billing/manage/check-free-service-usage>

## Configuração local

Cada integração fica desligada por padrão e pode ser ativada separadamente. Chaves e endpoints
devem existir apenas no `.env` local. O navegador, logs, banco e Git nunca recebem esses valores.

Limites iniciais antes de qualquer chamada Azure:

- áudio: no máximo 120 segundos;
- documento: no máximo 10 páginas por análise;
- Language: no máximo 20 registros de texto por análise;
- concorrência: uma chamada por vez.

Estimativa conservadora para até 20 áudios de demonstração, cada um limitado a 120 segundos:

- Speech: até 40 minutos, antes de repetições, dentro das 5 horas mensais do F0;
- Language: até 40 registros, considerando sentimento e frases-chave separadamente, dentro dos
  5.000 registros mensais compartilhados do F0;
- resultados concluídos são persistidos e não repetem chamadas ao reabrir ou recarregar a tela.

## Provisionamento proposto

Os serviços são provisionados um por vez. Speech F0 e Language F0 já foram criados e suas chaves
estão somente no `.env` local. Document Intelligence permanece pendente. O cliente Speech usa o
fluxo em tempo real, limita duração a 120 s e concorrência a uma chamada, e reaproveita o resultado
persistido do mesmo anexo. O Language analisa a transcrição em `pt-BR`, extraindo frases-chave e
sentimento textual sem atribuir significado diagnóstico ao resultado.

O comando `tech-ai check-speech` realiza o teste controlado sem dados pessoais: sintetiza um WAV
temporário com uma pausa intencional, transcreve o arquivo e o remove ao terminar. O teste consome
duas operações pequenas do Speech F0 (síntese e transcrição) e nunca imprime a chave.

Áudios OGG/Opus gerados pelo WhatsApp são aceitos e preservados no formato original. Um FFmpeg
empacotado no ambiente converte cada arquivo localmente para WAV PCM 16 kHz mono antes do Speech;
o WAV intermediário é removido mesmo em caso de falha. O comando `tech-ai check-language` valida
sentimento e frases-chave com um texto fictício e nunca imprime chave ou endpoint.

Critério experimental de pausas: intervalo mínimo de 0,8 s entre o fim de uma palavra reconhecida
e o início da seguinte. O relatório mostra quantidade e maior intervalo. Esse sinal não permite,
isoladamente, inferir desconforto ou dificuldade respiratória.
