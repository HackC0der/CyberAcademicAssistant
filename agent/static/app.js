/**
 * 文献匹配智能体 - 前端交互逻辑
 * 支持多会话持久化存储与切换，进行中的请求跨会话保持
 */

const chatContainer = document.getElementById('chat-container');
const messagesDiv = document.getElementById('messages');
const welcomeScreen = document.getElementById('welcome-screen');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const statsInfo = document.getElementById('stats-info');
const chatHistory = document.getElementById('chat-history');

const STORAGE_KEY = 'literature_agent_sessions';

// ========== 全局状态 ==========
let currentSessionId = null;

// 进行中的请求跟踪：sessionId → { fullText, progress, stage, reader, abortController }
const activeRequests = new Map();

// ========== 会话持久化 ==========

function loadAllSessions() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
    catch { return []; }
}

function saveAllSessions(sessions) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

function getSession(id) {
    return loadAllSessions().find(s => s.id === id) || null;
}

function saveSession(session) {
    const sessions = loadAllSessions();
    const idx = sessions.findIndex(s => s.id === session.id);
    if (idx >= 0) sessions[idx] = session;
    else sessions.unshift(session);
    saveAllSessions(sessions);
    renderSidebar();
}

function deleteSession(id) {
    // 如果有进行中的请求，取消它
    const req = activeRequests.get(id);
    if (req) {
        req.abortController.abort();
        activeRequests.delete(id);
    }

    const sessions = loadAllSessions().filter(s => s.id !== id);
    saveAllSessions(sessions);
    if (currentSessionId === id) {
        if (sessions.length > 0) switchSession(sessions[0].id);
        else newChat();
    } else {
        renderSidebar();
    }
}

function generateSessionTitle(messages) {
    const first = messages.find(m => m.role === 'user');
    if (!first) return '新对话';
    const text = first.content.trim();
    return text.length > 28 ? text.slice(0, 28) + '...' : text;
}

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
    initResize();
    renderSidebar();
    const sessions = loadAllSessions();
    if (sessions.length > 0) switchSession(sessions[0].id);
});

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
    document.querySelectorAll('.example-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            userInput.value = btn.dataset.query;
            autoResize();
            sendMessage();
        });
    });
}

function autoResize() {
    userInput.style.height = 'auto';
    userInput.style.height = Math.min(userInput.scrollHeight, 200) + 'px';
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
    const sessions = loadAllSessions();
    chatHistory.innerHTML = '';
    if (sessions.length === 0) {
        chatHistory.innerHTML = '<div class="sidebar-empty">暂无对话</div>';
        return;
    }
    sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = 'session-item' + (session.id === currentSessionId ? ' active' : '');
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
    const session = getSession(id);
    if (!session) return;

    welcomeScreen.classList.add('hidden');
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
    welcomeScreen.classList.remove('hidden');
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

function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    if (currentSessionId && activeRequests.has(currentSessionId)) return;

    welcomeScreen.classList.add('hidden');

    // 创建新会话
    if (!currentSessionId) {
        currentSessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        saveSession({
            id: currentSessionId,
            title: generateSessionTitle([{ role: 'user', content: text }]),
            messages: [],
            createdAt: Date.now(),
        });
    }

    // 保存用户消息
    const session = getSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    if (session.messages.filter(m => m.role === 'user').length === 1)
        session.title = generateSessionTitle(session.messages);
    saveSession(session);

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

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: history }),
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
    const session = getSession(sid);
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
