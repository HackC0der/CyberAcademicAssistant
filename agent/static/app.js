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
let currentMode = 'chat';          // 'chat' | 'literature' | 'debate' | 'quiz'
let currentPersona = 'reviewer';  // debate: 'reviewer'|'mentor', quiz: 'inquiry'|'solution'
let sessionsCache = [];
const activeRequests = new Map();
let appConfig = {};

const PLATFORMS = {
    academic: { label: '🎓 学术智能体', icon: '🎓', agents: ['chat', 'literature', 'debate', 'quiz'] },
    polish: { label: '📝 论文润色', icon: '📝', agents: ['chat'] },
};
let currentPlatform = 'academic';

function getPlatformLabel(p) { return PLATFORMS[p]?.label || '🎓 学术智能体'; }

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', async () => {
    initTheme();
    initPlatform();
    setupEventListeners();
    initResize();
    await loadConfig();
    await loadAllSessions();
    renderSidebar();
    if (sessionsCache.length > 0) switchSession(sessionsCache[0].id);
});

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        // Backspace 空输入时删除最后一个引用标签
        if (e.key === 'Backspace' && userInput.value === '' && refTags.length > 0) {
            removeRefTag(refTags[refTags.length - 1].id);
        }
    });
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

    // 平台切换
    document.getElementById('platform-btn').addEventListener('click', e => {
        e.stopPropagation();
        document.getElementById('platform-dropdown').classList.toggle('open');
    });
    document.querySelectorAll('#platform-dropdown button').forEach(btn => {
        btn.addEventListener('click', () => switchPlatform(btn.dataset.platform));
    });
    document.addEventListener('click', () => { document.getElementById('platform-dropdown').classList.remove('open'); document.getElementById('export-dropdown').classList.remove('open'); });

    // 侧边栏收起/展开
    sidebarToggle.addEventListener('click', toggleSidebar);

    // 导出
    document.getElementById('export-btn').addEventListener('click', e => {
        e.stopPropagation();
        document.getElementById('export-dropdown').classList.toggle('open');
    });
    document.querySelectorAll('#export-dropdown button').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('export-dropdown').classList.remove('open');
            const action = btn.dataset.export;
            if (action === 'pdf-all') exportAll('pdf');
            else if (action === 'md-all') exportAll('md');
            else if (action === 'pdf-select') toggleSelectMode('pdf');
            else if (action === 'md-select') toggleSelectMode('md');
        });
    });

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
    document.getElementById('persona-switch').style.display = mode === 'debate' ? '' : 'none';
    document.getElementById('quiz-persona-switch').style.display = mode === 'quiz' ? '' : 'none';
    // 重置 persona
    if (mode === 'debate') currentPersona = 'reviewer';
    else if (mode === 'quiz') currentPersona = 'inquiry';
    document.querySelectorAll('.persona-btn').forEach(b => {
        const p = b.dataset.persona;
        b.classList.toggle('active', p === currentPersona);
    });
    updatePlaceholder();
}

function switchPersona(persona) {
    currentPersona = persona;
    document.querySelectorAll('.persona-btn').forEach(b => b.classList.toggle('active', b.dataset.persona === persona));
    updatePlaceholder();
}

function updatePlaceholder() {
    const hint = document.getElementById('input-hint');
    if (currentMode === 'chat') {
        userInput.placeholder = '输入任何问题...';
        hint.textContent = '按 Enter 发送，Shift+Enter 换行';
    } else if (currentMode === 'literature') {
        userInput.placeholder = '描述你的研究课题...';
        hint.textContent = '按 Enter 发送，Shift+Enter 换行 | TF-IDF 初筛 + LLM 语义排序';
    } else if (currentMode === 'quiz') {
        if (currentPersona === 'solution') {
            userInput.placeholder = '回答 AI 提出的问题...';
            hint.textContent = '按 Enter 发送 | ✅ 解惑模式：评判你的回答，指出错误不给答案';
        } else {
            userInput.placeholder = '上传论文 PDF，AI 将提问核心问题...';
            hint.textContent = '按 Enter 发送 | 🔍 求索模式：基于论文提出深度问题';
        }
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

// ========== 平台切换 ==========

const PLATFORM_KEY = 'literature_agent_platform';

function initPlatform() {
    const saved = localStorage.getItem(PLATFORM_KEY) || 'academic';
    setPlatform(saved);
}

function switchPlatform(platform) {
    if (platform === currentPlatform || !PLATFORMS[platform]) return;
    // 保存当前会话
    if (currentSessionId) {
        const session = getCachedSession(currentSessionId);
        if (session) saveSession(session);
    }
    setPlatform(platform);
    localStorage.setItem(PLATFORM_KEY, platform);
    // 重新加载会话
    loadAllSessions().then(() => {
        renderSidebar();
        if (sessionsCache.length > 0) switchSession(sessionsCache[0].id);
        else newChat();
    });
}

function setPlatform(platform) {
    currentPlatform = platform;
    const info = PLATFORMS[platform];
    document.getElementById('platform-label').textContent = info.label;
    document.getElementById('platform-dropdown').classList.remove('open');

    // 只显示当前平台允许的智能体标签
    document.querySelectorAll('.agent-tab').forEach(tab => {
        tab.style.display = info.agents.includes(tab.dataset.mode) ? '' : 'none';
    });
    // 如果当前模式不在允许列表中，切换到第一个
    if (!info.agents.includes(currentMode)) {
        switchMode(info.agents[0]);
    }
}

// ========== PDF 上传 ==========

async function handlePdfUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    // 确保有活跃会话
    if (!currentSessionId) {
        const newSess = await createSession('新对话');
        if (!newSess) return;
        currentSessionId = newSess.id;
        welcomeScreen.classList.add('hidden');
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch('/api/upload-pdf', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        const session = getCachedSession(currentSessionId);
        if (!session.pdfs) session.pdfs = [];

        const pdf = {
            id: 'pdf_' + Date.now(),
            filename: data.filename,
            text: data.text,
            pages: data.pages,
            text_length: data.text_length,
            cache_key: data.cache_key || '',
            referenced: true,  // 首次上传默认引用
        };
        session.pdfs.push(pdf);

        // 以 PDF 文件名更新标题，不覆盖已有人工设定的标题
        if (session.title === '新对话' || !session.title) {
            session.title = generateSessionTitle(session);
        }
        await saveSession(session);

        // 渲染 PDF 气泡
        renderPdfBubble(pdf);
        scrollToBottom();
    } catch (err) {
        alert(`PDF 解析失败: ${err.message}`);
    }
    e.target.value = '';
}

// 当前会话的引用标签：[{id, filename, text}]
let refTags = [];

function renderPdfBubble(pdf) {
    const div = document.createElement('div');
    div.className = 'message pdf-bubble';
    div.dataset.pdfId = pdf.id;
    const isRef = refTags.some(t => t.id === pdf.id);
    div.innerHTML = `
        <div class="message-avatar" data-agent="literature">📄</div>
        <div class="message-content">
            <div class="pdf-bubble-header">
                <span class="pdf-bubble-icon">📑</span>
                <div class="pdf-bubble-info">
                    <div class="pdf-bubble-name">${pdf.filename}</div>
                    <div class="pdf-bubble-meta">${pdf.pages} 页 · ${pdf.text_length} 字</div>
                </div>
                <button class="pdf-ref-btn ${isRef ? 'active' : ''}" data-pdf-id="${pdf.id}">
                    ${isRef ? '✓ 已引用' : '引用论文'}
                </button>
            </div>
        </div>
    `;

    div.querySelector('.pdf-ref-btn').addEventListener('click', () => {
        addRefTag(pdf);
    });

    messagesDiv.appendChild(div);
}

function addRefTag(pdf) {
    if (refTags.find(t => t.id === pdf.id)) return;
    refTags.push({ id: pdf.id, filename: pdf.filename, text: pdf.text });
    renderRefTags();
    syncPdfRefState(pdf.id, true);
}

function removeRefTag(pdfId) {
    refTags = refTags.filter(t => t.id !== pdfId);
    renderRefTags();
    syncPdfRefState(pdfId, false);
}

function syncPdfRefState(pdfId, referenced) {
    // 同步引用状态到 session.pdfs
    const session = getCachedSession(currentSessionId);
    if (!session || !session.pdfs) return;
    const pdf = session.pdfs.find(p => p.id === pdfId);
    if (pdf) {
        pdf.referenced = referenced;
        saveSession(session);
    }
    // 更新 PDF 气泡按钮状态
    const btn = messagesDiv.querySelector(`.pdf-ref-btn[data-pdf-id="${pdfId}"]`);
    if (btn) {
        btn.classList.toggle('active', referenced);
        btn.textContent = referenced ? '✓ 已引用' : '引用论文';
    }
}

function renderRefTags() {
    const container = document.getElementById('ref-tags');
    container.innerHTML = '';

    refTags.forEach(tag => {
        const el = document.createElement('span');
        el.className = 'ref-tag';
        el.innerHTML = `
            <span class="ref-tag-icon">📄</span>
            <span class="ref-tag-name">${tag.filename}</span>
            <button class="ref-tag-remove" data-id="${tag.id}">×</button>
        `;
        el.querySelector('.ref-tag-remove').addEventListener('click', () => removeRefTag(tag.id));
        container.appendChild(el);
    });
}

function getReferencedPdfs() {
    return refTags;
}

function renderSessionPdfs(session) {
    if (!session.pdfs || session.pdfs.length === 0) return;
    session.pdfs.forEach(pdf => renderPdfBubble(pdf));
}

// ========== 会话管理 ==========

async function loadAllSessions() {
    try {
        const r = await fetch('/api/sessions');
        const all = await r.json();
        sessionsCache = all.filter(s => (s.platform || 'academic') === currentPlatform);
    } catch { sessionsCache = []; }
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
            body: JSON.stringify({ title, platform: currentPlatform }),
        });
        const session = await r.json();
        sessionsCache.unshift(session);
        return session;
    } catch (e) { console.error('创建会话失败:', e); return null; }
}

const MODE_TITLE_PREFIX = {
    chat: '',           // 💬 省略，避免标题过长
    literature: '📚 ',
    debate: '⚔️ ',
    quiz: '📝 ',
};

function generateSessionTitle(session) {
    const mode = session.mode || currentMode;
    const prefix = MODE_TITLE_PREFIX[mode] || '';
    const maxLen = 28;

    // 1. 优先使用 PDF 文件名
    const pdfs = session.pdfs || [];
    const refPdfs = pdfs.filter(p => p.referenced);
    if (refPdfs.length > 0) {
        const name = refPdfs[0].filename.replace(/\.pdf$/i, '');
        const full = prefix + name;
        return full.length > maxLen ? full.slice(0, maxLen) + '...' : full;
    }

    // 2. 使用第一条用户消息
    const first = (session.messages || []).find(m => m.role === 'user');
    if (!first) return '新对话';
    const text = first.content.trim();
    const full = prefix + text;
    return full.length > maxLen ? full.slice(0, maxLen) + '...' : full;
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
        else if (lastAi && lastAi.persona === 'quiz') icon.textContent = '📝';
        else if (lastAi && lastAi.persona === 'chat') icon.textContent = '💬';
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

    // 从会话恢复引用标签
    refTags = (session.pdfs || []).filter(p => p.referenced).map(p => ({
        id: p.id, filename: p.filename, text: p.text,
    }));
    renderRefTags();

    welcomeScreen.classList.add('hidden');
    messagesDiv.innerHTML = '';

    // 渲染 PDF 气泡（在消息之前）
    renderSessionPdfs(session);

    // 渲染消息
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
    refTags = [];
    renderRefTags();
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
    let text = userInput.value.trim();
    if (currentSessionId && activeRequests.has(currentSessionId)) return;

    // 求索解惑模式必须引用论文
    if (currentMode === 'quiz' && getReferencedPdfs().length === 0) {
        alert('请先上传并引用一篇论文 PDF');
        return;
    }

    // 无输入但有引用 PDF 时，使用默认提示词
    if (!text) {
        if (getReferencedPdfs().length > 0) {
            text = currentMode === 'quiz'
                ? '请基于论文内容提出深度问题'
                : '请分析这篇论文';
        } else {
            return;
        }
    }

    welcomeScreen.classList.add('hidden');

    if (!currentSessionId) {
        const newSess = await createSession('新对话');
        if (!newSess) return;
        currentSessionId = newSess.id;
    }

    const session = getCachedSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    // 首次发言时记录模式，标题由后续 LLM 摘要生成
    if (session.messages.filter(m => m.role === 'user').length === 1 && (session.title === '新对话' || !session.title)) {
        session.mode = currentMode;
    }
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
    if (currentMode === 'chat') {
        apiEndpoint = '/api/chat-general';
        body = { message: text, history: history, ...settings };
    } else if (currentMode === 'debate') {
        apiEndpoint = '/api/debate';
        body = { message: text, history: history, mode: currentPersona, ...settings };
    } else if (currentMode === 'quiz') {
        apiEndpoint = '/api/quiz';
        body = { message: text, history: history, mode: currentPersona, ...settings };
    } else {
        apiEndpoint = '/api/chat';
        body = { message: text, history: history, ...settings };
    }

    // 附带引用的 PDF（从当前会话获取）
    const refPdfs = getReferencedPdfs();
    if (refPdfs.length > 0) {
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

async function onComplete(sid) {
    const req = activeRequests.get(sid);
    if (!req) return;
    if (currentSessionId === sid) { markProgressDone(req.progressEl); req.resultEl.innerHTML = renderMarkdown(req.fullText); }
    const session = getCachedSession(sid);
    if (session && req.fullText) {
        session.messages.push({ role: 'assistant', content: req.fullText, persona: req.persona });
        // 首次问答完成后，用 LLM 生成摘要标题
        const userCount = session.messages.filter(m => m.role === 'user').length;
        if (userCount === 1 && (session.title === '新对话' || !session.title)) {
            try {
                const r = await fetch(`/api/sessions/${session.id}/generate-title`, { method: 'POST' });
                const data = await r.json();
                session.title = data.title;
            } catch (e) {
                console.error('标题生成失败:', e);
            }
        }
        saveSession(session);
    }
    activeRequests.delete(sid); updateBtnState(); renderSidebar();
}

// ========== DOM ==========

function getAgentAvatar() {
    if (currentMode === 'chat') return '💬';
    if (currentMode === 'debate') return currentPersona === 'mentor' ? '🎓' : '🔍';
    if (currentMode === 'quiz') return currentPersona === 'solution' ? '✅' : '🔍';
    return '📚';
}

function getAgentType() {
    if (currentMode === 'chat') return 'chat';
    if (currentMode === 'debate') return currentPersona === 'mentor' ? 'mentor' : 'reviewer';
    if (currentMode === 'quiz') return 'quiz';
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

    // ── 提取并渲染 LaTeX 公式 ──
    const hasKatex = typeof katex !== 'undefined';
    const rendered = {};
    let idx = 0;

    // 行间公式 $$...$$
    text = text.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
        const key = `__MATH_D_${idx++}__`;
        try {
            rendered[key] = hasKatex
                ? katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
                : `<div class="math-fallback">$$${formula.trim()}$$</div>`;
        } catch { rendered[key] = `<div class="math-fallback">$$${formula.trim()}$$</div>`; }
        return key;
    });

    // 行内公式 $...$
    text = text.replace(/(?<!\$)\$(.+?)\$(?!\$)/g, (_, formula) => {
        const key = `__MATH_I_${idx++}__`;
        try {
            rendered[key] = hasKatex
                ? katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
                : `<span class="math-fallback">$${formula.trim()}$</span>`;
        } catch { rendered[key] = `<span class="math-fallback">$${formula.trim()}$</span>`; }
        return key;
    });

    // ── Markdown 渲染 ──
    let html;
    if (typeof marked !== 'undefined') html = marked.parse(text);
    else html = text.replace(/\n/g, '<br>');

    // ── 恢复公式 ──
    html = html.replace(/__MATH_[DI]_\d+__/g, match => rendered[match] || match);

    // ── 表格包裹 ──
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

// ========== 导出 PDF ==========

let selectMode = false;
let selectedIndices = new Set();
let exportFormat = 'pdf';

function toggleSelectMode(format) {
    if (format) exportFormat = format;
    selectMode = !selectMode;
    const msgContainer = document.getElementById('messages');
    const selectionBar = document.getElementById('selection-bar');

    if (selectMode) {
        selectedIndices.clear();
        msgContainer.classList.add('select-mode');
        document.querySelectorAll('.message:not(.pdf-bubble)').forEach((el, i) => {
            el.classList.add('selectable');
            el.dataset.msgIndex = i;
            el.addEventListener('click', onMessageClick);
        });
        selectionBar.classList.remove('hidden');
        updateSelectionCount();
        document.getElementById('select-all-btn').onclick = selectAllMessages;
        document.getElementById('cancel-select-btn').onclick = toggleSelectMode;
        document.getElementById('export-selected-btn').onclick = exportSelected;
    } else {
        msgContainer.classList.remove('select-mode');
        document.querySelectorAll('.message.selectable').forEach(el => {
            el.classList.remove('selectable', 'selected');
            el.removeEventListener('click', onMessageClick);
        });
        selectionBar.classList.add('hidden');
    }
}

function onMessageClick(e) {
    const el = e.currentTarget;
    const idx = parseInt(el.dataset.msgIndex);
    if (selectedIndices.has(idx)) {
        selectedIndices.delete(idx);
        el.classList.remove('selected');
    } else {
        selectedIndices.add(idx);
        el.classList.add('selected');
    }
    updateSelectionCount();
}

function selectAllMessages() {
    document.querySelectorAll('.message.selectable').forEach(el => {
        const idx = parseInt(el.dataset.msgIndex);
        selectedIndices.add(idx);
        el.classList.add('selected');
    });
    updateSelectionCount();
}

function updateSelectionCount() {
    document.getElementById('selection-count').textContent = `已选 ${selectedIndices.size} 条`;
}

async function downloadExport(indices, format) {
    if (!currentSessionId) return;
    const endpoint = format === 'md' ? 'export-md' : 'export-pdf';
    const ext = format === 'md' ? '.md' : '.pdf';
    try {
        const resp = await fetch(`/api/sessions/${currentSessionId}/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(indices !== null ? { indices } : {}),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const session = getCachedSession(currentSessionId);
        a.download = (session?.title || '对话导出') + ext;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        alert(`导出失败: ${e.message}`);
    }
}

function exportAll(format) {
    if (!currentSessionId) return;
    if (selectMode) toggleSelectMode();
    downloadExport(null, format || 'pdf');
}

function exportSelected() {
    if (selectedIndices.size === 0) {
        alert('请先选择要导出的消息');
        return;
    }
    const indices = [...selectedIndices].sort((a, b) => a - b);
    downloadExport(indices, exportFormat);
    toggleSelectMode();
}
