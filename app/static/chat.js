class ChatInterface {
    constructor() {
        this.conversationId = this.generateConversationId();
        this.userId = 'frontend-user-' + Date.now();
        this.messages = [];
        this.isTyping = false;

        this.initializeElements();
        this.bindEvents();
        this.loadChatHistory();
    }

    generateConversationId() {
        return 'conv-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    }

    initializeElements() {
        this.elements = {
            chatMessages: document.getElementById('chatMessages'),
            messageInput: document.getElementById('messageInput'),
            sendBtn: document.getElementById('sendBtn'),
            clearChatBtn: document.getElementById('clearChatBtn'),
            typingIndicator: document.getElementById('typingIndicator'),
            charCount: document.getElementById('charCount'),
            suggestionBtns: document.querySelectorAll('.suggestion-btn')
        };
    }

    bindEvents() {
        // Send message events
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        this.elements.messageInput.addEventListener('keydown', (e) => this.handleKeyPress(e));
        this.elements.messageInput.addEventListener('input', () => this.handleInputChange());

        // Clear chat event
        this.elements.clearChatBtn.addEventListener('click', () => this.clearChat());

        // Suggestion buttons
        this.elements.suggestionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.getAttribute('data-message');
                this.elements.messageInput.value = message;
                this.handleInputChange();
                this.sendMessage();
            });
        });

        // Auto-resize textarea
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.messageInput.style.height = 'auto';
            this.elements.messageInput.style.height = Math.min(this.elements.messageInput.scrollHeight, 120) + 'px';
        });
    }

    handleKeyPress(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.sendMessage();
        }
    }

    handleInputChange() {
        const text = this.elements.messageInput.value;
        const charCount = text.length;

        this.elements.charCount.textContent = `${charCount} / 2000`;
        this.elements.sendBtn.disabled = !text.trim() || charCount > 2000;

        if (charCount > 1800) {
            this.elements.charCount.style.color = '#dc2626';
        } else if (charCount > 1500) {
            this.elements.charCount.style.color = '#f59e0b';
        } else {
            this.elements.charCount.style.color = '#6b7280';
        }
    }

    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message || this.isTyping) return;

        // Hide welcome message
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }

        // Add user message to chat
        this.addMessage(message, 'user');
        this.elements.messageInput.value = '';
        this.handleInputChange();
        this.elements.messageInput.style.height = 'auto';

        // Show typing indicator
        this.showTypingIndicator();

        try {
            const response = await this.callAPI(message);
            this.hideTypingIndicator();

            if (response.success) {
                this.addMessage(response.message, 'bot');
                this.saveChatHistory();
            } else {
                this.addMessage('I apologize, but I encountered an error. Please try again.', 'bot', true);
            }
        } catch (error) {
            this.hideTypingIndicator();
            console.error('API Error:', error);
            this.addMessage('I apologize, but I\'m having trouble connecting. Please try again in a moment.', 'bot', true);
        }
    }

    async callAPI(message) {
        const response = await fetch('/api/v1/chat/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: this.conversationId,
                message: message,
                user_id: this.userId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    addMessage(text, sender, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = `message-content ${isError ? 'error-message' : ''}`;

        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = text;

        const timeDiv = document.createElement('span');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });

        contentDiv.appendChild(textDiv);
        contentDiv.appendChild(timeDiv);

        if (sender === 'bot') {
            const avatar = this.createBotAvatar();
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);
        } else {
            messageDiv.appendChild(contentDiv);
        }

        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        // Store message
        this.messages.push({
            text: text,
            sender: sender,
            timestamp: new Date().toISOString(),
            isError: isError
        });
    }

    createBotAvatar() {
        const avatar = document.createElement('div');
        avatar.className = 'bot-avatar small';
        avatar.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2ZM21 9V7L15 1L9 7V9C9 10.1 9.9 11 11 11H13V22C13 22.6 13.4 23 14 23H18C18.6 23 19 22.6 19 22V11H21C22.1 11 23 10.1 23 9Z" fill="currentColor"/>
            </svg>
        `;
        return avatar;
    }

    showTypingIndicator() {
        this.isTyping = true;
        this.elements.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.isTyping = false;
        this.elements.typingIndicator.style.display = 'none';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        }, 100);
    }

    clearChat() {
        if (confirm('Are you sure you want to clear the chat history?')) {
            // Clear messages from DOM
            const messages = this.elements.chatMessages.querySelectorAll('.message');
            messages.forEach(message => message.remove());

            // Clear message array
            this.messages = [];

            // Generate new conversation ID
            this.conversationId = this.generateConversationId();

            // Show welcome message
            const welcomeMessage = document.querySelector('.welcome-message');
            if (welcomeMessage) {
                welcomeMessage.style.display = 'block';
            }

            // Clear localStorage
            localStorage.removeItem('chatHistory');

            // Focus input
            this.elements.messageInput.focus();
        }
    }

    saveChatHistory() {
        try {
            const chatHistory = {
                conversationId: this.conversationId,
                userId: this.userId,
                messages: this.messages.slice(-50), // Keep only last 50 messages
                timestamp: new Date().toISOString()
            };
            localStorage.setItem('chatHistory', JSON.stringify(chatHistory));
        } catch (error) {
            console.warn('Failed to save chat history:', error);
        }
    }

    loadChatHistory() {
        try {
            const saved = localStorage.getItem('chatHistory');
            if (saved) {
                const chatHistory = JSON.parse(saved);

                // Only restore if it's from the last 24 hours
                const savedTime = new Date(chatHistory.timestamp);
                const now = new Date();
                const hoursDiff = (now - savedTime) / (1000 * 60 * 60);

                if (hoursDiff < 24 && chatHistory.messages.length > 0) {
                    this.conversationId = chatHistory.conversationId;
                    this.userId = chatHistory.userId;

                    // Hide welcome message
                    const welcomeMessage = document.querySelector('.welcome-message');
                    if (welcomeMessage) {
                        welcomeMessage.style.display = 'none';
                    }

                    // Restore messages
                    chatHistory.messages.forEach(msg => {
                        this.addMessage(msg.text, msg.sender, msg.isError);
                    });
                }
            }
        } catch (error) {
            console.warn('Failed to load chat history:', error);
        }
    }

    // Handle page visibility changes
    handleVisibilityChange() {
        if (document.visibilityState === 'visible') {
            // Page is visible, focus input
            this.elements.messageInput.focus();
        }
    }

    // Handle connection errors
    handleConnectionError() {
        this.addMessage('Connection lost. Trying to reconnect...', 'bot', true);
        setTimeout(() => {
            this.addMessage('Connection restored! You can continue chatting.', 'bot');
        }, 2000);
    }
}

// Initialize chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const chat = new ChatInterface();

    // Handle page visibility
    document.addEventListener('visibilitychange', () => {
        chat.handleVisibilityChange();
    });

    // Handle connection issues
    window.addEventListener('online', () => {
        chat.addMessage('Connection restored! You can continue chatting.', 'bot');
    });

    window.addEventListener('offline', () => {
        chat.addMessage('Connection lost. Please check your internet connection.', 'bot', true);
    });

    // Focus input on load
    document.getElementById('messageInput').focus();
});

// Prevent form submission on page refresh
window.addEventListener('beforeunload', (e) => {
    const messageInput = document.getElementById('messageInput');
    if (messageInput.value.trim()) {
        e.preventDefault();
        e.returnValue = '';
    }
});// Test change
