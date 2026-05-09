/**
 * MedMind — Frontend Application (Premium Medical Theme)
 */

const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? `http://${window.location.hostname}:8000`
    : window.location.origin;

const SESSION_ID = localStorage.getItem("medmind_session") || crypto.randomUUID();
localStorage.setItem("medmind_session", SESSION_ID);

// ─── DOM Elements ─────────────────────────────────────────────────
const sidebar = document.getElementById("sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const newChatBtn = document.getElementById("newChatBtn");
const welcomeScreen = document.getElementById("welcomeScreen");
const chatContainer = document.getElementById("chatContainer");
const messageList = document.getElementById("messageList");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const attachBtn = document.getElementById("attachBtn");
const fileInput = document.getElementById("fileInput");
const uploadBtn = document.getElementById("uploadBtn");
const agentGrid = document.getElementById("agentGrid");
const imagePreview = document.getElementById("imagePreview");
const previewImg = document.getElementById("previewImg");
const removeImg = document.getElementById("removeImg");
const chatHistory = document.getElementById("chatHistory");
const toast = document.getElementById("toast");

const voiceBtn = document.getElementById("voiceBtn");
const setupProfileBtn = document.getElementById("setupProfileBtn");
const profileModal = document.getElementById("profileModal");
const saveProfileBtn = document.getElementById("saveProfileBtn");
const sourcesToggle = document.getElementById("sourcesToggle");
const clearChatBtn = document.getElementById("clearChatBtn");

let currentImageBase64 = null;
let isProcessing = false;
let isRecording = false;
let recognition = null;

// ─── Initialize ───────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    checkHealth();
    loadProfile();
    setupEventListeners();
    refreshHistory();
});

function setupEventListeners() {
    // Send message
    sendBtn.addEventListener("click", sendMessage);
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    userInput.addEventListener("input", () => {
        sendBtn.disabled = !userInput.value.trim() && !currentImageBase64;
    });

    // Sidebar Toggle
    sidebarToggle.addEventListener("click", () => {
        sidebar.classList.toggle("collapsed");
    });

    // New Chat
    newChatBtn.addEventListener("click", clearChat);
    clearChatBtn.addEventListener("click", clearChat);

    function clearChat() {
        messageList.innerHTML = "";
        welcomeScreen.style.display = "block";
        agentGrid.style.display = "none";
        userInput.value = "";
        userInput.style.height = "auto";
        currentImageBase64 = null;
        imagePreview.style.display = "none";
        showToast("Conversation cleared");
    }

    // Profile
    setupProfileBtn.addEventListener("click", () => {
        profileModal.classList.add("open");
        lucide.createIcons();
    });

    saveProfileBtn.addEventListener("click", saveProfile);

    // Sources Toggle
    sourcesToggle.addEventListener("click", () => {
        showToast("Medical sources are verified and listed under each AI response.");
    });

    // Image/File attachment
    attachBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileSelect);
    
    removeImg.addEventListener("click", () => {
        currentImageBase64 = null;
        imagePreview.style.display = "none";
        fileInput.value = "";
    });

    // Upload Document
    uploadBtn.addEventListener("click", () => fileInput.click());

    // Voice Input (Web Speech API)
    if (voiceBtn) {
        voiceBtn.addEventListener("click", toggleVoiceInput);
    }
}

// ─── Voice Input ─────────────────────────────────────────────────
function toggleVoiceInput() {
    if (isRecording) {
        stopVoice();
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast("Voice input is not supported in this browser. Try Chrome.", "error");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onstart = () => {
        isRecording = true;
        voiceBtn.classList.add("recording");
        voiceBtn.style.color = "var(--danger)";
        showToast("Listening... speak now");
    };

    recognition.onresult = (event) => {
        let transcript = "";
        for (let i = 0; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        userInput.value = transcript;
        userInput.style.height = "auto";
        userInput.style.height = userInput.scrollHeight + "px";
        sendBtn.disabled = !transcript.trim();
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        if (event.error === "not-allowed") {
            showToast("Microphone access denied. Please allow microphone permissions.", "error");
        } else {
            showToast(`Voice error: ${event.error}`, "error");
        }
        stopVoice();
    };

    recognition.onend = () => {
        stopVoice();
    };

    recognition.start();
}

function stopVoice() {
    isRecording = false;
    if (voiceBtn) {
        voiceBtn.classList.remove("recording");
        voiceBtn.style.color = "";
    }
    if (recognition) {
        try { recognition.stop(); } catch {}
        recognition = null;
    }
}

// ─── Chat Logic ───────────────────────────────────────────────────
async function sendMessage() {
    const text = userInput.value.trim();
    if ((!text && !currentImageBase64) || isProcessing) return;

    isProcessing = true;
    welcomeScreen.style.display = "none";

    addUserMessage(text, currentImageBase64);
    
    userInput.value = "";
    userInput.style.height = "auto";
    sendBtn.disabled = true;

    // Show agent pipeline grid (may be hidden later for conversational)
    agentGrid.style.display = "flex";
    resetAgentBadges();
    const assistantMsg = createAssistantMessage();
    const typingIndicator = addTypingIndicator(assistantMsg);

    const payload = {
        message: text || "Analyze this image",
        session_id: SESSION_ID,
        image_base64: currentImageBase64
    };

    currentImageBase64 = null;
    imagePreview.style.display = "none";

    try {
        setAgentActive("analyzer");

        const response = await fetch(`${API_BASE}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Server communication failed");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const bubble = assistantMsg.querySelector(".message-bubble");
        let streamedText = "";
        let buffer = "";
        let typingRemoved = false;
        let finalData = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE lines from buffer
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6);
                if (!jsonStr) continue;

                let event;
                try { event = JSON.parse(jsonStr); } catch (e) {
                    console.warn("[MedMind] SSE JSON parse error:", e, jsonStr.substring(0, 200));
                    continue;
                }

                if (event.type === "step") {
                    // Update agent badges based on step progress
                    if (event.step === 1) setAgentActive("analyzer");
                    if (event.step === 2) { setAgentCompleted("analyzer"); setAgentActive("retriever"); }
                    if (event.step === 3) { setAgentCompleted("retriever"); setAgentActive("reasoner"); }
                    if (event.step === 4) { setAgentCompleted("reasoner"); setAgentActive("verifier"); }
                    if (event.step === 5) setAgentCompleted("verifier");
                }

                if (event.type === "token") {
                    if (!typingRemoved) {
                        typingIndicator.remove();
                        typingRemoved = true;
                    }
                    streamedText += event.content;
                    bubble.innerHTML = `<div class="markdown-content">${formatMarkdown(streamedText)}</div>`;
                    scrollToBottom();
                }

                if (event.type === "done") {
                    finalData = event.metadata;
                }

                if (event.type === "error") {
                    throw new Error(event.message || "Pipeline error");
                }
            }
        }

        // Process any remaining data left in the buffer after stream ends
        if (buffer.trim()) {
            const remainingLines = buffer.split("\n");
            for (const line of remainingLines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6);
                if (!jsonStr) continue;
                try {
                    const event = JSON.parse(jsonStr);
                    if (event.type === "done") finalData = event.metadata;
                    if (event.type === "token" && !finalData) {
                        streamedText += event.content;
                    }
                } catch (e) {
                    console.warn("[MedMind] Failed to parse remaining SSE buffer:", e, jsonStr.substring(0, 200));
                }
            }
        }

        if (!typingRemoved) typingIndicator.remove();

        // Render the final formatted response (with sources, disclaimers, etc.)
        if (finalData) {
            renderAssistantResponse(assistantMsg, finalData);
        }

        refreshHistory();

    } catch (err) {
        typingIndicator.remove();
        assistantMsg.querySelector(".message-bubble").innerHTML = `<p style="color: var(--danger)"><strong>Error:</strong> ${err.message}</p>`;
    } finally {
        isProcessing = false;
        agentGrid.style.display = "none";
    }
}

function addUserMessage(text, imageBase64) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message user";
    
    let imageHtml = "";
    if (imageBase64) {
        imageHtml = `<img src="data:image/jpeg;base64,${imageBase64}" style="max-width: 100%; border-radius: var(--radius-md); margin-bottom: 8px; display: block;">`;
    }

    messageDiv.innerHTML = `
        <div class="message-bubble">
            ${imageHtml}
            ${escapeHtml(text)}
        </div>
        <div class="message-meta">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    
    messageList.appendChild(messageDiv);
    scrollToBottom();
}

function createAssistantMessage() {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message assistant";
    messageDiv.innerHTML = `
        <div class="message-bubble"></div>
        <div class="message-meta">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
    `;
    messageList.appendChild(messageDiv);
    scrollToBottom();
    return messageDiv;
}

function addTypingIndicator(container) {
    const bubble = container.querySelector(".message-bubble");
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = `
        <span style="width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; display: inline-block; animation: bounce 1.4s infinite ease-in-out both;"></span>
        <span style="width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; display: inline-block; animation: bounce 1.4s infinite ease-in-out both; animation-delay: 0.16s;"></span>
        <span style="width: 8px; height: 8px; background: var(--text-muted); border-radius: 50%; display: inline-block; animation: bounce 1.4s infinite ease-in-out both; animation-delay: 0.32s;"></span>
    `;
    bubble.appendChild(typing);
    return typing;
}

function renderAssistantResponse(container, data) {
    const bubble = container.querySelector(".message-bubble");

    // ── Conversational fast-path: clean, lightweight rendering ────
    if (data.is_conversational) {
        bubble.innerHTML = `<div class="markdown-content">${formatMarkdown(data.answer)}</div>`;
        lucide.createIcons();
        scrollToBottom();
        return;
    }

    // ── Full pipeline response rendering ─────────────────────────
    let reasoningHtml = "";
    if (data.image_analysis) {
        reasoningHtml = `
            <div class="reasoning-container">
                <div class="reasoning-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <span>Vision Analysis Summary</span>
                    <i data-lucide="chevron-down" style="width: 14px;"></i>
                </div>
                <div class="reasoning-content">
                    ${data.image_analysis}
                </div>
            </div>
        `;
    }

    let answerHtml = formatMarkdown(data.answer);

    let citationsHtml = "";
    if (data.sources && data.sources.length > 0) {
        citationsHtml = '<div style="margin-top: 24px; border-top: 1px solid var(--border); padding-top: 16px;"><h5 style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 12px;">Verified Sources</h5>';
        data.sources.forEach(s => {
            citationsHtml += `
                <div class="citation-card" onclick="window.open('${s.url}', '_blank')">
                    <div class="citation-icon">${s.label}</div>
                    <div class="citation-info">
                        <h5>${s.title || s.source}</h5>
                        <p>${s.source}${s.section ? ' • ' + s.section : ''}</p>
                    </div>
                </div>
            `;
        });
        citationsHtml += '</div>';
    }

    // Only show urgency badges — no time or grounding numbers
    let metaHtml = "";
    if (data.urgency === 'emergency' || data.urgency === 'high') {
        metaHtml = `<div style="display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;">`;
        if (data.urgency === 'emergency') metaHtml += `<span style="background: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 700;">🚨 EMERGENCY</span>`;
        if (data.urgency === 'high') metaHtml += `<span style="background: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 700;">⚠️ HIGH PRIORITY</span>`;
        metaHtml += `</div>`;
    }

    const pipelinePanelHtml = buildPipelinePanel(data);

    bubble.innerHTML = `
        ${reasoningHtml}
        <div class="markdown-content">${answerHtml}</div>
        ${citationsHtml}
        ${metaHtml}
        ${pipelinePanelHtml}
    `;

    lucide.createIcons();
    scrollToBottom();
}

// ─── "How I answered this" Pipeline Panel ─────────────────────────
//
// Builds a collapsible breakdown of every skill in the orchestrator
// pipeline using the full API response. Reads:
//   - data.analysis           {query_type, urgency, symptoms, medications}
//   - data.sources            list of cited sources with scores
//   - data.retrieval_confidence
//   - data.removed_citations  list of [Sx] the verifier stripped
//   - data.timings            {analyze, retrieve, reason, verify, format}
//   - data.steps_completed
//
// All fields are optional — the panel degrades gracefully when an older
// backend response shape doesn't include them.
function buildPipelinePanel(data) {
    const timings = data.timings || {};
    const analysis = data.analysis || {};
    const sources = data.sources || [];
    const removed = data.removed_citations || [];
    const stepsCompleted = data.steps_completed || 0;
    const retrievalConf = data.retrieval_confidence;

    // Compute effort percentages for each stage
    const total = ["analyze", "retrieve", "reason", "verify", "format"]
        .reduce((s, k) => s + (timings[k] || 0), 0);
    const effortPct = (key) => total > 0 ? Math.round(((timings[key] || 0) / total) * 100) : 0;

    // Header summary line — visible when collapsed.
    const summaryBits = [];
    summaryBits.push(`${stepsCompleted}/5 skills`);
    if (removed.length === 0 && sources.length > 0) {
        summaryBits.push(`✓ ${sources.length} cite${sources.length === 1 ? "" : "s"} verified`);
    } else if (removed.length > 0) {
        summaryBits.push(`${removed.length} cite${removed.length === 1 ? "" : "s"} stripped`);
    }
    const summaryText = summaryBits.join(" · ");

    // Skill rows
    const rows = [];

    // 1. Analyzer
    {
        const tags = [];
        if (analysis.query_type) tags.push(`<span class="pill">type: ${escapeAttr(analysis.query_type)}</span>`);
        if (analysis.urgency) {
            const cls = (analysis.urgency === "emergency" || analysis.urgency === "high") ? "danger"
                       : (analysis.urgency === "medium") ? "warn" : "";
            tags.push(`<span class="pill ${cls}">urgency: ${escapeAttr(analysis.urgency)}</span>`);
        }
        (analysis.symptoms || []).slice(0, 6).forEach(s => {
            tags.push(`<span class="pill">${escapeAttr(s)}</span>`);
        });
        (analysis.medications || []).slice(0, 6).forEach(m => {
            tags.push(`<span class="pill">${escapeAttr(m)}</span>`);
        });
        rows.push(skillRow("1", "Symptom Analyzer", "Parsed query into structured JSON",
            tags.length ? tags.join("") : '<span class="skill-detail">(no structured fields extracted)</span>',
            effortPct("analyze")));
    }

    // 2. Retriever
    {
        const detail = [];
        const n = sources.length;
        detail.push(`Retrieved <strong>${n}</strong> source${n === 1 ? "" : "s"} from local knowledge base`);
        rows.push(skillRow("2", "Medical Retriever", "Multi-query search + cross-encoder rerank",
            detail.join(" "), effortPct("retrieve")));
    }

    // 3. Reasoner
    {
        const detail = [];
        detail.push(`Generated answer with evidence-based citations`);
        rows.push(skillRow("3", "Clinical Reasoner", "Chain-of-thought reasoning over evidence",
            detail.join(""), effortPct("reason")));
    }

    // 4. Verifier — the headline skill
    {
        let detail = "";
        if (sources.length === 0) {
            detail = '<span class="skill-detail">No citations to verify (refusal path).</span>';
        } else if (removed.length === 0) {
            detail = `<span class="pill success">✓ all citations grounded</span>`;
        } else {
            const removedPills = removed.map(r => `<span class="pill danger">${escapeAttr(r)} stripped</span>`).join("");
            detail = `${removedPills}<div class="skill-detail" style="margin-top:4px;">Removed unsupported citation${removed.length === 1 ? "" : "s"} before you saw the answer.</div>`;
        }
        rows.push(skillRow("4", "Citation Verifier", "Re-checks every [Sx] against the actual evidence",
            detail, effortPct("verify")));
    }

    // 5. Formatter
    {
        const detail = [];
        if (analysis.urgency === "emergency") detail.push(`<span class="pill danger">emergency banner</span>`);
        else if (analysis.urgency === "high") detail.push(`<span class="pill warn">priority note</span>`);
        if (sources.length > 0) detail.push(`<span class="pill">${sources.length} source${sources.length === 1 ? "" : "s"} listed</span>`);
        if (detail.length === 0) detail.push(`<span class="pill">response formatted</span>`);
        rows.push(skillRow("5", "Safety Formatter", "Disclaimer, urgency banner, structured sources",
            detail.join(""), effortPct("format")));
    }

    // Effort bar — shows % of effort per stage
    let effortBarHtml = "";
    if (total > 0) {
        const segments = [
            ["analyze",  "Analyzer",  effortPct("analyze"),  "skill-color-analyze"],
            ["retrieve", "Retriever", effortPct("retrieve"), "skill-color-retrieve"],
            ["reason",   "Reasoner",  effortPct("reason"),   "skill-color-reason"],
            ["verify",   "Verifier",  effortPct("verify"),   "skill-color-verify"],
            ["format",   "Formatter", effortPct("format"),   "skill-color-format"],
        ];
        const segHtml = segments.map(([k, name, pct, cls]) => {
            if (pct === 0) return "";
            return `<div class="timing-bar-segment ${cls}" style="width:${pct}%" title="${name}: ${pct}% effort"></div>`;
        }).join("");
        const legend = segments.filter(([, , pct]) => pct > 0).map(([, name, pct, cls]) =>
            `<span class="legend-item"><span class="swatch ${cls}"></span>${name} ${pct}%</span>`
        ).join("");
        effortBarHtml = `
            <div class="timing-bar">
                <div class="timing-bar-label">Effort per stage</div>
                <div class="timing-bar-track">${segHtml}</div>
                <div class="timing-bar-legend">${legend}</div>
            </div>
        `;
    }

    return `
        <div class="pipeline-panel">
            <div class="pipeline-panel-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="pipeline-title">
                    <i data-lucide="cpu"></i>
                    How I answered this
                </span>
                <span class="pipeline-summary">
                    ${summaryText}
                    <i data-lucide="chevron-down" class="chevron"></i>
                </span>
            </div>
            <div class="pipeline-panel-body">
                ${rows.join("")}
                ${effortBarHtml}
            </div>
        </div>
    `;
}

function skillRow(num, name, subtitle, detailHtml, effortPercent) {
    const effortBadge = (typeof effortPercent === "number" && effortPercent > 0)
        ? `<span class="skill-time">${effortPercent}% effort</span>`
        : "";
    return `
        <div class="skill-row">
            <div class="skill-icon">${num}</div>
            <div class="skill-body">
                <div class="skill-name">
                    <span>${name}<span style="color: var(--text-muted); font-weight: 400; margin-left: 8px;">${subtitle}</span></span>
                    ${effortBadge}
                </div>
                <div class="skill-detail">${detailHtml}</div>
            </div>
        </div>
    `;
}

function escapeAttr(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─── Agent Orchestration ──────────────────────────────────────────
function resetAgentBadges() {
    document.querySelectorAll(".agent-badge").forEach(b => {
        b.className = "agent-badge";
    });
}

function setAgentActive(id) {
    const badge = document.getElementById(`agent-${id}`);
    if (badge) badge.classList.add("active");
}

function setAgentCompleted(id) {
    const badge = document.getElementById(`agent-${id}`);
    if (badge) {
        badge.classList.remove("active");
        badge.classList.add("completed");
    }
}

// ─── File Handling ────────────────────────────────────────────────
async function handleFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (ev) => {
            currentImageBase64 = ev.target.result.split(",")[1];
            previewImg.src = ev.target.result;
            imagePreview.style.display = "block";
            sendBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    } else {
        uploadDocument(file);
    }
}

async function uploadDocument(file) {
    showToast(`Uploading ${file.name}...`);
    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
        const data = await res.json();
        if (res.ok) {
            showToast(`Document ingested: ${data.chunks_added} sections`, "success");
            checkHealth();
        } else {
            showToast(data.detail || "Upload failed", "error");
        }
    } catch (e) {
        showToast("Server connection failed", "error");
    }
}

// ─── Sidebar & History ────────────────────────────────────────────
async function refreshHistory() {
    chatHistory.innerHTML = `
        <div class="history-item active">
            <i data-lucide="message-square" style="width: 14px;"></i>
            Current Session
        </div>
    `;
    lucide.createIcons();
}

async function loadProfile() {
    try {
        const res = await fetch(`${API_BASE}/profile/${SESSION_ID}`);
        if (res.ok) {
            const data = await res.json();
            if (data.profile) {
                const p = data.profile;
                document.getElementById("profileName").textContent = p.name || "Guest User";
                document.getElementById("profileSummary").textContent = p.conditions?.join(", ") || "Personalize your medical advice";
                
                // Populate inputs
                document.getElementById("profileNameInput").value = p.name || "";
                document.getElementById("profileAgeInput").value = p.age || "";
                document.getElementById("profileWeightInput").value = p.weight_kg || "";
                document.getElementById("profileHeightInput").value = p.height_cm || "";
                document.getElementById("profileConditionsInput").value = p.conditions?.join(", ") || "";
                document.getElementById("profileMedsInput").value = p.medications?.join(", ") || "";
                document.getElementById("profileAllergiesInput").value = p.allergies?.join(", ") || "";
                document.getElementById("profileGoalsInput").value = p.goals?.join(", ") || "";
            }
        }
    } catch (e) {}
}

async function saveProfile() {
    const profile = {
        name: document.getElementById("profileNameInput").value,
        age: parseInt(document.getElementById("profileAgeInput").value) || null,
        weight_kg: parseInt(document.getElementById("profileWeightInput").value) || null,
        height_cm: parseInt(document.getElementById("profileHeightInput").value) || null,
        conditions: parseList(document.getElementById("profileConditionsInput").value),
        medications: parseList(document.getElementById("profileMedsInput").value),
        allergies: parseList(document.getElementById("profileAllergiesInput").value),
        goals: parseList(document.getElementById("profileGoalsInput").value)
    };

    try {
        const res = await fetch(`${API_BASE}/profile`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: SESSION_ID, profile })
        });
        if (res.ok) {
            showToast("✅ Profile updated locally", "success");
            loadProfile();
            profileModal.classList.remove("open");
        }
    } catch (e) {
        showToast("Failed to update profile", "error");
    }
}

// ─── Utilities ────────────────────────────────────────────────────
function parseList(str) {
    return str ? str.split(",").map(s => s.trim()).filter(Boolean) : [];
}

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.status === "healthy") {
            document.getElementById("kbMedical").textContent = data.knowledge_base?.medical_kb || 0;
            document.getElementById("kbUser").textContent = data.knowledge_base?.user_documents || 0;
        }
    } catch (e) {}
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\[S(\d+)\]/g, '<span class="source-citation" onclick="scrollToSource(\'S$1\')">S$1</span>');
    
    return `<p>${html}</p>`;
}

function escapeHtml(text) {
    const p = document.createElement('p');
    p.textContent = text;
    return p.innerHTML;
}

function setQuery(text) {
    userInput.value = text;
    userInput.style.height = 'auto';
    userInput.style.height = (userInput.scrollHeight) + 'px';
    userInput.dispatchEvent(new Event('input'));
    sendMessage();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showToast(msg, type = "") {
    toast.textContent = msg;
    toast.className = `toast show ${type}`;
    setTimeout(() => { toast.classList.remove("show"); }, 3000);
}

function scrollToSource(label) {
    showToast(`Source ${label} details are listed below the response.`);
}

const style = document.createElement('style');
style.textContent = `
    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1.0); }
    }
`;
document.head.appendChild(style);
