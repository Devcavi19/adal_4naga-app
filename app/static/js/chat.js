// DOM Elements
const sendButton = document.getElementById('send-button');
const messageInput = document.getElementById('message-input');
const messagesContainer = document.getElementById('messages-container');
const welcomeScreen = document.getElementById('welcome-screen');
const chatArea = document.getElementById('chat-area');
const chatContentWrapper = document.querySelector('.chat-content-wrapper');
const newChatBtn = document.getElementById('new-chat-btn');
const feedbackBtn = document.getElementById('feedback-btn');
const settingsBtn = document.getElementById('settings-btn');
const dashboardBtn = document.getElementById('dashboard-btn');
const shareBtn = document.getElementById('share-btn');
const sidebar = document.getElementById('sidebar');
const robotExpandBtn = document.getElementById('robot-expand-btn');
const sidebarCollapseBtn = document.getElementById('sidebar-collapse-btn');
const userProfileTrigger = document.getElementById('user-profile-trigger');
const userDropdownMenu = document.getElementById('user-dropdown-menu');
const logoutBtn = document.getElementById('logout-btn');

// State
let isTyping = false;
let currentChatId = null;
let currentUser = null; // Store user info

// Configure marked.js for better Markdown rendering
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false,
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (err) {}
            }
            return code;
        }
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadChatHistory();
    fetchCurrentUser(); // Fetch user info on load
    
    // Load sidebar state from localStorage
    const sidebarState = localStorage.getItem('sidebarCollapsed');
    if (sidebarState === 'false') {
        sidebar.classList.remove('collapsed');
    }
});

// Fetch current user information
async function fetchCurrentUser() {
    try {
        const response = await fetch('/api/auth/user');
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
        }
    } catch (error) {
        console.error('Error fetching user:', error);
    }
}

// Generate avatar URL for user
function getUserAvatarUrl() {
    if (!currentUser) {
        return 'https://ui-avatars.com/api/?name=Student&background=10b981&color=fff';
    }
    const name = encodeURIComponent(currentUser.full_name || 'Student');
    return `https://ui-avatars.com/api/?name=${name}&background=10b981&color=fff`;
}

function setupEventListeners() {
    // Robot icon expand button
    if (robotExpandBtn) {
        robotExpandBtn.addEventListener('click', expandSidebar);
    }
    
    // X icon collapse button
    if (sidebarCollapseBtn) {
        sidebarCollapseBtn.addEventListener('click', collapseSidebar);
    }
    
    // Send button click
    sendButton.addEventListener('click', handleSendMessage);
    
    // Enter key press
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    // New chat button
    if (newChatBtn) {
        newChatBtn.addEventListener('click', (e) => {
            e.preventDefault();
            startNewChat();
        });
    }
    
    // Share button
    if (shareBtn) {
        shareBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showShareModal();
        });
    }
    
    // Feedback button
    if (feedbackBtn) {
        feedbackBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showFeedbackModal();
        });
    }

    // Settings button
    if (settingsBtn) {
        settingsBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showSettingsModal();
        });
    }

    // Dashboard button (admin only)
    if (dashboardBtn) {
        dashboardBtn.addEventListener('click', (e) => {
            e.preventDefault();
            // Close dropdown
            if (userDropdownMenu) {
                userDropdownMenu.classList.remove('show');
            }
            // Navigate to admin dashboard
            window.location.href = '/admin';
        });
    }

    // User profile dropdown
    if (userProfileTrigger && userDropdownMenu) {
        userProfileTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdownMenu.classList.toggle('show');
            userProfileTrigger.classList.toggle('active');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!userProfileTrigger.contains(e.target) && !userDropdownMenu.contains(e.target)) {
                userDropdownMenu.classList.remove('show');
                userProfileTrigger.classList.remove('active');
            }
        });
    }
    
    // Logout button
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            await handleLogout();
        });
    }
}

function expandSidebar() {
    sidebar.classList.remove('collapsed');
    localStorage.setItem('sidebarCollapsed', 'false');
    robotExpandBtn.title = 'Sidebar expanded';
}

function collapseSidebar() {
    sidebar.classList.add('collapsed');
    localStorage.setItem('sidebarCollapsed', 'true');
    robotExpandBtn.title = 'Expand sidebar';
}

function startNewChat() {
    // Clear current chat
    messagesContainer.innerHTML = '';
    messagesContainer.classList.remove('active');
    welcomeScreen.style.display = 'block';
    currentChatId = null;
    messageInput.value = '';
    
    // Update active state
    document.querySelectorAll('.chat-history-item').forEach(item => {
        item.classList.remove('active');
    });
}

function loadChatHistory() {
    // Load chat history from backend
    fetch('/api/chat/history')
        .then(response => response.json())
        .then(data => {
            const historyList = document.getElementById('chat-history-list');
            if (data.history && data.history.length > 0) {
                historyList.innerHTML = data.history.map(chat => `
                    <a href="#" class="nav-item chat-history-item" data-chat-id="${chat.id}" title="${escapeHtml(chat.title)}">
                        <i class="fas fa-message"></i>
                        <span class="sidebar-text">${escapeHtml(chat.title)}</span>
                        <button class="delete-chat-btn" data-chat-id="${chat.id}" title="Delete chat">
                            <i class="fas fa-trash"></i>
                        </button>
                    </a>
                `).join('');
                
                // Add click listeners to history items
                document.querySelectorAll('.chat-history-item').forEach(item => {
                    item.addEventListener('click', (e) => {
                        if (!e.target.closest('.delete-chat-btn')) {
                            e.preventDefault();
                            loadChat(item.dataset.chatId);
                        }
                    });
                });
                
                // Add delete listeners
                document.querySelectorAll('.delete-chat-btn').forEach(btn => {
                    btn.addEventListener('click', async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        await deleteChat(btn.dataset.chatId);
                    });
                });
            } else {
                historyList.innerHTML = '<div class="no-history"><span class="sidebar-text">No chat history yet</span></div>';
            }
        })
        .catch(error => console.error('Error loading chat history:', error));
}

function loadChat(chatId) {
    // Load specific chat from backend
    fetch(`/api/chat/${chatId}`)
        .then(response => response.json())
        .then(data => {
            if (data.chat_id && data.messages) {
                currentChatId = chatId;
                
                // Clear current messages
                messagesContainer.innerHTML = '';
                welcomeScreen.style.display = 'none';
                messagesContainer.classList.add('active');
                
                // Load messages
                if (data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        addMessage(msg.role, msg.content, null, msg.role === 'bot');
                    });
                    scrollToBottom();
                }
                
                // Update active state
                document.querySelectorAll('.chat-history-item').forEach(item => {
                    item.classList.remove('active');
                });
                document.querySelector(`[data-chat-id="${chatId}"]`)?.classList.add('active');
            }
        })
        .catch(error => {
            console.error('Error loading chat:', error);
            alert('Failed to load chat');
        });
}

async function deleteChat(chatId) {
    if (!confirm('Are you sure you want to delete this chat?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/chat/${chatId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            // Remove from UI
            document.querySelector(`[data-chat-id="${chatId}"]`)?.remove();
            
            // If it was the current chat, start new
            if (currentChatId === chatId) {
                startNewChat();
            }
            
            // Reload history to update UI
            loadChatHistory();
        } else {
            alert('Failed to delete chat');
        }
    } catch (error) {
        console.error('Error deleting chat:', error);
        alert('Failed to delete chat');
    }
}

function showFeedbackModal() {
    alert('Feedback feature coming soon!\n\nPlease share your thoughts about the AI assistant.');
}

function showSettingsModal() {
    alert('Settings feature coming soon!\n\nSettings include:\n\n• Theme: Light/Dark\n• Language: English/Filipino\n• Notifications: On/Off');
}

function showShareModal() {
    alert('Share feature coming soon!\n\nYou will be able to share messages and prompts with others.');
}

async function handleSendMessage() {
    const message = messageInput.value.trim();
    
    if (!message || isTyping) return;
    
    // Hide welcome screen and show messages
    if (welcomeScreen.style.display !== 'none') {
            welcomeScreen.style.display = 'none';
            messagesContainer.classList.add('active');
    }
    
    // Clear input
    messageInput.value = '';
    
    // Add user message
    addMessage('user', message);
    
    // Show typing indicator
    isTyping = true;
    const typingId = addTypingIndicator();
    
    try {
        // Send message to backend with streaming
        await sendMessageWithStreaming(message, typingId);
        
        // Save to chat history
        saveToChatHistory(message);
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator(typingId);
        addMessage('bot', 'Sorry, something went wrong. Please try again.');
        isTyping = false;
    }
}

async function handleLogout() {
    try {
        const response = await fetch('/api/auth/signout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            // Clear session storage
            sessionStorage.removeItem('access_token');
            // Redirect to login
            window.location.href = '/login';
        } else {
            console.error('Logout failed');
            alert('Failed to log out. Please try again.');
        }
    } catch (error) {
        console.error('Logout error:', error);
        alert('An error occurred while logging out.');
    }
}

function saveToChatHistory(message) {
    // This is now handled by the backend
    // Just reload the history list when a new chat starts
    if (!currentChatId) {
        setTimeout(() => {
            loadChatHistory();
        }, 500);
    }
}

function addMessage(sender, text, id = null, isMarkdown = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    if (id) messageDiv.id = id;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    
    // Use image for both bot and user
    if (sender === 'bot') {
        const avatarImg = document.createElement('img');
        avatarImg.src = '/static/img/adal_iconb.png';
        avatarImg.alt = 'Adal AI';
        avatarImg.style.width = '100%';
        avatarImg.style.height = '100%';
        avatarImg.style.objectFit = 'contain';
        avatar.appendChild(avatarImg);
    } else {
        // User avatar - use profile image
        const avatarImg = document.createElement('img');
        avatarImg.src = getUserAvatarUrl();
        avatarImg.alt = currentUser?.full_name || 'Student';
        avatarImg.style.width = '100%';
        avatarImg.style.height = '100%';
        avatarImg.style.objectFit = 'cover';
        avatarImg.style.borderRadius = '50%';
        avatar.appendChild(avatarImg);
    }
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    const header = document.createElement('div');
    header.className = 'message-header';
    
    const senderName = document.createElement('span');
    senderName.className = 'message-sender';
    senderName.textContent = sender === 'user' ? (currentUser?.full_name || 'You') : 'ADAL';
    
    header.appendChild(senderName);
    
    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    
    // Render markdown for bot messages, plain text for user messages
    if (isMarkdown && sender === 'bot' && typeof marked !== 'undefined') {
        messageText.innerHTML = marked.parse(text);
        addCopyButtonsToCodeBlocks(messageText);
        // Make all links open in new tab
        makeLinksOpenInNewTab(messageText);
    } else {
        messageText.textContent = text;
    }
    
    content.appendChild(header);
    content.appendChild(messageText);
    
    // Add feedback buttons for bot messages (only for new messages, not history)
    if (sender === 'bot' && !id) {
        // Generate temporary ID based on timestamp
        const tempId = `temp_${Date.now()}`;
        messageDiv.dataset.tempId = tempId;
        
        const feedbackContainer = document.createElement('div');
        feedbackContainer.className = 'feedback-buttons';
        feedbackContainer.innerHTML = `
            <button class="feedback-btn thumbs-up" data-temp-id="${tempId}" title="Helpful">
                <i class="fas fa-thumbs-up"></i>
            </button>
            <button class="feedback-btn thumbs-down" data-temp-id="${tempId}" title="Not helpful">
                <i class="fas fa-thumbs-down"></i>
            </button>
        `;
        content.appendChild(feedbackContainer);
        
        // Add event listeners
        feedbackContainer.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                const rating = btn.classList.contains('thumbs-up') ? 5 : 1;
                const feedbackText = rating === 5 ? 'positive' : 'negative';
                
                // Submit feedback with session context (backend will find the latest bot message)
                await submitFeedback(currentChatId, rating, feedbackText);
                
                // Visual feedback
                feedbackContainer.innerHTML = '<span style="color: #10b981; font-size: 14px;"><i class="fas fa-check"></i> Thank you for your feedback!</span>';
            });
        });
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    
    return messageDiv;
}

async function submitFeedback(chatSessionId, rating, feedbackText = '') {
    try {
        // Get the most recent bot message from current session
        // The backend will match this to the latest bot message in the chat session
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chat_session_id: chatSessionId,
                rating: rating,
                feedback_text: feedbackText
            })
        });
        
        if (!response.ok) {
            console.error('Failed to submit feedback');
        }
    } catch (error) {
        console.error('Error submitting feedback:', error);
    }
}

function addCopyButtonsToCodeBlocks(messageElement) {
    const codeBlocks = messageElement.querySelectorAll('pre code');
    codeBlocks.forEach((codeBlock, index) => {
        const pre = codeBlock.parentElement;
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';
        
        pre.parentNode.insertBefore(wrapper, pre);
        wrapper.appendChild(pre);
        
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-code-btn';
        copyBtn.textContent = 'Copy';
        copyBtn.onclick = () => {
            const code = codeBlock.textContent;
            navigator.clipboard.writeText(code).then(() => {
                copyBtn.textContent = 'Copied!';
                copyBtn.classList.add('copied');
                setTimeout(() => {
                    copyBtn.textContent = 'Copy';
                    copyBtn.classList.remove('copied');
                }, 2000);
            });
        };
        
        wrapper.insertBefore(copyBtn, pre);
    });
}

function makeLinksOpenInNewTab(messageElement) {
    const links = messageElement.querySelectorAll('a');
    links.forEach(link => {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
    });
}

function addTypingIndicator() {
    const id = 'typing-' + Date.now();
    const messageDiv = document.createElement('div');
    messageDiv.id = id;
    messageDiv.className = 'message bot-message';
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    
    // Use image for typing indicator avatar
    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/img/adal_iconb.png';
    avatarImg.alt = 'Adal AI';
    avatarImg.style.width = '100%';
    avatarImg.style.height = '100%';
    avatarImg.style.objectFit = 'contain';
    avatar.appendChild(avatarImg);
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = `
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
    `;
    
    messageText.appendChild(typingIndicator);
    content.appendChild(messageText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);
    
    messagesContainer.appendChild(messageDiv);
    scrollToBottom();
    
    return id;
}

function removeTypingIndicator(id) {
    const typingElement = document.getElementById(id);
    if (typingElement) {
        typingElement.remove();
    }
}

async function sendMessageWithStreaming(message, typingId) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                chat_id: currentChatId 
            })
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        // Remove typing indicator
        removeTypingIndicator(typingId);
        
        // Create message element for streaming response
        const botMessageDiv = addMessage('bot', '▊'); // Start with cursor
        const messageTextElement = botMessageDiv.querySelector('.message-text');
        
        // Read the stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        let isFirstToken = true;
        let renderQueue = '';
        let lastRenderTime = 0;
        const renderInterval = 16; // ~60fps for smooth rendering
        
        // Add streaming indicator class
        messageTextElement.classList.add('streaming');
        
        // Optimized render function with RAF for smooth 60fps updates
        function renderUpdate() {
            if (renderQueue) {
                fullText += renderQueue;
                renderQueue = '';
                
                // Fast rendering with markdown
                if (typeof marked !== 'undefined') {
                    messageTextElement.innerHTML = marked.parse(fullText + '▊');
                    addCopyButtonsToCodeBlocks(messageTextElement);
                    makeLinksOpenInNewTab(messageTextElement);
                } else {
                    messageTextElement.textContent = fullText + '▊';
                }
                
                scrollToBottom();
            }
        }
        
        // Use RAF for consistent 60fps rendering
        let rafId = null;
        function scheduleRender() {
            if (!rafId) {
                rafId = requestAnimationFrame(() => {
                    renderUpdate();
                    rafId = null;
                });
            }
        }
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
                // Final render
                if (renderQueue) {
                    renderUpdate();
                }
                messageTextElement.classList.remove('streaming');
                break;
            }
            
            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n').filter(line => line.trim());
            
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    
                    // Handle chat_id from server
                    if (data.chat_id && !currentChatId) {
                        currentChatId = data.chat_id;
                        // Reload history to show new chat
                        setTimeout(() => {
                            loadChatHistory();
                        }, 500);
                    }
                    
                    if (data.token) {
                        // Remove cursor on first token
                        if (isFirstToken) {
                            fullText = '';
                            renderQueue = '';
                            isFirstToken = false;
                        }
                        
                        // Add to render queue and schedule immediate render
                        renderQueue += data.token;
                        scheduleRender();
                    }
                } catch (e) {
                    console.error('Error parsing JSON:', e);
                }
            }
        }
        
        // Final render without cursor
        if (typeof marked !== 'undefined') {
            messageTextElement.innerHTML = marked.parse(fullText);
            addCopyButtonsToCodeBlocks(messageTextElement);
            makeLinksOpenInNewTab(messageTextElement);
        } else {
            messageTextElement.textContent = fullText;
        }
        
        isTyping = false;
        
    } catch (error) {
        console.error('Streaming error:', error);
        throw error;
    }
}

function scrollToBottom() {
    // Immediate smooth scroll for better streaming UX
    if (chatContentWrapper) {
        chatContentWrapper.scrollTo({
            top: chatContentWrapper.scrollHeight,
            behavior: 'instant' // instant for real-time feeling
        });
    }
}

function formatTime(date) {
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Auto-resize textarea
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});