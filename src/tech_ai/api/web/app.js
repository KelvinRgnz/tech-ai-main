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
const authGate = document.querySelector("#auth-gate");
const loginForm = document.querySelector("#login-form");
const loginUsername = document.querySelector("#login-username");
const loginPassword = document.querySelector("#login-password");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");
const sessionBox = document.querySelector("#session-box");
const sessionUser = document.querySelector("#session-user");
const logoutButton = document.querySelector("#logout-button");
const appShell = document.querySelector(".app");
const patientSelect = document.querySelector("#patient-select");
const patientForm = document.querySelector("#patient-form");
const patientName = document.querySelector("#patient-name");
const patientCreateButton = document.querySelector("#patient-create-button");
const patientFeedback = document.querySelector("#patient-feedback");
const attachmentButton = document.querySelector("#attachment-button");
const attachmentInput = document.querySelector("#attachment-input");
const attachmentFeedback = document.querySelector("#attachment-feedback");
const clearHistoryButton = document.querySelector("#clear-history");
const clearDialog = document.querySelector("#clear-dialog");
const clearCopy = document.querySelector("#clear-copy");

let signedIn = false;
let activePatient = null;

function renderEmptyState(message = "Selecione ou cadastre um paciente fictício para iniciar.") {
  transcript.innerHTML = `
    <article class="empty-card">
      <p class="eyebrow">Próximo passo</p>
      <h2>Decidir para onde ir</h2>
      <p>${escapeHtml(message)}</p>
      <div class="go-grid">
        <button type="button" class="destination light" data-go="consult">
          <span>Consulta</span>
          <small>Fazer uma pergunta</small>
        </button>
        <button type="button" class="destination light" data-go="patient">
          <span>Paciente</span>
          <small>Escolher ou criar</small>
        </button>
        <button type="button" class="destination light" data-go="attach">
          <span>Anexo</span>
          <small>Enviar um arquivo</small>
        </button>
      </div>
    </article>
  `;
  syncSuggestions();
}

function syncSuggestions() {
  chips.hidden = transcript.querySelector(".bubble") !== null;
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
  const interview = payload.mode === "interview";
  const warnings = (payload.warnings || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const card = document.createElement("article");
  card.className = "bubble answer-card";
  card.innerHTML = `
    <div class="meta-row">
      <span class="badge ${grounded ? "ok" : interview ? "interview" : "warn"}">${
        grounded
          ? "Fundamentado em fontes"
          : interview
            ? "Precisamos de mais detalhes"
            : "Sem evidência suficiente"
      }</span>
      <span class="distance">${escapeHtml(payload.model || "MedQuAD / Chroma Cloud")}</span>
    </div>
    <h3>${interview ? "Vamos entender melhor" : "Orientação acadêmica"}</h3>
    <p>${escapeHtml(answer)}</p>
    ${warnings ? `<ul class="warnings">${warnings}</ul>` : ""}
    ${
      interview
        ? ""
        : `<details class="sources-fold">
            <summary>Fontes (${sources.length})</summary>
            <div class="sources">${renderSources(sources, citations)}</div>
          </details>`
    }
    <p class="disclaimer">${escapeHtml(payload.disclaimer || "")}</p>
  `;
  transcript.appendChild(card);
  syncSuggestions();
}

function appendUser(text) {
  const bubble = document.createElement("article");
  bubble.className = "bubble user";
  bubble.textContent = text;
  transcript.appendChild(bubble);
  syncSuggestions();
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function attachmentPreview(attachment) {
  const url = `/api/patients/${activePatient.id}/attachments/${attachment.id}/content`;
  if (attachment.modality === "document") {
    return `<object class="attachment-document" data="${url}" type="application/pdf">
      <a href="${url}" target="_blank" rel="noreferrer">Abrir PDF</a>
    </object>`;
  }
  if (attachment.modality === "image") {
    return `<img class="attachment-preview" src="${url}" alt="Prévia de ${escapeHtml(attachment.original_name)}" />`;
  }
  if (attachment.modality === "audio") {
    return `<audio class="attachment-media" controls preload="metadata" src="${url}"></audio>`;
  }
  return `<video class="attachment-media" controls preload="none" src="${url}"></video>`;
}

function renderAttachment(attachment) {
  const analysis = attachment.analysis;
  const completed = analysis.status === "completed";
  const failed = analysis.status === "failed";
  const speechCompleted = analysis.processor_name.startsWith("azure-speech");
  const ocrCompleted = analysis.processor_name === "azure-document-intelligence-read";
  const videoCompleted = analysis.processor_name === "mediapipe-pose-sit-to-stand";
  const statusLabel = completed
    ? speechCompleted
      ? "Transcrição concluída"
      : ocrCompleted
        ? "OCR concluído"
        : videoCompleted
          ? "Análise de movimento concluída"
          : "Simulação concluída"
    : failed
      ? "Falha no processamento"
      : "Aguardando processamento";
  const observations = (analysis.observations || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const limitations = (analysis.limitations || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const simulated = analysis.processor_name === "simulated-multimodal-processor";
  const processAction = failed
    ? `<button type="button" class="retry-button" data-process-id="${attachment.id}">Tentar novamente</button>`
    : !completed || simulated
      ? `<button type="button" class="retry-button" data-process-id="${attachment.id}">Processar agora</button>`
      : "";
  const card = document.createElement("article");
  card.className = "bubble attachment-card";
  card.dataset.attachmentId = attachment.id;
  card.innerHTML = `
    <div class="meta-row">
      <span class="badge ${completed ? "ok" : failed ? "warn" : "interview"}">${statusLabel}</span>
      <span class="distance">${escapeHtml(attachment.modality.toUpperCase())}</span>
    </div>
    <h3>${escapeHtml(attachment.original_name)}</h3>
    <p class="attachment-size">${formatBytes(attachment.size_bytes)} · ${escapeHtml(attachment.content_type)}</p>
    ${attachmentPreview(attachment)}
    ${analysis.summary ? `<p>${escapeHtml(analysis.summary)}</p>` : ""}
    ${observations ? `<h4>Observações</h4><ul>${observations}</ul>` : ""}
    ${limitations ? `<h4>Limitações</h4><ul class="warnings">${limitations}</ul>` : ""}
    ${processAction}
  `;
  const existing = transcript.querySelector(`[data-attachment-id="${attachment.id}"]`);
  if (existing) existing.replaceWith(card);
  else transcript.appendChild(card);
  card.querySelector("[data-process-id]")?.addEventListener("click", () => {
    processAttachment(attachment.id).catch(showAttachmentError);
  });
  syncSuggestions();
}

function setComposerEnabled(enabled) {
  const available = enabled && signedIn && Boolean(activePatient);
  question.disabled = !available;
  sendButton.disabled = !available;
  attachmentButton.disabled = !available;
  clearHistoryButton.disabled = !available;
}

function markDestination(destination) {
  for (const button of document.querySelectorAll(".destinations [data-go]")) {
    button.toggleAttribute("aria-current", button.dataset.go === destination);
  }
}

function goTo(destination) {
  markDestination(destination);
  if (destination === "patient") {
    document.querySelector("#patient-panel")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    (activePatient ? patientSelect : patientName).focus();
    return;
  }
  if (!signedIn) {
    showLogin("Entre para continuar.");
    return;
  }
  if (!activePatient) {
    patientFeedback.textContent = "Crie ou selecione um paciente para continuar.";
    patientName.focus();
    return;
  }
  if (destination === "attach") {
    attachmentInput.click();
    return;
  }
  question.focus();
}

function setBusy(isBusy) {
  sendButton.disabled = isBusy || !signedIn || !activePatient;
  sendButton.textContent = isBusy ? "Consultando..." : "Consultar";
  statusCopy.textContent = isBusy
    ? "Buscando evidências no conhecimento indexado."
    : activePatient
      ? `Conversa de ${activePatient.display_name}.`
      : "Selecione um paciente.";
}

async function consult(questionText) {
  if (!signedIn) {
    showLogin("Entre para consultar o assistente.");
    throw new Error("Autenticação obrigatória.");
  }
  if (!activePatient) {
    throw new Error("Selecione um paciente para registrar a conversa.");
  }
  const mode = modeSelect.value;
  const response = await fetch(mode === "ask" ? "/api/ask" : "/api/consult", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: questionText, patient_id: activePatient.id }),
  });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      showLogin("Sessão expirada. Entre novamente.");
    }
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item).join(" ")
      : detail;
    if (String(message).includes("Extras de runtime")) {
      throw new Error(
        "O modo com modelo não está disponível nesta instalação. Use Evidências do MedQuAD."
      );
    }
    throw new Error(message || "Não foi possível concluir a consulta.");
  }
  return payload;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!signedIn) {
    showLogin("Entre para consultar o assistente.");
    return;
  }
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
    setBusy(false);
    transcript.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
  }
});

async function requestJson(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      showLogin("Sessão expirada. Entre novamente.");
    }
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || item).join(" ")
      : detail;
    throw new Error(message || "A operação não pôde ser concluída.");
  }
  return payload;
}

async function configureCapabilities() {
  const capabilities = await requestJson("/api/capabilities");
  const askOption = modeSelect.querySelector('option[value="ask"]');
  askOption.disabled = !capabilities.assistant_runtime;
  askOption.textContent = capabilities.assistant_runtime
    ? "Resposta com o modelo"
    : "Resposta com o modelo (runtime não instalado)";
  if (!capabilities.assistant_runtime && modeSelect.value === "ask") {
    modeSelect.value = "consult";
  }
}

function renderHistory(messages) {
  transcript.innerHTML = "";
  if (!messages.length) {
    renderEmptyState(
      `Conversa de ${activePatient.display_name}. Faça a primeira pergunta clínica.`
    );
    return;
  }
  for (const message of messages) {
    if (message.role === "user") {
      appendUser(message.content);
    } else if (message.payload) {
      renderAssistant(message.payload);
    } else {
      renderAssistant({ answer: message.content, grounded: false, sources: [] });
    }
  }
}

function renderConversation(messages, attachments) {
  transcript.innerHTML = "";
  if (!messages.length && !attachments.length) {
    renderEmptyState(
      `Conversa de ${activePatient.display_name}. Faça a primeira pergunta ou anexe um arquivo.`
    );
    return;
  }
  for (const message of messages) {
    if (message.role === "user") appendUser(message.content);
    else if (message.payload) renderAssistant(message.payload);
    else renderAssistant({ answer: message.content, grounded: false, sources: [] });
  }
  for (const attachment of attachments) renderAttachment(attachment);
}

async function selectPatient(patient) {
  activePatient = patient;
  patientSelect.value = patient.id;
  setComposerEnabled(true);
  statusCopy.textContent = `Carregando conversa de ${patient.display_name}...`;
  try {
    const [messages, attachments] = await Promise.all([
      requestJson(`/api/patients/${patient.id}/messages`),
      requestJson(`/api/patients/${patient.id}/attachments`),
    ]);
    renderConversation(messages, attachments);
    statusCopy.textContent = `Conversa de ${patient.display_name}.`;
  } catch (error) {
    activePatient = null;
    setComposerEnabled(false);
    renderEmptyState(error.message);
    statusCopy.textContent = "Não foi possível carregar a conversa.";
  }
}

async function loadPatients(preferredId = null) {
  const patients = await requestJson("/api/patients");
  patientSelect.innerHTML = "";
  if (!patients.length) {
    activePatient = null;
    patientSelect.disabled = true;
    patientSelect.add(new Option("Nenhum paciente cadastrado", ""));
    setComposerEnabled(false);
    renderEmptyState();
    statusCopy.textContent = "Cadastre um paciente fictício para começar.";
    return;
  }
  patientSelect.disabled = false;
  for (const patient of patients) {
    patientSelect.add(new Option(patient.display_name, patient.id));
  }
  const selected = patients.find((patient) => patient.id === preferredId) || patients[0];
  await selectPatient(selected);
}

patientSelect.addEventListener("change", async () => {
  if (!patientSelect.value) return;
  const patients = await requestJson("/api/patients");
  const selected = patients.find((patient) => patient.id === patientSelect.value);
  if (selected) await selectPatient(selected);
});

patientForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const displayName = patientName.value.trim();
  if (!displayName) return;
  patientCreateButton.disabled = true;
  patientFeedback.textContent = "Criando paciente...";
  try {
    const patient = await requestJson("/api/patients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName }),
    });
    patientName.value = "";
    patientFeedback.textContent = "Paciente criado.";
    await loadPatients(patient.id);
  } catch (error) {
    patientFeedback.textContent = error.message;
  } finally {
    patientCreateButton.disabled = false;
  }
});

function declaredType(file) {
  if (file.type) return file.type;
  const extension = file.name.toLowerCase().split(".").pop();
  return {
    pdf: "application/pdf",
    jpg: "image/jpeg",
    jpeg: "image/jpeg",
    png: "image/png",
    wav: "audio/wav",
    mp3: "audio/mpeg",
    ogg: "audio/ogg",
    mp4: "video/mp4",
  }[extension] || "application/octet-stream";
}

function showAttachmentError(error) {
  attachmentFeedback.textContent = error.message || "Não foi possível anexar o arquivo.";
  statusCopy.textContent = "O anexo não foi processado.";
}

async function processAttachment(attachmentId) {
  attachmentFeedback.textContent = "Processando o anexo...";
  const processed = await requestJson(
    `/api/patients/${activePatient.id}/attachments/${attachmentId}/process`,
    { method: "POST" }
  );
  renderAttachment(processed);
  const processor = processed.analysis.processor_name;
  attachmentFeedback.textContent = processor.startsWith("azure-speech")
    ? processed.analysis.processor_name === "azure-speech-language"
      ? "Transcrição e análise textual concluídas com a Azure."
      : "Transcrição concluída com o Azure Speech."
    : processor === "azure-document-intelligence-read"
      ? "Texto extraído com o Azure Document Intelligence."
    : processor === "mediapipe-pose-sit-to-stand"
      ? "Movimento analisado localmente com o MediaPipe Pose."
    : "Simulação local concluída.";
  statusCopy.textContent = `Conversa de ${activePatient.display_name}.`;
}

attachmentButton.addEventListener("click", () => attachmentInput.click());

attachmentInput.addEventListener("change", async () => {
  const file = attachmentInput.files?.[0];
  attachmentInput.value = "";
  if (!file || !activePatient) return;
  if (transcript.querySelector(".empty-card")) transcript.innerHTML = "";
  attachmentButton.disabled = true;
  attachmentFeedback.textContent = `Enviando ${file.name}...`;
  statusCopy.textContent = "Validando e armazenando o anexo.";
  try {
    const uploaded = await requestJson(
      `/api/patients/${activePatient.id}/attachments?filename=${encodeURIComponent(file.name)}`,
      {
        method: "POST",
        headers: { "Content-Type": declaredType(file) },
        body: file,
      }
    );
    renderAttachment(uploaded);
    await processAttachment(uploaded.id);
    transcript.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
  } catch (error) {
    showAttachmentError(error);
  } finally {
    attachmentButton.disabled = !signedIn || !activePatient;
  }
});

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target.closest("[data-go]") : null;
  if (!target) return;
  goTo(target.dataset.go || "consult");
});

clearHistoryButton.addEventListener("click", () => {
  if (!activePatient || typeof clearDialog.showModal !== "function") return;
  const attachments = transcript.querySelectorAll(".attachment-card").length;
  const kept = attachments === 1
    ? "1 anexo continua na conversa."
    : attachments > 1
      ? `${attachments} anexos continuam na conversa.`
      : "Não há anexos nesta conversa.";
  clearCopy.textContent = `As perguntas e respostas de ${activePatient.display_name} serão apagadas. ${kept}`;
  clearDialog.showModal();
});

clearDialog.addEventListener("close", async () => {
  if (clearDialog.returnValue !== "confirm" || !activePatient) return;
  const patient = activePatient;
  clearHistoryButton.disabled = true;
  try {
    const result = await requestJson(`/api/patients/${patient.id}/messages`, { method: "DELETE" });
    await selectPatient(patient);
    if (activePatient?.id === patient.id) {
      statusCopy.textContent = result.deleted
        ? `Histórico de ${patient.display_name} apagado. Os anexos foram mantidos.`
        : `Não havia mensagens para apagar em ${patient.display_name}.`;
    }
  } catch (error) {
    patientFeedback.textContent = error.message;
    statusCopy.textContent = "Não foi possível apagar o histórico.";
    clearHistoryButton.disabled = !signedIn || !activePatient;
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

function showLogin(message) {
  signedIn = false;
  activePatient = null;
  document.body.classList.add("is-locked");
  document.body.classList.remove("is-ready");
  authGate.hidden = false;
  sessionBox.hidden = true;
  appShell?.setAttribute("aria-hidden", "true");
  setComposerEnabled(false);
  if (message) {
    loginError.hidden = false;
    loginError.textContent = message;
  } else {
    loginError.hidden = true;
    loginError.textContent = "";
  }
  loginUsername.focus();
}

function showApp(username) {
  signedIn = true;
  document.body.classList.remove("is-locked");
  document.body.classList.add("is-ready");
  authGate.hidden = true;
  sessionBox.hidden = false;
  sessionUser.textContent = username;
  appShell?.removeAttribute("aria-hidden");
  loginError.hidden = true;
  loginPassword.value = "";
  setComposerEnabled(false);
  loadPatients().catch((error) => {
    patientFeedback.textContent = error.message;
    renderEmptyState("Não foi possível carregar os pacientes.");
  });
  configureCapabilities().catch(() => {
    const askOption = modeSelect.querySelector('option[value="ask"]');
    askOption.disabled = true;
    askOption.textContent = "Resposta com o modelo (indisponível)";
    modeSelect.value = "consult";
  });
}

async function readSession() {
  const response = await fetch("/api/me", { credentials: "same-origin" });
  if (!response.ok) {
    showLogin();
    return;
  }
  const payload = await response.json();
  showApp(payload.username);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginButton.disabled = true;
  loginError.hidden = true;
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: loginUsername.value.trim(),
        password: loginPassword.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Não foi possível entrar.");
    }
    showApp(payload.username);
  } catch (error) {
    loginError.hidden = false;
    loginError.textContent = error.message || "Credenciais inválidas.";
  } finally {
    loginButton.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
  showLogin();
  loginUsername.focus();
});

readSession();
renderEmptyState();
