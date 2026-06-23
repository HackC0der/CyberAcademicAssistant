/**
 * 学术智能体平台 - 前端交互逻辑
 * 包含：文献匹配智能体、Idea 辩论智能体（审稿人/导师共享上下文）
 */

const chatContainer = document.getElementById('chat-container');
const messagesDiv = document.getElementById('messages');
const welcomeScreen = document.getElementById('welcome-screen');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const statsInfo = document.getElementById('stats-info');
const chatHistory = document.getElementById('chat-history');
const personaSwitch = document.getElementById('persona-switch');

// ========== 全局状态 ==========
let currentSessionId = null;
let currentMode = 'literature';   // 'literature' | 'debate'
let currentPersona = 'reviewer';  // 'reviewer' | 'mentor'，仅 debate 模式
let sessionsCache = [];
const activeRequests = new Map();

// PDF 上下文（上传后暂存，发送后清空）
let pendingPdf = null;  // { filename, text, images }

// ========== 会话持久化 ==========

async function loadAllSessions() {
    try { const r = await fetch('/api/sessions'); sessionsCache = await r.json(); }
    catch { sessionsCache = []; }
    return sessionsCache;
}

function getCachedSession(id) { return sessionsCache.find(s => s.id === id) || null; }

async function saveSession(session) {
    try {
        const r = await fetch(`/api/sessions/${session.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(session),
        });
        const updated = await r.json();
        const idx = sessionsCache.findIndex(s => s.id === session.id);
        if (idx >= 0) sessionsCache[idx] = updated; else sessionsCache.unshift(updated);
    } catch (e) { console.error('保存会话失败:', e); }
    renderSidebar();
}

async function deleteSession(id) {
    const req = activeRequests.get(id);
    if (req) { req.abortController.abort(); activeRequests.delete(id); }
    try { await fetch(`/api/sessions/${id}`, { method: 'DELETE' }); } catch {}
    sessionsCache = sessionsCache.filter(s => s.id !== id);
    if (currentSessionId === id) { if (sessionsCache.length > 0) switchSession(sessionsCache[0].id); else newChat(); }
    else renderSidebar();
}

async function createSession(title) {
    try {
        const r = await fetch('/api/sessions', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
        const session = await r.json();
        sessionsCache.unshift(session);
        return session;
    } catch (e) { console.error('创建会话失败:', e); return null; }
}

function generateSessionTitle(messages) {
    const first = messages.find(m => m.role === 'user');
    if (!first) return '新对话';
    const text = first.content.trim();
    return text.length > 28 ? text.slice(0, 28) + '...' : text;
}

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    loadStats();
    setupEventListeners();
    initResize();
    await loadAllSessions();
    renderSidebar();
    if (sessionsCache.length > 0) switchSession(sessionsCache[0].id);
});

function loadStats() {
    fetch('/api/stats').then(r => r.json()).then(data => {
        const lines = [`共 ${data.total} 篇论文`];
        for (const [c, n] of Object.entries(data.by_conference)) lines.push(`${c}: ${n} 篇`);
        statsInfo.innerHTML = lines.join('<br>');
    }).catch(() => { statsInfo.textContent = '统计信息加载失败'; });
}

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    userInput.addEventListener('input', autoResize);
    newChatBtn.addEventListener('click', newChat);

    // PDF 上传
    const pdfUpload = document.getElementById('pdf-upload');
    const pdfBtn = document.getElementById('pdf-btn');
    const pdfClear = document.getElementById('pdf-clear');
    pdfBtn.addEventListener('click', () => pdfUpload.click());
    pdfUpload.addEventListener('change', handlePdfUpload);
    pdfClear.addEventListener('click', clearPdf);

    // 示例查询
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            userInput.value = btn.dataset.query;
            autoResize();
            sendMessage();
        });
    });

    // 智能体模式切换
    document.querySelectorAll('.agent-tab').forEach(tab => {
        tab.addEventListener('click', () => switchMode(tab.dataset.mode));
    });

    // 人格切换（共享上下文）
    document.querySelectorAll('.persona-btn').forEach(btn => {
        btn.addEventListener('click', () => switchPersona(btn.dataset.persona));
    });
}

// ========== 模式切换 ==========

function switchMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.agent-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
    personaSwitch.style.display = mode === 'debate' ? '' : 'none';
    updatePlaceholder();
}

function switchPersona(persona) {
    currentPersona = persona;
    document.querySelectorAll('.persona-btn').forEach(b => b.classList.toggle('active', b.dataset.persona === persona));
    updatePlaceholder();
}

function updatePlaceholder() {
    const hint = document.getElementById('input-hint');
    if (currentMode === 'literature') {
        userInput.placeholder = '描述你的研究课题，例如：我对侧信道攻击感兴趣...';
        hint.textContent = '按 Enter 发送，Shift+Enter 换行 | TF-IDF 初筛 + LLM 语义排序';
    } else if (currentPersona === 'reviewer') {
        userInput.placeholder = '描述你的研究想法，审稿人将进行严厉质疑...';
        hint.textContent = '按 Enter 发送 | 🔍 审稿人模式：可随时切换为导师模式';
    } else {
        userInput.placeholder = '描述你的研究想法，导师将帮你打磨创新点...';
        hint.textContent = '按 Enter 发送 | 🎓 导师模式：可随时切换为审稿人模式';
    }
}

// ========== PDF 上传 ==========

async function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const indicator = document.getElementById('pdf-indicator');
    const nameEl = document.getElementById('pdf-name');
    nameEl.textContent = `正在解析: ${file.name}...`;
    indicator.style.display = '';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload-pdf', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        pendingPdf = { filename: data.filename, text: data.text, images: data.images || [] };
        nameEl.textContent = `${data.filename} (${data.pages}页, ${data.text_length}字)`;
    } catch (err) {
        nameEl.textContent = `解析失败: ${err.message}`;
        pendingPdf = null;
        setTimeout(() => { indicator.style.display = 'none'; }, 3000);
    }

    // 重置 input 以便重复上传同一文件
    e.target.value = '';
}

function clearPdf() {
    pendingPdf = null;
    document.getElementById('pdf-indicator').style.display = 'none';
}

// ========== 主题 ==========

function initTheme() {
    const THEME_KEY = 'literature_agent_theme';
    const toggle = document.getElementById('theme-toggle');
    const saved = localStorage.getItem(THEME_KEY) || 'dark';
    applyTheme(saved);
    toggle.addEventListener('click', () => {
        const next = (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        localStorage.setItem(THEME_KEY, next);
    });
}

function applyTheme(theme) {
    const toggle = document.getElementById('theme-toggle');
    if (theme === 'light') { document.documentElement.setAttribute('data-theme', 'light'); toggle.textContent = '☀️'; toggle.title = '切换暗色'; }
    else { document.documentElement.removeAttribute('data-theme'); toggle.textContent = '🌙'; toggle.title = '切换亮色'; }
}

// ========== 侧边栏 ==========

function renderSidebar() {
    chatHistory.innerHTML = '';
    if (sessionsCache.length === 0) { chatHistory.innerHTML = '<div class="sidebar-empty">暂无对话</div>'; return; }
    sessionsCache.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item' + (session.id === currentSessionId ? ' active' : '');
        // 图标：根据最后一条 AI 消息判断
        const icon = document.createElement('span');
        icon.className = 'session-icon';
        const lastAi = [...(session.messages || [])].reverse().find(m => m.role === 'assistant');
        if (lastAi && lastAi.persona === 'reviewer') icon.textContent = '🔍';
        else if (lastAi && lastAi.persona === 'mentor') icon.textContent = '🎓';
        else icon.textContent = '📚';
        item.appendChild(icon);
        // 忙碌指示
        if (activeRequests.has(session.id)) {
            const dot = document.createElement('span');
            dot.className = 'session-busy'; dot.textContent = '●';
            item.appendChild(dot);
        }
        const title = document.createElement('span');
        title.className = 'session-title';
        title.textContent = session.title || '新对话';
        title.title = session.title || '新对话';
        const delBtn = document.createElement('button');
        delBtn.className = 'session-delete'; delBtn.innerHTML = '×'; delBtn.title = '删除';
        delBtn.addEventListener('click', e => { e.stopPropagation(); if (confirm('确定删除此对话？')) deleteSession(session.id); });
        item.addEventListener('click', () => switchSession(session.id));
        item.appendChild(title); item.appendChild(delBtn);
        chatHistory.appendChild(item);
    });
}

// ========== 会话切换 ==========

function switchSession(id) {
    if (currentSessionId === id) return;
    currentSessionId = id;
    const session = getCachedSession(id);
    if (!session) return;

    welcomeScreen.classList.add('hidden');
    messagesDiv.innerHTML = '';
    (session.messages || []).forEach(msg => {
        const agentType = msg.persona || 'literature';
        appendMessageToDOM(msg.role, msg.content, agentType);
    });

    const req = activeRequests.get(id);
    if (req) {
        const aiMsg = appendMessageToDOM('assistant', '');
        const contentEl = aiMsg.querySelector('.message-content');
        contentEl.innerHTML = ''; contentEl.appendChild(req.progressEl); contentEl.appendChild(req.resultEl);
    }
    updateBtnState(); renderSidebar(); scrollToBottom(); userInput.focus();
}

// ========== 新建会话 ==========

function newChat() {
    currentSessionId = null;
    messagesDiv.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    userInput.value = ''; userInput.style.height = 'auto';
    updateBtnState(); renderSidebar();
}

// ========== 按钮状态 ==========

function updateBtnState() {
    const sending = currentSessionId && activeRequests.has(currentSessionId);
    sendBtn.disabled = !!sending; userInput.disabled = !!sending;
}

// ========== 发送消息 ==========

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    if (currentSessionId && activeRequests.has(currentSessionId)) return;

    welcomeScreen.classList.add('hidden');

    // 创建新会话
    if (!currentSessionId) {
        const title = generateSessionTitle([{ role: 'user', content: text }]);
        const newSess = await createSession(title);
        if (!newSess) return;
        currentSessionId = newSess.id;
    }

    // 保存用户消息
    const session = getCachedSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    if (session.messages.filter(m => m.role === 'user').length === 1) session.title = generateSessionTitle(session.messages);
    await saveSession(session);

    // 记录当前 persona 用于后续保存 AI 回复
    const requestPersona = currentPersona;

    // DOM
    appendMessageToDOM('user', text);
    userInput.value = ''; userInput.style.height = 'auto';

    // 进度条 + 结果区（用请求时的 persona 决定头像）
    const agentType = currentMode === 'debate' ? requestPersona : 'literature';
    const progressEl = createProgressBar();
    const resultEl = document.createElement('div');
    const aiMsg = appendMessageToDOM('assistant', '', agentType);
    const contentEl = aiMsg.querySelector('.message-content');
    contentEl.innerHTML = ''; contentEl.appendChild(progressEl); contentEl.appendChild(resultEl);

    // 请求
    const abortController = new AbortController();
    const reqState = { fullText: '', progressEl, resultEl, abortController, persona: agentType };
    const sid = currentSessionId;
    activeRequests.set(sid, reqState);
    updateBtnState(); renderSidebar();

    // 构建历史与 API
    const history = session.messages.slice(-10);
    let apiEndpoint, body;
    if (currentMode === 'debate') {
        apiEndpoint = '/api/debate';
        body = { message: text, history: history, mode: currentPersona };
    } else {
        apiEndpoint = '/api/chat';
        body = { message: text, history: history };
    }

    // 附带 PDF 上下文
    if (pendingPdf) {
        body.pdf_context = pendingPdf.text;
        body.pdf_filename = pendingPdf.filename;
        clearPdf();
    }

    fetch(apiEndpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body), signal: abortController.signal,
    }).then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        function read() {
            reader.read().then(({ done, value }) => {
                if (done) { onComplete(sid); return; }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n'); buffer = lines.pop();
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.progress !== undefined) {
                            reqState.progress = data.progress; reqState.stage = data.stage;
                            if (currentSessionId === sid) updateProgress(progressEl, data.progress, data.stage);
                        }
                        if (data.token) {
                            reqState.fullText += data.token;
                            if (currentSessionId === sid) resultEl.innerHTML = renderMarkdown(reqState.fullText);
                            autoScrollIfAtBottom();
                        }
                        if (data.done) { onComplete(sid); return; }
                    } catch (e) {}
                }
                read();
            }).catch(err => { if (err.name !== 'AbortError') { reqState.fullText = `<p style="color:#ef4444;">${err.message}</p>`; onComplete(sid); } });
        }
        read();
    }).catch(err => { if (err.name !== 'AbortError') { reqState.fullText = `<p style="color:#ef4444;">${err.message}</p>`; onComplete(sid); } });
}

function onComplete(sid) {
    const req = activeRequests.get(sid);
    if (!req) return;
    if (currentSessionId === sid) { markProgressDone(req.progressEl); req.resultEl.innerHTML = renderMarkdown(req.fullText); }
    const session = getCachedSession(sid);
    if (session && req.fullText) { session.messages.push({ role: 'assistant', content: req.fullText, persona: req.persona || 'literature' }); saveSession(session); }
    activeRequests.delete(sid); updateBtnState(); renderSidebar();
}

// ========== DOM ==========

function getAgentAvatar() {
    if (currentMode === 'debate') return currentPersona === 'mentor' ? '🎓' : '🔍';
    return '📚';
}

function getAgentType() {
    if (currentMode === 'debate') return currentPersona === 'mentor' ? 'mentor' : 'reviewer';
    return 'literature';
}

function appendMessageToDOM(role, content, agentType) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    const avatar = role === 'user' ? '👤' : getAgentAvatar();
    const dataAttr = role === 'assistant' ? ` data-agent="${agentType || getAgentType()}"` : '';
    div.innerHTML = `<div class="message-avatar"${dataAttr}>${avatar}</div><div class="message-content">${role === 'user' ? escapeHtml(content) : renderMarkdown(content)}</div>`;
    messagesDiv.appendChild(div); scrollToBottom();
    return div;
}

function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined') return marked.parse(text);
    return text.replace(/\n/g, '<br>');
}

function escapeHtml(text) { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }

function autoResize() { userInput.style.height = 'auto'; userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px'; }

function isNearBottom() { return chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 120; }
function scrollToBottom() { chatContainer.scrollTop = chatContainer.scrollHeight; }
function autoScrollIfAtBottom() { if (isNearBottom()) scrollToBottom(); }

// ========== 进度条 ==========

function createProgressBar() {
    const div = document.createElement('div');
    div.className = 'progress-container';
    div.innerHTML = `<div class="progress-header"><span class="progress-stage">准备中...</span><span class="progress-percent">0%</span></div><div class="progress-track"><div class="progress-fill" style="width:0%"></div></div>`;
    return div;
}

function updateProgress(el, percent, stage) {
    const fill = el.querySelector('.progress-fill');
    const p = el.querySelector('.progress-percent');
    const s = el.querySelector('.progress-stage');
    if (fill) fill.style.width = percent + '%';
    if (p) p.textContent = percent + '%';
    if (s) s.textContent = stage;
    autoScrollIfAtBottom();
}

function markProgressDone(el) {
    el.classList.add('done');
    updateProgress(el, 100, '✅ 完成');
    setTimeout(() => { el.style.transition = 'opacity 0.5s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 500); }, 1500);
}
