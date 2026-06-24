/**
 * 学术智能体平台
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
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');

// ========== 全局状态 ==========
let currentSessionId = null;
let currentMode = 'literature';
let currentPersona = 'reviewer';
let sessionsCache = [];
const activeRequests = new Map();
let appConfig = {};
// PDF 管理：上传的 PDF 列表，可点击引用
let uploadedPdfs = [];  // [{id, filename, text, images, active}]

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    setupEventListeners();
    initResize();
    await loadConfig();
    await loadAllSessions();
    renderSidebar();
    if (sessionsCache.length > 0) switchSession(sessionsCache[0].id);
});

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
    userInput.addEventListener('input', autoResize);
    newChatBtn.addEventListener('click', newChat);

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

    // 人格切换
    document.querySelectorAll('.persona-btn').forEach(btn => {
        btn.addEventListener('click', () => switchPersona(btn.dataset.persona));
    });

    // PDF 上传
    document.getElementById('pdf-upload').addEventListener('change', handlePdfUpload);
    document.getElementById('pdf-btn').addEventListener('click', () => document.getElementById('pdf-upload').click());

    // 侧边栏标签页
    document.querySelectorAll('.sidebar-tab').forEach(tab => {
        tab.addEventListener('click', () => switchSidebarTab(tab.dataset.tab));
    });

    // 侧边栏收起/展开
    sidebarToggle.addEventListener('click', toggleSidebar);

    // 设置保存
    document.getElementById('cfg-save-btn').addEventListener('click', saveConfig);
}

// ========== 侧边栏标签页 ==========

function switchSidebarTab(tab) {
    document.querySelectorAll('.sidebar-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.getElementById('panel-sessions').style.display = tab === 'sessions' ? '' : 'none';
    document.getElementById('panel-settings').style.display = tab === 'settings' ? '' : 'none';
}

// ========== 侧边栏收起/展开 ==========

function toggleSidebar() {
    sidebar.classList.toggle('collapsed');
    sidebarToggle.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
    sidebarToggle.title = sidebar.classList.contains('collapsed') ? '展开侧边栏' : '收起侧边栏';
}

// ========== 配置管理 ==========

async function loadConfig() {
    try {
        const resp = await fetch('/api/config');
        appConfig = await resp.json();
    } catch { appConfig = {}; }

    // 填入设置表单
    document.getElementById('cfg-api-base').value = appConfig.api_base || '';
    document.getElementById('cfg-api-key').value = appConfig.api_key || '';
    document.getElementById('cfg-model').value = appConfig.model || '';
    const temp = appConfig.temperature ?? 0.7;
    const maxTokens = appConfig.max_tokens ?? 0;
    document.getElementById('cfg-temperature').value = temp;
    document.getElementById('temp-value').textContent = temp;
    document.getElementById('cfg-max-tokens').value = maxTokens;
    document.getElementById('max-tokens-value').textContent = maxTokens || '不限制';

    // 滑块事件
    document.getElementById('cfg-temperature').addEventListener('input', e => {
        document.getElementById('temp-value').textContent = parseFloat(e.target.value).toFixed(1);
    });
    document.getElementById('cfg-max-tokens').addEventListener('input', e => {
        document.getElementById('max-tokens-value').textContent = parseInt(e.target.value) || '不限制';
    });
}

async function saveConfig() {
    const cfg = {
        api_base: document.getElementById('cfg-api-base').value.trim(),
        api_key: document.getElementById('cfg-api-key').value.trim(),
        model: document.getElementById('cfg-model').value.trim(),
        temperature: parseFloat(document.getElementById('cfg-temperature').value),
        max_tokens: parseInt(document.getElementById('cfg-max-tokens').value) || 0,
    };

    try {
        const resp = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg),
        });
        const data = await resp.json();
        if (data.ok) {
            appConfig = cfg;
            document.getElementById('cfg-save-status').textContent = '✅ 配置已保存';
            setTimeout(() => { document.getElementById('cfg-save-status').textContent = ''; }, 2000);
        }
    } catch (e) {
        document.getElementById('cfg-save-status').textContent = `❌ 保存失败: ${e.message}`;
    }
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
        userInput.placeholder = '描述你的研究课题...';
        hint.textContent = '按 Enter 发送，Shift+Enter 换行 | TF-IDF 初筛 + LLM 语义排序';
    } else if (currentPersona === 'reviewer') {
        userInput.placeholder = '描述你的研究想法，审稿人将进行严厉质疑...';
        hint.textContent = '按 Enter 发送 | 🔍 审稿人模式：可随时切换为导师模式';
    } else {
        userInput.placeholder = '描述你的研究想法，导师将帮你打磨创新点...';
        hint.textContent = '按 Enter 发送 | 🎓 导师模式：可随时切换为审稿人模式';
    }
}

// ========== 主题 ==========

function initTheme() {
    const THEME_KEY = 'literature_agent_theme';
    const saved = localStorage.getItem(THEME_KEY) || 'dark';
    applyTheme(saved);

    // 设置页的主题按钮
    document.querySelectorAll('.theme-opt').forEach(btn => {
        btn.addEventListener('click', () => {
            applyTheme(btn.dataset.theme);
            localStorage.setItem(THEME_KEY, btn.dataset.theme);
        });
    });
}

function applyTheme(theme) {
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    // 更新设置页按钮状态
    document.querySelectorAll('.theme-opt').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === theme);
    });
}

// ========== PDF 上传 ==========

async function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload-pdf', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        const pdf = {
            id: 'pdf_' + Date.now(),
            filename: data.filename,
            text: data.text,
            pages: data.pages,
            text_length: data.text_length,
            active: true,  // 默认引用
        };
        uploadedPdfs.push(pdf);
        renderPdfBar();
    } catch (err) {
        alert(`PDF 解析失败: ${err.message}`);
    }
    e.target.value = '';
}

function renderPdfBar() {
    const bar = document.getElementById('pdf-bar');
    if (uploadedPdfs.length === 0) {
        bar.style.display = 'none';
        bar.innerHTML = '';
        return;
    }

    bar.style.display = '';
    bar.innerHTML = '';

    uploadedPdfs.forEach(pdf => {
        const chip = document.createElement('div');
        chip.className = 'pdf-chip' + (pdf.active ? ' active' : '');
        chip.title = pdf.active ? '点击取消引用' : '点击引用此 PDF';
        chip.innerHTML = `
            <span class="pdf-chip-icon">📄</span>
            <span class="pdf-chip-name">${pdf.filename}</span>
            <button class="pdf-chip-remove" title="移除">×</button>
        `;

        // 点击芯片切换引用状态
        chip.addEventListener('click', (e) => {
            if (e.target.classList.contains('pdf-chip-remove')) return;
            pdf.active = !pdf.active;
            renderPdfBar();
        });

        // 移除按钮
        chip.querySelector('.pdf-chip-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            uploadedPdfs = uploadedPdfs.filter(p => p.id !== pdf.id);
            renderPdfBar();
        });

        bar.appendChild(chip);
    });
}

function getReferencedPdfs() {
    return uploadedPdfs.filter(p => p.active);
}

// ========== 会话管理 ==========

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

// ========== 侧边栏渲染 ==========

function renderSidebar() {
    chatHistory.innerHTML = '';
    if (sessionsCache.length === 0) { chatHistory.innerHTML = '<div class="sidebar-empty">暂无对话</div>'; return; }
    sessionsCache.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item' + (session.id === currentSessionId ? ' active' : '');
        const icon = document.createElement('span');
        icon.className = 'session-icon';
        const lastAi = [...(session.messages || [])].reverse().find(m => m.role === 'assistant');
        if (lastAi && lastAi.persona === 'reviewer') icon.textContent = '🔍';
        else if (lastAi && lastAi.persona === 'mentor') icon.textContent = '🎓';
        else icon.textContent = '📚';
        item.appendChild(icon);
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
    // 更新 stats
    loadStats();
}

function loadStats() {
    fetch('/api/stats').then(r => r.json()).then(data => {
        const lines = [`共 ${data.total} 篇论文`];
        for (const [c, n] of Object.entries(data.by_conference)) lines.push(`${c}: ${n} 篇`);
        statsInfo.innerHTML = lines.join('<br>');
    }).catch(() => { statsInfo.textContent = ''; });
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

function newChat() {
    currentSessionId = null;
    messagesDiv.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    userInput.value = ''; userInput.style.height = 'auto';
    updateBtnState(); renderSidebar();
}

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

    if (!currentSessionId) {
        const title = generateSessionTitle([{ role: 'user', content: text }]);
        const newSess = await createSession(title);
        if (!newSess) return;
        currentSessionId = newSess.id;
    }

    const session = getCachedSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    if (session.messages.filter(m => m.role === 'user').length === 1) session.title = generateSessionTitle(session.messages);
    await saveSession(session);

    const requestPersona = currentPersona;
    appendMessageToDOM('user', text);
    userInput.value = ''; userInput.style.height = 'auto';

    const agentType = currentMode === 'debate' ? requestPersona : 'literature';
    const progressEl = createProgressBar();
    const resultEl = document.createElement('div');
    const aiMsg = appendMessageToDOM('assistant', '', agentType);
    const contentEl = aiMsg.querySelector('.message-content');
    contentEl.innerHTML = ''; contentEl.appendChild(progressEl); contentEl.appendChild(resultEl);

    const abortController = new AbortController();
    const reqState = { fullText: '', progressEl, resultEl, abortController, persona: agentType };
    const sid = currentSessionId;
    activeRequests.set(sid, reqState);
    updateBtnState(); renderSidebar();

    const history = session.messages.slice(-10);
    let apiEndpoint, body;
    const settings = {
        temperature: appConfig.temperature ?? 0.7,
        max_tokens: (appConfig.max_tokens || undefined),
    };
    if (currentMode === 'debate') {
        apiEndpoint = '/api/debate';
        body = { message: text, history: history, mode: currentPersona, ...settings };
    } else {
        apiEndpoint = '/api/chat';
        body = { message: text, history: history, ...settings };
    }

    // 附带引用的 PDF
    const refPdfs = getReferencedPdfs();
    if (refPdfs.length > 0) {
        // 合并多个 PDF 的内容
        const combined = refPdfs.map(p => `=== ${p.filename} ===\n${p.text}`).join('\n\n');
        body.pdf_context = combined;
        body.pdf_filename = refPdfs.map(p => p.filename).join(', ');
        // 在用户消息旁显示引用标记
        const userMsgEl = messagesDiv.querySelector('.message.user:last-of-type .message-content');
        if (userMsgEl) {
            refPdfs.forEach(pdf => {
                const tag = document.createElement('div');
                tag.className = 'pdf-tag';
                tag.textContent = `📄 ${pdf.filename}`;
                userMsgEl.appendChild(tag);
            });
        }
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
    if (session && req.fullText) { session.messages.push({ role: 'assistant', content: req.fullText, persona: req.persona }); saveSession(session); }
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
    let html;
    if (typeof marked !== 'undefined') html = marked.parse(text);
    else html = text.replace(/\n/g, '<br>');
    html = html.replace(/<table/g, '<div class="table-wrapper"><table').replace(/<\/table>/g, '</table></div>');
    return html;
}

function escapeHtml(text) { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }
function autoResize() { userInput.style.height = 'auto'; userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px'; }
function isNearBottom() { return chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 120; }
function scrollToBottom() { chatContainer.scrollTop = chatContainer.scrollHeight; }
function autoScrollIfAtBottom() { if (isNearBottom()) scrollToBottom(); }

// ========== 侧边栏拖拽 ==========

function initResize() {
    const handle = document.getElementById('resize-handle');
    const root = document.documentElement;
    const SIDEBAR_KEY = 'literature_agent_sidebar_width';

    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved) { const w = parseInt(saved, 10); if (w >= 180 && w <= 500) root.style.setProperty('--sidebar-width', w + 'px'); }

    let startX, startWidth;

    handle.addEventListener('mousedown', e => {
        e.preventDefault();
        startX = e.clientX;
        startWidth = sidebar.getBoundingClientRect().width;
        handle.classList.add('active');
        document.body.classList.add('resizing');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    function onMouseMove(e) {
        let newWidth = startWidth + (e.clientX - startX);
        newWidth = Math.max(180, Math.min(500, newWidth));
        root.style.setProperty('--sidebar-width', newWidth + 'px');
    }

    function onMouseUp() {
        handle.classList.remove('active');
        document.body.classList.remove('resizing');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        localStorage.setItem(SIDEBAR_KEY, Math.round(sidebar.getBoundingClientRect().width));
    }
}

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
