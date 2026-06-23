/**
 * 文献匹配智能体 - 前端交互逻辑
 * 支持多会话持久化存储与切换
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

// ========== 会话管理 ==========

function loadAllSessions() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
    } catch { return []; }
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
    if (idx >= 0) {
        sessions[idx] = session;
    } else {
        sessions.unshift(session);
    }
    saveAllSessions(sessions);
    renderSidebar();
}

function deleteSession(id) {
    const sessions = loadAllSessions().filter(s => s.id !== id);
    saveAllSessions(sessions);
    if (currentSessionId === id) {
        if (sessions.length > 0) {
            switchSession(sessions[0].id);
        } else {
            newChat();
        }
    } else {
        renderSidebar();
    }
}

function generateSessionTitle(messages) {
    // 取第一条用户消息作为标题
    const first = messages.find(m => m.role === 'user');
    if (!first) return '新对话';
    const text = first.content.trim();
    return text.length > 28 ? text.slice(0, 28) + '...' : text;
}

// ========== 当前会话状态 ==========
let currentSessionId = null;
let isSending = false;

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
    renderSidebar();

    // 恢复上次的会话，或显示欢迎页
    const sessions = loadAllSessions();
    if (sessions.length > 0) {
        switchSession(sessions[0].id);
    }
});

function loadStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            const lines = [`共 ${data.total} 篇论文`];
            for (const [conf, count] of Object.entries(data.by_conference)) {
                lines.push(`${conf}: ${count} 篇`);
            }
            statsInfo.innerHTML = lines.join('<br>');
        })
        .catch(() => {
            statsInfo.textContent = '统计信息加载失败';
        });
}

function setupEventListeners() {
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
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

// ========== 侧边栏渲染 ==========

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
            if (confirm('确定删除此对话？')) {
                deleteSession(session.id);
            }
        });

        item.addEventListener('click', () => switchSession(session.id));
        item.appendChild(title);
        item.appendChild(delBtn);
        chatHistory.appendChild(item);
    });
}

// ========== 会话切换 ==========

function switchSession(id) {
    const session = getSession(id);
    if (!session) return;

    currentSessionId = id;
    welcomeScreen.classList.add('hidden');
    messagesDiv.innerHTML = '';

    // 渲染该会话的所有消息
    (session.messages || []).forEach(msg => {
        appendMessageToDOM(msg.role, msg.content);
    });

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
    renderSidebar();
}

// ========== 发送消息 ==========

function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isSending) return;

    welcomeScreen.classList.add('hidden');

    // 如果没有当前会话，创建新会话
    if (!currentSessionId) {
        currentSessionId = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
        const newSession = {
            id: currentSessionId,
            title: generateSessionTitle([{ role: 'user', content: text }]),
            messages: [],
            createdAt: Date.now(),
        };
        saveSession(newSession);
    }

    // 保存用户消息
    const session = getSession(currentSessionId);
    session.messages.push({ role: 'user', content: text });
    // 如果是第一条消息，更新标题
    if (session.messages.filter(m => m.role === 'user').length === 1) {
        session.title = generateSessionTitle(session.messages);
    }
    saveSession(session);

    // DOM 操作
    appendMessageToDOM('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';
    isSending = true;
    sendBtn.disabled = true;
    userInput.disabled = true;

    // AI 消息占位（含进度条）
    const aiMsg = appendMessageToDOM('assistant', '');
    const contentEl = aiMsg.querySelector('.message-content');
    const progressEl = createProgressBar();
    contentEl.innerHTML = '';
    contentEl.appendChild(progressEl);
    const resultEl = document.createElement('div');
    contentEl.appendChild(resultEl);

    let fullText = '';
    let gotContent = false;

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
    }).then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    markProgressDone(progressEl);
                    finalizeMessage(resultEl, fullText);
                    finishSending(fullText);
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.progress !== undefined) {
                            updateProgress(progressEl, data.progress, data.stage);
                        }
                        if (data.token) {
                            if (!gotContent) {
                                resultEl.innerHTML = '';
                                gotContent = true;
                            }
                            fullText += data.token;
                            resultEl.innerHTML = renderMarkdown(fullText);
                            scrollToBottom();
                        }
                        if (data.done) {
                            markProgressDone(progressEl);
                            finalizeMessage(resultEl, fullText);
                            finishSending(fullText);
                        }
                    } catch (e) {}
                }
                read();
            }).catch(err => {
                resultEl.innerHTML = `<p style="color: #ef4444;">读取响应失败: ${err.message}</p>`;
                finishSending('');
            });
        }
        read();
    }).catch(err => {
        resultEl.innerHTML = `<p style="color: #ef4444;">请求失败: ${err.message}</p>`;
        finishSending('');
    });
}

function finishSending(aiText) {
    isSending = false;
    sendBtn.disabled = false;
    userInput.disabled = false;
    userInput.focus();

    // 保存 AI 回复到会话
    if (aiText && currentSessionId) {
        const session = getSession(currentSessionId);
        if (session) {
            session.messages.push({ role: 'assistant', content: aiText });
            saveSession(session);
        }
    }
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

function finalizeMessage(contentEl, text) {
    if (text) contentEl.innerHTML = renderMarkdown(text);
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

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
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
    scrollToBottom();
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
