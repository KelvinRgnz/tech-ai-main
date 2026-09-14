const SUGGESTIONS = [
  "Quais são os sintomas da diabetes?",
  "O que é transtorno de estresse pós-traumático?",
  "O que causa pressão alta?",
];

const transcript = document.querySelector("#transcript");
const form = document.querySelector("#consult-form");
const question = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const modeSelect = document.querySelector("#mode-select");
const statusCopy = document.querySelector("#status-copy");
const chips = document.querySelector("#chips");

function renderEmptyState() {
  transcript.innerHTML = `
    <article class="empty-card">
      <p>
        Faça uma pergunta clínica objetiva. O assistente recupera trechos do
        MedQuAD, mostra a resposta mais próxima e lista as fontes usadas.
      </p>
    </article>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function parseEvidence(text) {
  const topic = text.match(/(?:Tópico médico|Medical topic):\s*(.+)/i);
  const asked = text.match(/(?:Pergunta|Question):\s*([\s\S]*?)\n(?:Resposta|Answer):/i);
  const answered = text.match(/(?:Resposta|Answer):\s*([\s\S]+)/i);
  return {
    topic: topic ? topic[1].trim() : "",
    question: asked ? asked[1].trim() : "",
    answer: answered ? answered[1].trim() : text,
  };
}

function relevance(distance) {
  const score = Math.max(0, Math.min(100, Math.round((1 - Number(distance)) * 100)));
  return `${score}% de proximidade`;
}

function renderSources(sources, citations) {
  if (!sources.length) {
    return `<p class="disclaimer">Nenhuma evidência passou pelo filtro de distância.</p>`;
  }
  return sources
    .map((source, index) => {
      const citation = citations[index] || {};
      const evidence = parseEvidence(source.text || "");
      const focus = citation.focus || evidence.topic || "Tema não informado";
      const url = citation.source_url
        ? `<a href="${escapeHtml(citation.source_url)}" target="_blank" rel="noreferrer">Abrir fonte</a>`
        : "Fonte sem URL";
      const chunkId = citation.chunk_id || source.chunk_id || source.record_id || "";
      const documentId = citation.document_id || source.document_id || "";
      const parentId = documentId || citation.record_id || source.record_id || "";
      const excerpt = evidence.answer
        ? `<h3>Trecho recuperado</h3><p>${escapeHtml(evidence.answer)}</p>`
        : "";
      return `
        <article class="source-card">
          <div class="source-top">
            <strong>${escapeHtml(citation.citation || `[${index + 1}]`)} ${escapeHtml(focus)}</strong>
            <span class="distance">${relevance(source.distance)}</span>
          </div>
          ${evidence.question ? `<h3>Pergunta da fonte</h3><p>${escapeHtml(evidence.question)}</p>` : ""}
          ${excerpt}
          <p class="disclaimer">${url} · registro-pai ${escapeHtml(parentId)} · chunk ${escapeHtml(chunkId)}</p>
        </article>
      `;
    })
    .join("");
}

function renderAssistant(payload) {
  const sources = payload.sources || [];
  const citations = payload.citations || payload.sources || [];
  const first = sources[0] ? parseEvidence(sources[0].text || "") : null;
  const answer = payload.answer || first?.answer || "Não encontrei evidências suficientemente relacionadas.";
  const grounded = payload.grounded !== false && sources.length > 0;
  const warnings = (payload.warnings || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const card = document.createElement("article");
  card.className = "bubble answer-card";
  card.innerHTML = `
    <div class="meta-row">
      <span class="badge ${grounded ? "ok" : "warn"}">${grounded ? "Fundamentado em fontes" : "Sem evidência suficiente"}</span>
      <span class="distance">${escapeHtml(payload.model || "MedQuAD / Chroma Cloud")}</span>
    </div>
    <h3>Orientação acadêmica</h3>
    <p>${escapeHtml(answer)}</p>
    ${warnings ? `<ul class="warnings">${warnings}</ul>` : ""}
    <h3>Fontes</h3>
    <div class="sources">${renderSources(sources, citations)}</div>
    <p class="disclaimer">${escapeHtml(payload.disclaimer || "")}</p>
  `;
  transcript.appendChild(card);
}

function appendUser(text) {
  const bubble = document.createElement("article");
  bubble.className = "bubble user";
  bubble.textContent = text;
  transcript.appendChild(bubble);
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy;
  sendButton.textContent = isBusy ? "Consultando..." : "Consultar";
  statusCopy.textContent = isBusy
    ? "Buscando evidências no conhecimento indexado."
    : "Pronto para uma pergunta.";
}

async function consult(questionText) {
  const mode = modeSelect.value;
  const response = await fetch(mode === "ask" ? "/api/ask" : "/api/consult", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: questionText }),
  });
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item).join(" ")
      : detail;
    throw new Error(message || "Não foi possível concluir a consulta.");
  }
  return payload;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = question.value.trim();
  if (!text) {
    return;
  }
  if (transcript.querySelector(".empty-card")) {
    transcript.innerHTML = "";
  }
  appendUser(text);
  question.value = "";
  setBusy(true);
  try {
    renderAssistant(await consult(text));
  } catch (error) {
    const card = document.createElement("article");
    card.className = "bubble answer-card";
    card.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
    transcript.appendChild(card);
    statusCopy.textContent = "A consulta falhou. Revise a pergunta ou o runtime.";
  } finally {
    sendButton.disabled = false;
    sendButton.textContent = "Consultar";
    transcript.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
  }
});

question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

for (const suggestion of SUGGESTIONS) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = suggestion;
  chip.addEventListener("click", () => {
    question.value = suggestion;
    question.focus();
  });
  chips.appendChild(chip);
}

renderEmptyState();
