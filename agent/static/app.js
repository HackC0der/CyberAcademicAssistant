/**
 * 文献匹配智能体 - 前端交互逻辑
 */

const chatContainer = document.getElementById('chat-container');
const messagesDiv = document.getElementById('messages');
const welcomeScreen = document.getElementById('welcome-screen');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const statsInfo = document.getElementById('stats-info');

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    setupEventListeners();
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
    // 发送按钮
    sendBtn.addEventListener('click', sendMessage);

    // 输入框
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 自动调整高度
    userInput.addEventListener('input', autoResize);

    // 新对话
    newChatBtn.addEventListener('click', newChat);

    // 示例查询
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

// ========== 对话管理 ==========
function newChat() {
    messagesDiv.innerHTML = '';
    welcomeScreen.classList.remove('hidden');
    userInput.value = '';
    userInput.style.height = 'auto';
}

function sendMessage() {
    const text = userInput.value.trim();
    if (!text || sendBtn.disabled) return;

    // 隐藏欢迎页
    welcomeScreen.classList.add('hidden');

    // 添加用户消息
    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';

    // 禁用输入
    setLoading(true);

    // 添加 AI 消息占位（含进度条）
    const aiMsg = appendMessage('assistant', '');
    const contentEl = aiMsg.querySelector('.message-content');

    // 创建进度条
    const progressEl = createProgressBar();
    contentEl.innerHTML = '';
    contentEl.appendChild(progressEl);

    // 结果文本容器
    const resultEl = document.createElement('div');
    contentEl.appendChild(resultEl);

    let fullText = '';
    let gotContent = false;

    // 发送请求
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
                    setLoading(false);
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));

                        // 进度事件
                        if (data.progress !== undefined) {
                            updateProgress(progressEl, data.progress, data.stage);
                        }

                        // 文本 token
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
                            setLoading(false);
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }

                read();
            }).catch(err => {
                resultEl.innerHTML = `<p style="color: #ef4444;">读取响应失败: ${err.message}</p>`;
                setLoading(false);
            });
        }

        read();
    }).catch(err => {
        resultEl.innerHTML = `<p style="color: #ef4444;">请求失败: ${err.message}</p>`;
        setLoading(false);
    });
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
    // 1.5秒后淡出
    setTimeout(() => {
        el.style.transition = 'opacity 0.5s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 500);
    }, 1500);
}

// ========== 消息渲染 ==========
function appendMessage(role, content) {
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
    if (text) {
        contentEl.innerHTML = renderMarkdown(text);
    }
}

function renderMarkdown(text) {
    if (!text) return '';
    // 使用 marked 库渲染
    if (typeof marked !== 'undefined') {
        return marked.parse(text);
    }
    // 降级：简单换行
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

function setLoading(loading) {
    sendBtn.disabled = loading;
    userInput.disabled = loading;
    if (!loading) userInput.focus();
}
