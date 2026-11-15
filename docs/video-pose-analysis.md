# Análise experimental de vídeo de fisioterapia

## Objetivo e escopo

Esta POC analisa um exercício encenado de sentar e levantar. O resultado serve para demonstrar
estimativa de pose, fases do movimento, repetições e eventos temporais. Não é um instrumento
clínico validado e não diagnostica fadiga, dor, risco de queda ou qualidade funcional.

## Modelo escolhido

Foi escolhido o **MediaPipe Pose Landmarker Lite** como alternativa ao OpenPose e ao YOLO Pose.
O enunciado cita esses modelos como exemplos, sem exigir um fornecedor específico. A alternativa
selecionada:

- possui SDK Python e modo temporal próprio para vídeo;
- estima 33 pontos corporais em coordenadas normalizadas e tridimensionais;
- foi otimizada para aplicações locais de movimento e fitness;
- evita adicionar PyTorch e pesos grandes ao ambiente leve da demonstração.

Referências oficiais:

- [Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)
- [API Python `detect_for_video`](https://developers.google.com/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmarker#detect_for_video)

## Protocolo de gravação

1. Usar câmera fixa em orientação vertical.
2. Manter cabeça, tronco, quadril, joelhos e tornozelos visíveis.
3. Posicionar a pessoa lateralmente e evitar que móveis cubram as articulações.
4. Manter iluminação suficiente e apenas uma pessoa no enquadramento.
5. Iniciar sentado, executar ciclos completos e terminar sentado.
6. Registrar manualmente quantas repetições e pausas foram encenadas para comparação.

## Critérios experimentais versão 1.0

O vídeo é amostrado por padrão a 5 quadros por segundo. Em cada amostra válida, o lado do corpo
com maior visibilidade fornece ombro, quadril, joelho e tornozelo.

| Medida | Critério |
|---|---|
| Posição sentada | ângulo do joelho menor ou igual a 115° |
| Posição em pé | ângulo do joelho maior ou igual a 150° |
| Repetição | sequência sentada → em pé → sentada |
| Ciclo incompleto | vídeo termina em pé antes do retorno à posição sentada |
| Fase prolongada | permanência de pelo menos 5 s antes de mudar de posição |
| Cobertura | quadros com pose confiável / quadros amostrados |

A faixa entre 115° e 150° funciona como histerese: é tratada como transição e evita contar
oscilações próximas a um único limiar. Uma fase prolongada é um evento para revisão, não uma
anomalia clínica.

## Limitações

- Os limiares foram definidos para a gravação acadêmica e precisam ser comparados com anotação
  manual.
- Mudanças de câmera, perspectiva, altura do assento, roupas e oclusões alteram os ângulos.
- Uma única câmera não mede força, dor, equilíbrio ou profundidade com precisão clínica.
- O vídeo gravado não demonstra monitoramento contínuo durante uma internação.
- O relatório deve sempre manter os instantes e o vídeo original disponíveis para revisão.

## Validação da gravação fictícia

Antes de considerar o resultado correto, a gravação `teste_video.mp4` foi anotada manualmente pelo
autor do vídeo com os seguintes eventos esperados:

- cinco repetições completas;
- uma pausa longa na posição sentada;
- início de uma sexta repetição, sem retornar à posição sentada antes do fim do vídeo.

O processamento automático encontrou cinco repetições completas, uma fase sentada de 12,8 s e
um ciclo incompleto iniciado aos 40,3 s. A pose foi detectada em 100% dos quadros amostrados e o
ângulo do joelho variou entre 70,0° e 174,6°. Assim, os três eventos anotados foram encontrados
nesta gravação. Esse resultado valida somente o cenário encenado e não estima desempenho em
outras pessoas, câmeras ou exercícios.

O resultado também foi validado na interface autenticada: o MP4 permaneceu associado ao paciente,
o processamento foi recuperável pelo botão **Processar agora** e o relatório persistido voltou a
ser exibido ao carregar o histórico.

## Execução reproduzível

```powershell
uv sync --dev --extra azure --extra video

New-Item -ItemType Directory -Force .data/models | Out-Null
Invoke-WebRequest `
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task" `
  -OutFile ".data/models/pose_landmarker_lite.task"

uv run --no-sync tech-ai check-video --file ".data/samples/teste_video.mp4"
```

Para habilitar o mesmo analisador na interface:

```dotenv
TECH_AI_VIDEO_ENABLED=true
TECH_AI_VIDEO_MODEL_PATH=.data/models/pose_landmarker_lite.task
TECH_AI_VIDEO_SAMPLE_FPS=5
```
