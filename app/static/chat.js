class ChatInterface {
    constructor() {
        this.conversationId = this.generateConversationId();
        this.userId = 'frontend-user-' + Date.now();
        this.messages = [];
        this.isTyping = false;

        this.initializeElements();
        this.bindEvents();
        this.loadChatHistory();
        this.checkAPIConnection();
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
            suggestionBtns: document.querySelectorAll('.suggestion-btn'),
            connectionStatus: document.getElementById('connectionStatus'),
            connectionText: document.getElementById('connectionText')
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

        // Show enhanced processing status
        this.showProcessingStatus();

        try {
            const response = await this.callAPIWithProgress(message);
            this.hideProcessingStatus();

            // Comprehensive response handling to fix UI display issue
            console.log('Raw API response:', response);
            console.log('Response type:', typeof response);

            let messageText = '';

            // Extract message content from various response formats
            if (response && typeof response === 'object') {
                // Format 1: Response object with 'response' field (most common)
                if (response.response && typeof response.response === 'string') {
                    messageText = response.response;
                    console.log('Extracted from response.response:', messageText);
                }
                // Format 2: Response object with 'message' field
                else if (response.message && typeof response.message === 'string') {
                    messageText = response.message;
                    console.log('Extracted from response.message:', messageText);
                }
                // Format 3: Response object where 'response' is an object (error case)
                else if (response.response && typeof response.response === 'object') {
                    // This is the problematic case - extract from nested object
                    if (response.response.message) {
                        messageText = response.response.message;
                        console.log('Extracted from response.response.message:', messageText);
                    } else if (response.response.response) {
                        messageText = response.response.response;
                        console.log('Extracted from response.response.response:', messageText);
                    } else {
                        console.warn('Nested object response found but no message field:', response.response);
                        messageText = JSON.stringify(response.response);
                    }
                }
                // Format 4: Fallback - convert to string
                else {
                    console.warn('Unknown response format, converting to string');
                    messageText = JSON.stringify(response);
                }
            } else if (typeof response === 'string') {
                messageText = response;
                console.log('Using string response directly:', messageText);
            } else {
                console.error('Invalid response format:', response);
                messageText = 'I apologize, but I received an unexpected response format. Please try again.';
            }

            // Add the extracted message to the chat
            if (messageText) {
                this.addMessage(messageText, 'bot');
                this.saveChatHistory();
            } else {
                this.addMessage('I apologize, but I couldn\'t process the response. Please try again.', 'bot', true);
            }
        } catch (error) {
            this.hideProcessingStatus();
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
            const errorText = await response.text();
            console.error('API Error Response:', errorText);
            throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
        }

        const data = await response.json();
        console.log('API Response:', data);
        return data;
    }

    async callStreamingAPI(message) {
        const response = await fetch('/api/v1/chat/message/stream', {
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
            const errorText = await response.text();
            console.error('Streaming API Error Response:', errorText);
            throw new Error(`Streaming API error! status: ${response.status} - ${errorText}`);
        }

        return response;
    }

    addMessage(text, sender, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = `message-content ${isError ? 'error-message' : ''}`;

        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';

        // Handle case where text might be an object (JSON response issue)
        if (typeof text === 'object' && text !== null) {
            console.warn('addMessage received an object instead of string:', text);
            // Extract the actual message content from the object
            let extractedText = '';

            if (text.response) {
                if (typeof text.response === 'string') {
                    extractedText = text.response;
                } else if (text.response.message) {
                    extractedText = text.response.message;
                } else if (text.response.response) {
                    extractedText = text.response.response;
                } else {
                    extractedText = JSON.stringify(text.response);
                }
            } else if (text.message) {
                if (typeof text.message === 'string') {
                    extractedText = text.message;
                } else {
                    extractedText = JSON.stringify(text.message);
                }
            } else if (text.content) {
                extractedText = text.content;
            } else {
                extractedText = JSON.stringify(text);
            }

            console.log('Extracted text from object:', extractedText);
            textDiv.textContent = extractedText;
        } else {
            textDiv.textContent = text;
        }

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

    showProcessingStatus() {
        this.isTyping = true;
        this.processingElement = null;

        // Add processing message as a chat message
        this.addProcessingMessage();
        this.scrollToBottom();
    }

    hideProcessingStatus() {
        this.isTyping = false;

        // Remove processing message if it exists
        if (this.processingElement) {
            this.processingElement.remove();
            this.processingElement = null;
        }

        // Show typing indicator for final response
        this.elements.typingIndicator.style.display = 'flex';
        this.scrollToBottom();
    }

    addProcessingMessage() {
        const processingHTML = `
            <div class="message bot processing-message">
                <div class="processing-avatar">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2ZM21 9V7L15 1L9 7V9C9 10.1 9.9 11 11 11H13V22C13 22.6 13.4 23 14 23H18C18.6 23 19 22.6 19 22V11H21C22.1 11 23 10.1 23 9Z" fill="currentColor"/>
                    </svg>
                </div>
                <div class="processing-content">
                    <div class="processing-text">
                        <span class="processing-stage-text">Understanding your request</span>
                        <span class="processing-dots">
                            <span class="processing-dot"></span>
                            <span class="processing-dot"></span>
                            <span class="processing-dot"></span>
                        </span>
                    </div>
                </div>
            </div>
        `;

        this.elements.chatMessages.insertAdjacentHTML('beforeend', processingHTML);
        this.processingElement = this.elements.chatMessages.lastElementChild;
    }

    updateProcessingStageFromMessage(statusMessage) {
        console.log('updateProcessingStageFromMessage called with:', statusMessage); // Debug logging
        if (!this.processingElement) {
            console.log('No processing element found'); // Debug logging
            return;
        }

        // Map various status messages to user-friendly stages
        const stageMapping = {
            'Initializing LangGraph workflow...': 'Initializing conversation',
            'Processing message with intelligent routing...': 'Analyzing your intent',
            'Using streamlined system...': 'Initializing conversation',
            'Initializing conversation': 'Initializing conversation',
            'Analyzing your intent': 'Analyzing your intent',
            'Determining search parameters': 'Determining search parameters',
            'Searching Shopify products': 'Searching Shopify products',
            'Creating personalized recommendations': 'Creating personalized recommendations',
            // Legacy mappings for compatibility
            'Understanding your request': 'Initializing conversation',
            'Analyzing your requirements': 'Analyzing your intent',
            'Preparing product search': 'Determining search parameters',
            'Searching Shopify store': 'Searching Shopify products',
            'Searching for products': 'Searching Shopify products',
            'Finding relevant products': 'Searching Shopify products',
            'Analyzing search results': 'Creating personalized recommendations',
            'Generating personalized response': 'Creating personalized recommendations',
            'Finalizing recommendations': 'Creating personalized recommendations',
            'Preparing recommendations': 'Creating personalized recommendations'
        };

        // Extract stage from status message
        let mappedStage = statusMessage;
        for (const [key, value] of Object.entries(stageMapping)) {
            if (statusMessage.includes(key) || statusMessage.toLowerCase().includes(value.toLowerCase())) {
                mappedStage = value;
                console.log('Mapped stage:', statusMessage, '->', mappedStage); // Debug logging
                break;
            }
        }

        const stageText = this.processingElement.querySelector('.processing-stage-text');
        if (stageText) {
            console.log('Updating stage text to:', mappedStage); // Debug logging
            stageText.textContent = mappedStage;
        } else {
            console.log('No stage text element found'); // Debug logging
        }
    }

    // Optional: You can also add a streaming effect for responses
    addStreamingResponse(text) {
        if (this.processingElement) {
            this.processingElement.remove();
            this.processingElement = null;
        }

        const streamingMessage = document.createElement('div');
        streamingMessage.className = 'message bot';
        streamingMessage.innerHTML = `
            <div class="bot-avatar small">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2ZM21 9V7L15 1L9 7V9C9 10.1 9.9 11 11 11H13V22C13 22.6 13.4 23 14 23H18C18.6 23 19 22.6 19 22V11H21C22.1 11 23 10.1 23 9Z" fill="currentColor"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="streaming-text">${text}<span class="streaming-cursor"></span></div>
                <div class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}</div>
            </div>
        `;

        this.elements.chatMessages.appendChild(streamingMessage);
        this.scrollToBottom();

        return streamingMessage;
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

    async callAPIWithProgress(message) {
        // Use the streaming API to get real progress updates
        return await this.processStreamingResponse(message);
    }

    async processStreamingResponse(message) {
        const response = await this.callStreamingAPI(message);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResponse = null;

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            console.log('Received streaming data:', data); // Debug logging

                            switch (data.type) {
                                case 'status':
                                    console.log('Updating status to:', data.message); // Debug logging
                                    this.updateProcessingStageFromMessage(data.message);
                                    break;
                                case 'response':
                                    console.log('Received response content:', data.content); // Debug logging
                                    finalResponse = { response: data.content, success: true };
                                    break;
                                case 'complete':
                                    console.log('Processing complete'); // Debug logging
                                    // Processing finished
                                    break;
                                case 'error':
                                    throw new Error(data.message);
                            }
                        } catch (parseError) {
                            console.warn('Failed to parse streaming data:', line);
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }

        // If we didn't get a response from streaming, fall back to regular API
        if (!finalResponse) {
            console.log('No response from streaming, falling back to regular API'); // Debug logging
            return await this.callAPI(message);
        }

        console.log('Final response:', finalResponse); // Debug logging
        return finalResponse;
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
        this.setConnectionStatus('offline', 'Connection lost');
        this.addMessage('Connection lost. Trying to reconnect...', 'bot', true);
        setTimeout(() => {
            this.addMessage('Connection restored! You can continue chatting.', 'bot');
            this.setConnectionStatus('online', 'Online - Ready to help');
        }, 2000);
    }

    // Connection status management
    setConnectionStatus(status, text) {
        if (!this.elements.connectionStatus || !this.elements.connectionText) return;

        this.elements.connectionStatus.className = `status-dot ${status}`;
        this.elements.connectionText.textContent = text;

        console.log(`Connection status: ${status} - ${text}`);
    }

    async checkAPIConnection() {
        try {
            this.setConnectionStatus('connecting', 'Checking connection...');
            const response = await fetch('/api/v1/chat/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    message: 'Hello, just checking connection',
                    user_id: this.userId
                })
            });

            if (response.ok) {
                this.setConnectionStatus('online', 'Online - Ready to help');
                console.log('API connection successful');
            } else {
                this.setConnectionStatus('offline', 'API connection failed');
                console.warn('API connection failed:', response.status);
            }
        } catch (error) {
            this.setConnectionStatus('offline', 'API connection failed');
            console.error('API connection error:', error);
        }
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
