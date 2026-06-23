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

    // 添加 AI 消息占位
    const aiMsg = appendMessage('assistant', '');
    const contentEl = aiMsg.querySelector('.message-content');

    // 显示加载动画
    contentEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

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
        let fullText = '';
        let gotContent = false;

        function read() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    finalizeMessage(contentEl, fullText);
                    setLoading(false);
                    return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留未完成的行

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.token) {
                            if (!gotContent) {
                                contentEl.innerHTML = '';
                                gotContent = true;
                            }
                            fullText += data.token;
                            contentEl.innerHTML = renderMarkdown(fullText);
                            scrollToBottom();
                        }
                        if (data.done) {
                            finalizeMessage(contentEl, fullText);
                            setLoading(false);
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }

                read();
            }).catch(err => {
                contentEl.innerHTML = `<p style="color: #ef4444;">读取响应失败: ${err.message}</p>`;
                setLoading(false);
            });
        }

        read();
    }).catch(err => {
        contentEl.innerHTML = `<p style="color: #ef4444;">请求失败: ${err.message}</p>`;
        setLoading(false);
    });
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
