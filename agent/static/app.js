/**
 * 文献匹配智能体 - 前端交互逻辑
 * 支持多会话持久化存储（服务端）与切换，进行中的请求跨会话保持
 */

const chatContainer = document.getElementById('chat-container');
const messagesDiv = document.getElementById('messages');
const welcomeLit = document.getElementById('welcome-literature');
const welcomeDebate = document.getElementById('welcome-debate');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const statsInfo = document.getElementById('stats-info');
const chatHistory = document.getElementById('chat-history');

// ========== 全局状态 ==========
let currentSessionId = null;
let currentMode = 'literature';  // 'literature' 或 'debate'
let currentSubMode = 'reviewer'; // 'reviewer' 或 'mentor'（仅 debate 模式）
let sessionsCache = [];

// 进行中的请求跟踪：sessionId → { fullText, progress, stage, progressEl, resultEl, abortController }
const activeRequests = new Map();

// ========== 会话持久化（服务端 API） ==========

async function loadAllSessions() {
    try {
        const resp = await fetch('/api/sessions');
        sessionsCache = await resp.json();
    } catch { sessionsCache = []; }
    return sessionsCache;
}

function getCachedSession(id) {
    return sessionsCache.find(s => s.id === id) || null;
}

async function saveSession(session) {
    try {
        const resp = await fetch(`/api/sessions/${session.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(session),
        });
        const updated = await resp.json();
        // 更新缓存
        const idx = sessionsCache.findIndex(s => s.id === session.id);
        if (idx >= 0) sessionsCache[idx] = updated;
        else sessionsCache.unshift(updated);
    } catch (e) {
        console.error('保存会话失败:', e);
    }
    renderSidebar();
}

async function deleteSession(id) {
    const req = activeRequests.get(id);
    if (req) {
        req.abortController.abort();
        activeRequests.delete(id);
    }

    try { await fetch(`/api/sessions/${id}`, { method: 'DELETE' }); } catch {}
    sessionsCache = sessionsCache.filter(s => s.id !== id);

    if (currentSessionId === id) {
        if (sessionsCache.length > 0) switchSession(sessionsCache[0].id);
        else newChat();
    } else {
        renderSidebar();
    }
}

async function createSession(title) {
    try {
        const resp = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title }),
        });
        const session = await resp.json();
        sessionsCache.unshift(session);
        return session;
    } catch (e) {
        console.error('创建会话失败:', e);
        return null;
    }
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

// ========== 主题切换 ==========

function initTheme() {
    const THEME_KEY = 'literature_agent_theme';
    const toggle = document.getElementById('theme-toggle');

    // 恢复保存的主题，默认暗色
    const saved = localStorage.getItem(THEME_KEY) || 'dark';
    applyTheme(saved);

    toggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        localStorage.setItem(THEME_KEY, next);
    });
}

function applyTheme(theme) {
    const toggle = document.getElementById('theme-toggle');
    if (theme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        toggle.textContent = '☀️';
        toggle.title = '切换为暗色主题';
    } else {
        document.documentElement.removeAttribute('data-theme');
        toggle.textContent = '🌙';
        toggle.title = '切换为亮色主题';
    }
}

function loadStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            const lines = [`共 ${data.total} 篇论文`];
            for (const [conf, count] of Object.entries(data.by_conference))
                lines.push(`${conf}: ${count} 篇`);
            statsInfo.innerHTML = lines.join('<br>');
        })
        .catch(() => { statsInfo.textContent = '统计信息加载失败'; });
}

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    userInput.addEventListener('input', autoResize);
    newChatBtn.addEventListener('click', newChat);

    // 示例查询
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // 如果示例指定了模式，先切换
            if (btn.dataset.mode) switchMode(btn.dataset.mode);
            userInput.value = btn.dataset.query;
            autoResize();
            sendMessage();
        });
    });

    // 模式切换
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => switchMode(btn.dataset.mode));
    });

    // 辩论子模式切换
    document.querySelectorAll('.submode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentSubMode = btn.dataset.submode;
            document.querySelectorAll('.submode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            updatePlaceholder();
        });
    });
}

function switchMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.mode-btn[data-mode="${mode}"]`).classList.add('active');

    document.getElementById('welcome-literature').style.display = mode === 'literature' ? '' : 'none';
    document.getElementById('welcome-debate').style.display = mode === 'debate' ? '' : 'none';
    document.getElementById('debate-submode').style.display = mode === 'debate' ? '' : 'none';
    document.getElementById('stats-info').style.display = mode === 'literature' ? '' : 'none';

    // 切换会话列表（按模式过滤）
    renderSidebar();
    newChat();
    updatePlaceholder();
}

function updatePlaceholder() {
    const hint = document.getElementById('input-hint');
    if (currentMode === 'literature') {
        userInput.placeholder = '描述你的研究课题...';
        hint.textContent = '按 Enter 发送，Shift+Enter 换行 | TF-IDF 初筛 + LLM 语义排序';
    } else if (currentSubMode === 'reviewer') {
        userInput.placeholder = '描述你的研究想法，审稿人将进行严厉质疑...';
        hint.textContent = '按 Enter 发送 | 🔍 审稿人模式：批判性审视你的假设与贡献';
    } else {
        userInput.placeholder = '描述你的研究想法，导师将帮你打磨创新点...';
        hint.textContent = '按 Enter 发送 | 🎓 导师模式：引导你凝练科学问题与设计';
    }
}

function autoResize() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
}

function hideAllWelcome() {
    welcomeLit.classList.add('hidden');
    welcomeDebate.classList.add('hidden');
}

function showCurrentWelcome() {
    hideAllWelcome();
    if (currentMode === 'debate') welcomeDebate.classList.remove('hidden');
    else welcomeLit.classList.remove('hidden');
}

// ========== 侧边栏拖拽调整宽度 ==========

function initResize() {
    const handle = document.getElementById('resize-handle');
    const sidebar = document.querySelector('.sidebar');
    const root = document.documentElement;
    const SIDEBAR_KEY = 'literature_agent_sidebar_width';

    // 恢复上次保存的宽度
    const saved = localStorage.getItem(SIDEBAR_KEY);
    if (saved) {
        const w = parseInt(saved, 10);
        if (w >= 180 && w <= 500) {
            root.style.setProperty('--sidebar-width', w + 'px');
        }
    }

    let startX, startWidth;

    function onMouseDown(e) {
        e.preventDefault();
        startX = e.clientX;
        startWidth = sidebar.getBoundingClientRect().width;
        handle.classList.add('active');
        document.body.classList.add('resizing');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    function onMouseMove(e) {
        const dx = e.clientX - startX;
        let newWidth = startWidth + dx;
        newWidth = Math.max(180, Math.min(500, newWidth));
        root.style.setProperty('--sidebar-width', newWidth + 'px');
    }

    function onMouseUp() {
        handle.classList.remove('active');
        document.body.classList.remove('resizing');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        // 保存宽度
        const w = sidebar.getBoundingClientRect().width;
        localStorage.setItem(SIDEBAR_KEY, Math.round(w));
    }

    handle.addEventListener('mousedown', onMouseDown);
}

// ========== 侧边栏 ==========

function renderSidebar() {
    chatHistory.innerHTML = '';
    // 按当前模式过滤会话
    const filtered = sessionsCache.filter(s => (s.mode || 'literature') === currentMode);
    if (filtered.length === 0) {
        chatHistory.innerHTML = '<div class="sidebar-empty">暂无对话</div>';
        return;
    }
    filtered.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item' + (session.id === currentSessionId ? ' active' : '');
        // 模式图标
        const icon = document.createElement('span');
        icon.className = 'session-icon';
        if (session.mode === 'debate') {
            icon.textContent = session.subMode === 'mentor' ? '🎓' : '⚔️';
        } else {
            icon.textContent = '📚';
        }
        item.appendChild(icon);
        // 进行中有请求时显示小圆点
        if (activeRequests.has(session.id)) {
            const dot = document.createElement('span');
            dot.className = 'session-busy';
            dot.textContent = '●';
            item.appendChild(dot);
        }
        const title = document.createElement('span');
        title.className = 'session-title';
        title.textContent = session.title || '新对话';
        title.title = session.title || '新对话';
        const delBtn = document.createElement('button');
        delBtn.className = 'session-delete';
        delBtn.innerHTML = '×';
        delBtn.title = '删除对话';
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm('确定删除此对话？')) deleteSession(session.id);
        });
        item.addEventListener('click', () => switchSession(session.id));
        item.appendChild(title);
        item.appendChild(delBtn);
        chatHistory.appendChild(item);
    });
}

// ========== 会话切换 ==========

function switchSession(id) {
    if (currentSessionId === id) return;
    currentSessionId = id;
    const session = getCachedSession(id);
    if (!session) return;

    hideAllWelcome();
    messagesDiv.innerHTML = '';

    // 渲染已保存的消息
    (session.messages || []).forEach(msg => {
        appendMessageToDOM(msg.role, msg.content);
    });

    // 如果该会话有进行中的请求，挂载活跃的进度条和结果区
    const req = activeRequests.get(id);
    if (req) {
        const aiMsg = appendMessageToDOM('assistant', '');
        const contentEl = aiMsg.querySelector('.message-content');
        contentEl.innerHTML = '';
        contentEl.appendChild(req.progressEl);
        contentEl.appendChild(req.resultEl);
        updateBtnState();
    } else {
        updateBtnState();
    }

    renderSidebar();
    scrollToBottom();
    userInput.focus();
}

// ========== 新建会话 ==========

function newChat() {
    currentSessionId = null;
    messagesDiv.innerHTML = '';
    showCurrentWelcome();
    userInput.value = '';
    userInput.style.height = 'auto';
    updateBtnState();
    renderSidebar();
}

// ========== 按钮状态 ==========

function updateBtnState() {
    // 当前会话有进行中的请求 → 禁用
    const sending = currentSessionId && activeRequests.has(currentSessionId);
    sendBtn.disabled = !!sending;
    userInput.disabled = !!sending;
}

// ========== 发送消息 ==========

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    if (currentSessionId && activeRequests.has(currentSessionId)) return;

    hideAllWelcome();

    // 创建新会话
    if (!currentSessionId) {
        const title = generateSessionTitle([{ role: 'user', content: text }]);
        const newSess = await createSession(title);
        if (!newSess) return;
        currentSessionId = newSess.id;
        // 记录会话模式
        newSess.mode = currentMode;
        newSess.subMode = currentSubMode;
        await saveSession(newSess);
    }

    // 保存用户消息
    const session = getCachedSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    if (session.messages.filter(m => m.role === 'user').length === 1)
        session.title = generateSessionTitle(session.messages);
    await saveSession(session);

    // DOM
    appendMessageToDOM('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';

    // 进度条 + 结果区
    const progressEl = createProgressBar();
    const resultEl = document.createElement('div');
    const aiMsg = appendMessageToDOM('assistant', '');
    const contentEl = aiMsg.querySelector('.message-content');
    contentEl.innerHTML = '';
    contentEl.appendChild(progressEl);
    contentEl.appendChild(resultEl);

    // 跟踪请求
    const abortController = new AbortController();
    const reqState = { fullText: '', progress: 0, stage: '', progressEl, resultEl, abortController };
    const sid = currentSessionId; // 捕获当前会话 ID
    activeRequests.set(sid, reqState);
    updateBtnState();
    renderSidebar();

    // 构建历史对话（最近 10 条，包含刚保存的用户消息）
    const history = session.messages.slice(-10);

    // 根据模式选择 API
    const apiEndpoint = currentMode === 'debate' ? '/api/debate' : '/api/chat';
    const body = currentMode === 'debate'
        ? { message: text, history: history, mode: currentSubMode }
        : { message: text, history: history };

    fetch(apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortController.signal,
    }).then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) { onComplete(sid); return; }
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.progress !== undefined) {
                            reqState.progress = data.progress;
                            reqState.stage = data.stage;
                            // 只在当前会话可见时更新 DOM
                            if (currentSessionId === sid)
                                updateProgress(progressEl, data.progress, data.stage);
                        }
                        if (data.token) {
                            reqState.fullText += data.token;
                            if (currentSessionId === sid)
                                resultEl.innerHTML = renderMarkdown(reqState.fullText);
                            autoScrollIfAtBottom();
                        }
                        if (data.done) { onComplete(sid); return; }
                    } catch (e) {}
                }
                read();
            }).catch(err => {
                if (err.name === 'AbortError') return;
                reqState.fullText = `<p style="color: #ef4444;">读取响应失败: ${err.message}</p>`;
                if (currentSessionId === sid) resultEl.innerHTML = reqState.fullText;
                onComplete(sid);
            });
        }
        read();
    }).catch(err => {
        if (err.name === 'AbortError') return;
        reqState.fullText = `<p style="color: #ef4444;">请求失败: ${err.message}</p>`;
        if (currentSessionId === sid) resultEl.innerHTML = reqState.fullText;
        onComplete(sid);
    });
}

function onComplete(sid) {
    const req = activeRequests.get(sid);
    if (!req) return;

    // 进度条完成动画（只在可见时）
    if (currentSessionId === sid) {
        markProgressDone(req.progressEl);
        req.resultEl.innerHTML = renderMarkdown(req.fullText);
    }

    // 保存 AI 回复
    const session = getCachedSession(sid);
    if (session && req.fullText) {
        session.messages.push({ role: 'assistant', content: req.fullText });
        saveSession(session);
    }

    // 清理
    activeRequests.delete(sid);
    updateBtnState();
    renderSidebar();
}

// ========== DOM 操作 ==========

function appendMessageToDOM(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerHTML = `
        <div class="message-avatar">${role === 'user' ? '👤' : '📚'}</div>
        <div class="message-content">${role === 'user' ? escapeHtml(content) : renderMarkdown(content)}</div>
    `;
    messagesDiv.appendChild(div);
    scrollToBottom();
    return div;
}

function renderMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined') return marked.parse(text);
    return text.replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function isNearBottom() {
    // 距离底部 120px 以内视为"在底部"
    return chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 120;
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 仅在用户已在底部时自动滚动（流式输出用）
function autoScrollIfAtBottom() {
    if (isNearBottom()) scrollToBottom();
}

// ========== 进度条 ==========

function createProgressBar() {
    const div = document.createElement('div');
    div.className = 'progress-container';
    div.innerHTML = `
        <div class="progress-header">
            <span class="progress-stage">准备中...</span>
            <span class="progress-percent">0%</span>
        </div>
        <div class="progress-track">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
    `;
    return div;
}

function updateProgress(el, percent, stage) {
    const fill = el.querySelector('.progress-fill');
    const percentEl = el.querySelector('.progress-percent');
    const stageEl = el.querySelector('.progress-stage');
    if (fill) fill.style.width = percent + '%';
    if (percentEl) percentEl.textContent = percent + '%';
    if (stageEl) stageEl.textContent = stage;
    autoScrollIfAtBottom();
}

function markProgressDone(el) {
    el.classList.add('done');
    updateProgress(el, 100, '✅ 完成');
    setTimeout(() => {
        el.style.transition = 'opacity 0.5s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 500);
    }, 1500);
}
