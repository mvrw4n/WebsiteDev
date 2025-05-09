/**
 * Wizzy Chat Module
 * Handles all chat interactions with the AI assistant
 */

class ChatManager {
    constructor() {
        // DOM elements
        this.chatContainer = document.getElementById('chatContainer');
        this.chatMessages = document.getElementById('chatMessages');
        this.userInput = document.getElementById('userInput');
        this.sendButton = document.getElementById('sendButton');
        this.clearButton = document.getElementById('clearChatButton');
        this.chatHistoryContainer = document.getElementById('chatHistoryContainer');
        this.closeButton = document.getElementById('closeChat');
        this.toggleButton = document.getElementById('toggleChat');

        // Chat state
        this.chatId = document.getElementById('chatId')?.value;
        this.isProcessingMessage = false;
        this.lastMessageTime = null;
        this.pendingActions = new Set();

        console.log('Chat manager initialized with elements:', {
            chatContainer: !!this.chatContainer,
            chatMessages: !!this.chatMessages,
            userInput: !!this.userInput,
            sendButton: !!this.sendButton,
            clearButton: !!this.clearButton,
            chatHistoryContainer: !!this.chatHistoryContainer,
            closeButton: !!this.closeButton,
            toggleButton: !!this.toggleButton,
            chatId: this.chatId
        });

        // Initialize CSS styles
        this.addCssStyles();

        // Set up event listeners
        this.setupEventListeners();

        // Create structure modal
        this.createStructureModal();

        // Load chat history for current chat
        if (this.chatId) {
            this.loadChatHistory();
        }
    }

    setupEventListeners() {
        console.log('Setting up event listeners');

        // Handle send button click
        if (this.sendButton) {
            this.sendButton.addEventListener('click', () => {
                this.sendMessage();
            });
        }

        // Handle keyboard events (Enter to send, Shift+Enter for new line)
        if (this.userInput) {
            this.userInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    this.sendMessage();
                }
            });

            // Auto-resize the textarea
            this.userInput.addEventListener('input', () => {
                this.autoResizeTextarea();
            });
        }

        // Handle clearing the chat
        if (this.clearButton) {
            this.clearButton.addEventListener('click', () => {
                if (confirm('Êtes-vous sûr de vouloir effacer toute la conversation?')) {
                    this.clearChat();
                }
            });
        }

        // Handle history item clicks
        if (this.chatHistoryContainer) {
            this.chatHistoryContainer.addEventListener('click', (event) => {
                const historyItem = event.target.closest('.chat-history-item');
                if (historyItem) {
                    const chatId = historyItem.dataset.chatId;
                    if (chatId) {
                        window.location.href = `/chat/?id=${chatId}`;
                    }
                }
            });
        }

        // Handle close button - direct selection
        if (this.closeButton) {
            console.log('Close button found, attaching event listener');
            this.closeButton.addEventListener('click', () => {
                console.log('Close button clicked');
                if (this.chatContainer) {
                    this.chatContainer.style.display = 'none';
                }

                // If there's a toggle button, make it visible
                if (this.toggleButton) {
                    this.toggleButton.style.display = 'block';
                }
            });
        } else {
            // Fallback for other DOM structures
            const closeBtn = document.querySelector('#closeChat, .chat-close-btn');
            if (closeBtn) {
                console.log('Close button found via selector, attaching event listener');
                closeBtn.addEventListener('click', () => {
                    console.log('Close button clicked (selector)');
                    const chatContainer = document.querySelector('#chatContainer, .chat-container');
                    if (chatContainer) {
                        chatContainer.style.display = 'none';
                    }

                    // If there's a toggle button, make it visible
                    const toggleBtn = document.querySelector('#toggleChat, .chat-toggle-btn');
                    if (toggleBtn) {
                        toggleBtn.style.display = 'block';
                    }
                });
            } else {
                console.warn('Close button not found');
            }
        }

        // Handle toggle button - direct selection
        if (this.toggleButton) {
            console.log('Toggle button found, attaching event listener');
            this.toggleButton.addEventListener('click', () => {
                console.log('Toggle button clicked');
                this.reopenChat();
            });
        } else {
            // Fallback for other DOM structures
            const toggleBtn = document.querySelector('#toggleChat, .chat-toggle-btn');
            if (toggleBtn) {
                console.log('Toggle button found via selector, attaching event listener');
                toggleBtn.addEventListener('click', () => {
                    console.log('Toggle button clicked (selector)');
                    this.reopenChat();
                });
            } else {
                console.warn('Toggle button not found');
            }
        }
    }

    async checkPendingActions() {
        if (this.pendingActions.size === 0) return;

        try {
            const response = await fetch('/api/chat/jobs-status/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    action_ids: Array.from(this.pendingActions)
                })
            });

            const data = await response.json();

            if (data.actions) {
                data.actions.forEach(action => {
                    if (action.status !== 'pending') {
                        this.updateActionStatus(action);
                        this.pendingActions.delete(action.id);
                    }
                });
            }
        } catch (error) {
            console.error('Error checking pending actions:', error);
        }
    }

    updateActionStatus(action) {
        const actionBlock = document.querySelector(`[data-action-id="${action.id}"]`);
        if (!actionBlock) return;

        const statusDiv = actionBlock.querySelector('.action-status');
        if (statusDiv) {
            statusDiv.className = `action-status ${action.status}`;
            statusDiv.innerHTML = `<i class="fas ${this.getStatusIcon(action.status)}"></i> ${this.getStatusText(action.status)}`;

            if (action.result) {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'action-result';
                resultDiv.textContent = action.result;
                actionBlock.appendChild(resultDiv);
            }
        }
    }

    async sendMessage(message = null) {
        try {
            // Get the message from the input if not provided
            if (!message) {
                message = this.userInput.value.trim();
            }

            if (!message || this.isProcessingMessage) {
                return;
            }

            this.isProcessingMessage = true;
            this.showThinkingIndicator();
            this.sendButton.disabled = true;
            this.userInput.value = '';
            this.autoResizeTextarea();

            // Log the message being sent (truncate for display if too long)
            console.log(`Sending message: ${message.length > 50 ? message.substring(0, 50) + '...' : message}`);

            // Add the user message to the chat
            this.addMessage(message, 'user');
            this.scrollToBottom();

            try {
                // Use AuthManager to make authenticated request
                const response = await AuthManager.fetchWithAuth('/api/chat/send/', {
                    method: 'POST',
                    body: JSON.stringify({ message }),
                });

                // Remove thinking indicator
                this.removeThinkingIndicator();

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                // Enhanced debugging for response data
                console.log('Chat response received:', data);
                console.log('Response data properties:', Object.keys(data));
                console.log('Actions launched:', data.actions_launched);

                // Process the response data
                if (!data.success) {
                    // If the response indicates a failure, show the error message
                    const errorMessage = data.message || 'Une erreur est survenue lors de la communication avec l\'IA.';
                    this.showError(errorMessage);
                    console.error('Error response from server:', data);
                    return;
                }

                // Process AI message if available
                if (data.message) {
                    this.addMessage(data.message, 'ai');
                } else if (data.response_chat) {
                    this.addMessage(data.response_chat, 'ai');
                } else {
                    this.showError('Désolé, je n\'ai pas pu générer une réponse cohérente.');
                    console.error('Missing message in AI response:', data);
                }

                // Enhanced debugging for structure update
                console.log('Structure update check:', {
                    hasStructureUpdate: !!data.structure_update,
                    structureUpdateData: data.structure_update,
                    updateStatus: data.structure_update_status
                });

                // Process structure update if available (prioritize this)
                if (data.structure_update && typeof data.structure_update === 'object') {
                    console.log('Processing structure update:', data.structure_update);
                    try {
                        this.handleStructureUpdate(data.structure_update);
                        console.log('Structure successfully displayed');
                    } catch (structureError) {
                        console.error('Error displaying structure:', structureError);
                        this.showError('Erreur lors de l\'affichage de la structure de scraping');

                        // Try to create a minimal display anyway
                        try {
                            this.displayMinimalStructure(data.structure_update);
                        } catch (e) {
                            console.error('Failed to display minimal structure:', e);
                        }
                    }
                }
                // Then process AI actions if available and no structure was processed
                else if (data.actions_launched && data.actions_launched !== 'no_action') {
                    console.log('Processing AI actions:', data.actions_launched);
                    this.handleAIActions(data);
                }
            } catch (error) {
                console.error('Error sending message:', error);
                this.showError('Une erreur est survenue lors de l\'envoi du message. Veuillez réessayer.');
                // Make sure thinking indicator is removed even on error
                this.removeThinkingIndicator();
            }

            this.scrollToBottom();
        } catch (error) {
            console.error('Error in message processing:', error);
            this.showError('Une erreur est survenue. Veuillez réessayer.');
            // Make sure thinking indicator is removed even on error
            this.removeThinkingIndicator();
        } finally {
            // Reset state
            this.isProcessingMessage = false;
            this.sendButton.disabled = false;
            this.userInput.focus();
        }
    }

    handleAIActions(actions) {
        // Make sure actions is treated as an array even if it's a single object or has nested actions
        let actionsArray = [];

        if (Array.isArray(actions)) {
            actionsArray = actions;
        } else if (actions.actions_launched && Array.isArray(actions.actions_launched)) {
            actionsArray = actions.actions_launched;
        } else if (actions.structure_update) {
            // If we have a structure update, create a structure detection action
            actionsArray = [{
                type: 'structure_detection',
                status: 'success',
                result: { structure: actions.structure_update },
                description: 'Structure de données détectée par Wizzy'
            }];
        }

        actionsArray.forEach(action => {
            const actionBlock = document.createElement('div');
            actionBlock.className = 'action-block';
            actionBlock.dataset.actionId = action.id || Math.random().toString(36).substring(2);

            const header = document.createElement('div');
            header.className = 'action-header';
            header.innerHTML = `<i class="fas ${this.getActionIcon(action.type)}"></i> ${this.getActionTitle(action.type)}`;

            const content = document.createElement('div');
            content.className = 'action-content';
            content.textContent = action.description || '';

            const status = document.createElement('div');
            status.className = `action-status ${action.status || 'pending'}`;
            status.innerHTML = `<i class="fas ${this.getStatusIcon(action.status)}"></i> ${this.getStatusText(action.status)}`;

            actionBlock.appendChild(header);
            actionBlock.appendChild(content);
            actionBlock.appendChild(status);

            // Add view/edit button for structure actions
            if (action.type === 'structure_detection' && action.result && action.result.structure) {
                const structure = action.result.structure;
                console.log('Structure detected:', structure);

                // Only show structure if it has required fields
                if (structure) {
                    const viewButton = document.createElement('button');
                    viewButton.className = 'btn btn-sm btn-outline-primary mt-2';
                    viewButton.innerHTML = '<i class="fas fa-eye"></i> Voir/Modifier la structure';
                    viewButton.addEventListener('click', () => this.showStructureDetails(structure));
                    actionBlock.appendChild(viewButton);

                    // Add structure preview with more details
                    const previewDiv = document.createElement('div');
                    previewDiv.className = 'structure-preview mt-2';

                    // Create a more detailed preview
                    let previewHTML = '<div class="structure-info">';

                    // Add entity type with icon
                    const entityIcon = this.getEntityTypeIcon(structure.entity_type);
                    previewHTML += `<div class="structure-field"><i class="fas ${entityIcon}"></i> <strong>Type:</strong> ${structure.entity_type || 'Non spécifié'}</div>`;

                    // Add name
                    previewHTML += `<div class="structure-field"><i class="fas fa-tag"></i> <strong>Nom:</strong> ${structure.name || 'Non spécifié'}</div>`;

                    // Add strategy
                    previewHTML += `<div class="structure-field"><i class="fas fa-robot"></i> <strong>Stratégie:</strong> ${structure.scraping_strategy || 'Non spécifié'}</div>`;

                    // Add target
                    previewHTML += `<div class="structure-field"><i class="fas fa-bullseye"></i> <strong>Objectif:</strong> ${structure.leads_target_per_day || 'Non spécifié'} leads/jour</div>`;

                    // Add fields count
                    const fieldsCount = structure.structure && Array.isArray(structure.structure) ? structure.structure.length : 0;
                    previewHTML += `<div class="structure-field"><i class="fas fa-list"></i> <strong>Champs:</strong> ${fieldsCount}</div>`;

                    previewHTML += '</div>';
                    previewDiv.innerHTML = previewHTML;

                    actionBlock.appendChild(previewDiv);
                }
            }

            if (action.status === 'pending') {
                this.pendingActions.add(action.id || '');
            }

            this.chatMessages.appendChild(actionBlock);
            this.scrollToBottom();
        });
    }

    getActionTitle(type) {
        const titles = {
            'scraping': 'Recherche de leads',
            'analysis': 'Analyse des données',
            'search': 'Recherche',
            'processing': 'Traitement',
            'notification': 'Notification',
            'structure_detection': 'Structure de scraping'
        };
        return titles[type] || type;
    }

    getStatusText(status) {
        const texts = {
            'success': 'Terminé avec succès',
            'error': 'Erreur',
            'pending': 'En cours',
            'processing': 'En traitement'
        };
        return texts[status] || status;
    }

    addMessage(content, sender, timestamp = null) {
        try {
            // Create message element
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;

            // Add avatar/icon
            const iconDiv = document.createElement('div');
            iconDiv.className = 'message-icon';

            if (sender === 'user') {
                iconDiv.innerHTML = '<i class="fas fa-user"></i>';
            } else if (sender === 'ai') {
                iconDiv.innerHTML = '<i class="fas fa-robot"></i>';
            } else {
                iconDiv.innerHTML = '<i class="fas fa-info-circle"></i>';
            }

            messageDiv.appendChild(iconDiv);

            // Create message content with timestamp
            const messageContent = document.createElement('div');
            messageContent.className = 'message-content';

            // Format the message content - handle markdown-like syntax
            let formattedContent = content;

            // Simple code block highlighting
            formattedContent = formattedContent.replace(/```(\w*)([\s\S]*?)```/g, '<pre><code>$2</code></pre>');

            // Inline code highlighting
            formattedContent = formattedContent.replace(/`([^`]+)`/g, '<code>$1</code>');

            // Bold text
            formattedContent = formattedContent.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

            // Italic text
            formattedContent = formattedContent.replace(/\*([^*]+)\*/g, '<em>$1</em>');

            // Convert URLs to links
            formattedContent = formattedContent.replace(
                /(https?:\/\/[^\s]+)/g,
                '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
            );

            // Convert line breaks to <br> tags
            formattedContent = formattedContent.replace(/\n/g, '<br>');

            // Set the HTML content
            messageContent.innerHTML = formattedContent;

            // Add timestamp if provided
            if (timestamp) {
                const timestampDiv = document.createElement('div');
                timestampDiv.className = 'message-timestamp';

                // Format timestamp
                const date = new Date(timestamp);
                const formattedDate = date.toLocaleString('fr-FR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    day: '2-digit',
                    month: '2-digit',
                    year: 'numeric'
                });

                timestampDiv.textContent = formattedDate;
                messageContent.appendChild(timestampDiv);
            }

            messageDiv.appendChild(messageContent);

            // Add to chat window
            this.chatMessages.appendChild(messageDiv);

            // Scroll to the latest message
            this.scrollToBottom();

            return messageDiv;
        } catch (error) {
            console.error('Error adding message:', error);
        }
    }

    showThinkingIndicator() {
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'thinking';
        thinkingDiv.id = 'thinkingIndicator';

        const dots = document.createElement('div');
        dots.className = 'spinner-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';

        const text = document.createElement('div');
        text.className = 'thinking-text';
        text.textContent = 'Wizzy réfléchit...';

        thinkingDiv.appendChild(dots);
        thinkingDiv.appendChild(text);

        this.chatMessages.appendChild(thinkingDiv);
        this.scrollToBottom();
    }

    removeThinkingIndicator() {
        const thinkingDiv = this.chatMessages.querySelector('.thinking');
        if (thinkingDiv) {
            thinkingDiv.remove();
        }
    }

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message system-message error';
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        this.chatMessages.appendChild(errorDiv);
        this.scrollToBottom();

        // Remove error message after 5 seconds
        setTimeout(() => {
            errorDiv.classList.add('fade-out');
            setTimeout(() => errorDiv.remove(), 300);
        }, 5000);
    }

    async loadChatHistory() {
        try {
            if (!this.chatId) {
                console.warn('No chat ID available, cannot load history');
                return;
            }

            // Clear existing messages
            this.chatMessages.innerHTML = '';

            console.log(`Loading chat history for chat ID: ${this.chatId}`);
            this.showLoading();

            try {
                // Use specific endpoint for chat history
                const historyUrl = `/api/chat/history/${this.chatId}/`;
                console.log(`Requesting chat history from: ${historyUrl}`);

                const response = await AuthManager.fetchWithAuth(historyUrl);

                if (!response.ok) {
                    console.error(`HTTP error loading history: ${response.status}`);
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                console.log('Chat history response data:', data);

                this.hideLoading();

                if (data.success && data.messages && data.messages.length > 0) {
                    console.log(`Loaded ${data.messages.length} messages from history`);

                    // Sort messages by timestamp if available
                    if (data.messages[0].created_at) {
                        data.messages.sort((a, b) => {
                            return new Date(a.created_at) - new Date(b.created_at);
                        });
                    }

                    // Render the messages
                    this.renderMessages(data.messages);

                    // Look for structure elements in the rendered messages
                    const structureElements = this.chatMessages.querySelectorAll('[data-structure]');
                    console.log(`Found ${structureElements.length} structure elements in the chat`);

                    // Process any structures in the history after small delay to ensure DOM is updated
                    setTimeout(() => {
                        this.renderHistoryStructures();
                    }, 300);

                    // Scroll to bottom
                    this.scrollToBottom();
                } else {
                    console.log('No chat history available or empty history');

                    // If no messages, show welcome message
                    const welcomeMsg = 'Bonjour! Je suis Wizzy, votre assistant IA pour la génération de leads et le scraping. Comment puis-je vous aider aujourd\'hui?';
                    this.addMessage(welcomeMsg, 'ai');
                }
            } catch (error) {
                this.hideLoading();
                console.error('Error loading chat history:', error);
                this.showError(`Erreur lors du chargement de l'historique: ${error.message}`);

                // Show a welcome message as fallback
                const welcomeMsg = 'Désolé, je n\'ai pas pu charger votre historique de chat. Comment puis-je vous aider aujourd\'hui?';
                this.addMessage(welcomeMsg, 'ai');
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error in loadChatHistory:', error);
        }
    }

    async loadMoreMessages() {
        try {
            this.showLoading();
            const response = await AuthManager.fetchWithAuth(`/api/chat/history/?offset=${this.messageOffset}&limit=${this.messageLimit}`);
            const data = await response.json();

            if (data.messages && data.messages.length > 0) {
                // Update offset based on the number of messages received
                this.messageOffset += data.messages.length;

                // If we received less messages than the limit, hide the load more button
                if (data.messages.length < this.messageLimit) {
                    this.loadMoreBtn.style.display = 'none';
                }

                // Render messages at the beginning in chronological order
                this.renderMessages(data.messages, true);
            } else {
                // No more messages to load
                this.loadMoreBtn.style.display = 'none';
            }

            this.hideLoading();
        } catch (error) {
            console.error('Error loading more messages:', error);
            this.showError('Failed to load more messages');
        }
    }

    async clearChat() {
        try {
            const response = await AuthManager.fetchWithAuth('/api/chat/clear/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });

            if (response.ok) {
                this.chatMessages.innerHTML = '';
                this.messageOffset = 0;
                this.loadMoreBtn.style.display = 'block';

                // Add welcome message
                this.addMessage('Bonjour ! Je suis Wizzy, votre assistant IA. Comment puis-je vous aider aujourd\'hui ?', 'ai');
            }
        } catch (error) {
            console.error('Error clearing chat:', error);
            this.showError('Failed to clear chat history');
        }
    }

    showLoading() {
        if (!this.loadingIndicator) {
            this.loadingIndicator = document.createElement('div');
            this.loadingIndicator.className = 'chat-loading-indicator';
            this.loadingIndicator.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Chargement...</span></div>';
            document.body.appendChild(this.loadingIndicator);
        }
        this.loadingIndicator.style.display = 'flex';
    }

    hideLoading() {
        if (this.loadingIndicator) {
            this.loadingIndicator.style.display = 'none';
        }
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    autoResizeTextarea() {
        this.userInput.style.height = 'auto';
        this.userInput.style.height = this.userInput.scrollHeight + 'px';
    }

    getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            return csrfInput.value;
        }

        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            return csrfMeta.getAttribute('content');
        }

        return ''; // Return empty string if token not found
    }

    getActionIcon(type) {
        const icons = {
            'scraping': 'fa-robot',
            'analysis': 'fa-chart-bar',
            'search': 'fa-search',
            'processing': 'fa-cogs',
            'notification': 'fa-bell'
        };
        return icons[type] || 'fa-info-circle';
    }

    getStatusIcon(status) {
        const icons = {
            'success': 'fa-check-circle',
            'error': 'fa-times-circle',
            'pending': 'fa-clock',
            'processing': 'fa-spinner fa-spin'
        };
        return icons[status] || 'fa-info-circle';
    }

    toggleChat() {
        this.isOpen = !this.isOpen;
        this.chatWindow.style.display = this.isOpen ? 'flex' : 'none';
        this.chatButton.style.display = this.isOpen ? 'none' : 'flex';

        if (this.isOpen) {
            // Ensure chat is scrolled to bottom when opened
            setTimeout(() => {
                this.scrollToBottom();
            }, 100);
        }
    }

    initializeStructureModal() {
        // Create modal HTML
        const modalHTML = `
            <div id="structureModal" class="modal fade" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Détails de la structure</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="structure-info">
                                <div class="mb-3">
                                    <label class="form-label">Nom de la structure</label>
                                    <input type="text" class="form-control" id="structureName">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Type d'entité</label>
                                    <select class="form-select" id="structureType">
                                        <option value="mairie">Mairie</option>
                                        <option value="entreprise">Entreprise</option>
                                        <option value="b2b_lead">B2B Lead</option>
                                        <option value="custom">Structure personnalisée</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Stratégie de scraping</label>
                                    <select class="form-select" id="scrapingStrategy">
                                        <option value="web_scraping">Web Scraping</option>
                                        <option value="api_scraping">API Scraping</option>
                                        <option value="custom_scraping">Scraping personnalisé</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Leads cibles par jour</label>
                                    <input type="number" class="form-control" id="leadsTarget" min="1" max="1000">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Structure des données</label>
                                    <div id="structureFields" class="structure-fields">
                                        <!-- Fields will be dynamically added here -->
                                    </div>
                                    <button type="button" class="btn btn-sm btn-outline-primary mt-2" id="addFieldBtn">
                                        <i class="fas fa-plus"></i> Ajouter un champ
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                            <button type="button" class="btn btn-primary" id="saveStructureBtn">Enregistrer</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Only initialize bootstrap modal if bootstrap is loaded
        try {
            if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
                this.structureModal = new bootstrap.Modal(document.getElementById('structureModal'));
                // Initialize modal event listeners
                this.initializeModalEventListeners();
            } else {
                console.warn('Bootstrap Modal not available, structure modal functionality will be limited');
            }
        } catch (error) {
            console.error('Error initializing bootstrap modal:', error);
        }
    }

    initializeModalEventListeners() {
        const modal = document.getElementById('structureModal');
        const addFieldBtn = modal.querySelector('#addFieldBtn');
        const saveStructureBtn = modal.querySelector('#saveStructureBtn');
        const structureFields = modal.querySelector('#structureFields');

        addFieldBtn.addEventListener('click', () => this.addStructureField());
        saveStructureBtn.addEventListener('click', () => this.saveStructure());
    }

    addStructureField() {
        const fieldHTML = `
            <div class="structure-field mb-2">
                <div class="input-group">
                    <input type="text" class="form-control" placeholder="Nom du champ" name="fieldName">
                    <select class="form-select" name="fieldType">
                        <option value="text">Texte</option>
                        <option value="email">Email</option>
                        <option value="phone">Téléphone</option>
                        <option value="url">URL</option>
                        <option value="number">Nombre</option>
                    </select>
                    <button type="button" class="btn btn-outline-danger" onclick="this.closest('.structure-field').remove()">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
        document.getElementById('structureFields').insertAdjacentHTML('beforeend', fieldHTML);
    }

    async saveStructure() {
        const modal = document.getElementById('structureModal');
        const structureData = {
            name: modal.querySelector('#structureName').value,
            entity_type: modal.querySelector('#structureType').value,
            scraping_strategy: modal.querySelector('#scrapingStrategy').value,
            leads_target_per_day: parseInt(modal.querySelector('#leadsTarget').value),
            structure: this.getStructureFields()
        };

        try {
            const response = await fetch('/api/scraping/structures/', {
                method: this.currentStructure ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(structureData)
            });

            if (response.ok) {
                this.structureModal.hide();
                this.showSuccess('Structure sauvegardée avec succès');
                // Add confirmation message to chat
                this.addMessage(`Structure "${structureData.name}" sauvegardée avec succès.`, 'ai');
            } else {
                const error = await response.json();
                this.showError(error.message || 'Erreur lors de la sauvegarde de la structure');
            }
        } catch (error) {
            console.error('Error saving structure:', error);
            this.showError('Une erreur est survenue lors de la sauvegarde de la structure');
        }
    }

    getStructureFields() {
        const fields = [];
        document.querySelectorAll('.structure-field').forEach(field => {
            fields.push({
                name: field.querySelector('[name="fieldName"]').value,
                type: field.querySelector('[name="fieldType"]').value
            });
        });
        return fields;
    }

    getEntityTypeIcon(entityType) {
        const icons = {
            'mairie': 'fa-building-government',
            'entreprise': 'fa-building',
            'b2b_lead': 'fa-handshake',
            'custom': 'fa-gear',
            'company': 'fa-building',
            'person': 'fa-user',
            'product': 'fa-box',
            'service': 'fa-cogs',
            'job': 'fa-briefcase',
            'event': 'fa-calendar-alt',
            'article': 'fa-newspaper',
            'property': 'fa-home'
        };
        return icons[entityType?.toLowerCase()] || 'fa-question-circle';
    }

    showStructureDetails(structureData) {
        console.log('Showing structure details:', structureData);
        if (!structureData) {
            console.error('Invalid structure data received');
            return;
        }

        try {
            // Make sure the modal exists
            const modal = this.createStructureModal();
            const form = modal.querySelector('#structureForm');

            if (!form) {
                console.error('Structure form not found in modal');
                return;
            }

            // Clear existing fields
            form.innerHTML = '';

            // Add fields for basic structure data
            this.addFormField(form, 'name', 'Nom de la structure', structureData.name || '', 'text');

            // Normalize entity_type if needed
            let entityType = structureData.entity_type || '';
            if (entityType === 'b2b_company') {
                entityType = 'entreprise';
            }

            this.addFormField(form, 'entity_type', 'Type d\'entité', entityType, 'select', [
                { value: 'mairie', label: 'Mairie' },
                { value: 'entreprise', label: 'Entreprise' },
                { value: 'b2b_lead', label: 'Lead B2B' },
                { value: 'custom', label: 'Structure personnalisée' }
            ]);

            this.addFormField(form, 'scraping_strategy', 'Stratégie de scraping', structureData.scraping_strategy || '', 'select', [
                { value: 'web_scraping', label: 'Web Scraping' },
                { value: 'api_scraping', label: 'API Scraping' },
                { value: 'serp_scraping', label: 'Scraping SERP' },
                { value: 'social_scraping', label: 'Scraping Réseaux Sociaux' },
                { value: 'custom_scraping', label: 'Scraping personnalisé' }
            ]);

            this.addFormField(form, 'leads_target_per_day', 'Objectif de leads par jour', structureData.leads_target_per_day || '10', 'number');

            // Add section for structure fields
            const fieldsetStructure = document.createElement('fieldset');
            fieldsetStructure.className = 'mt-4 border p-3';
            fieldsetStructure.innerHTML = '<legend class="w-auto px-2 fs-5">Champs de données</legend>';

            const fieldsContainer = document.createElement('div');
            fieldsContainer.id = 'structureFieldsContainer';
            fieldsetStructure.appendChild(fieldsContainer);

            // Add button to add new field
            const addButton = document.createElement('button');
            addButton.type = 'button';
            addButton.className = 'btn btn-sm btn-outline-success mt-2';
            addButton.innerHTML = '<i class="fas fa-plus"></i> Ajouter un champ';
            addButton.addEventListener('click', () => this.addStructureField(fieldsContainer));
            fieldsetStructure.appendChild(addButton);

            form.appendChild(fieldsetStructure);

            // Add existing structure fields
            if (structureData.structure && Array.isArray(structureData.structure)) {
                structureData.structure.forEach(field => {
                    this.addStructureField(fieldsContainer, field);
                });
            }

            // Handle save button
            const saveButton = modal.querySelector('#saveStructureBtn');
            if (saveButton) {
                // Remove existing event listeners
                const newSaveButton = saveButton.cloneNode(true);
                saveButton.parentNode.replaceChild(newSaveButton, saveButton);

                // Add new event listener
                newSaveButton.addEventListener('click', () => {
                    const updatedStructure = this.saveStructureFromForm(form);
                    console.log('Saving structure:', updatedStructure);
                    this.saveStructureUpdate(updatedStructure);

                    // Close the modal
                    if (typeof bootstrap !== 'undefined') {
                        const modalInstance = bootstrap.Modal.getInstance(modal);
                        if (modalInstance) {
                            modalInstance.hide();
                        }
                    }
                });
            }

            // Show the modal
            try {
                if (typeof bootstrap !== 'undefined') {
                    const modalInstance = new bootstrap.Modal(modal);
                    modalInstance.show();
                } else {
                    console.error('Bootstrap is not available');
                    alert('Erreur: Bootstrap n\'est pas disponible. Impossible d\'afficher le modal.');
                }
            } catch (error) {
                console.error('Error showing modal:', error);
                alert('Erreur lors de l\'ouverture du modal. Consultez la console pour voir les détails de la structure.');
            }
        } catch (error) {
            console.error('Error in showStructureDetails:', error);
            alert('Erreur lors de l\'affichage des détails de la structure: ' + error.message);
        }
    }

    async saveStructureUpdate(structureData) {
        try {
            console.log('Saving structure update:', structureData);

            // Show loading indicator
            this.showLoading();

            // Use AuthManager for authenticated request
            const response = await AuthManager.fetchWithAuth('/api/chat/update-structure/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ structure: structureData })
            });

            // Hide loading indicator
            this.hideLoading();

            if (!response.ok) {
                throw new Error('Erreur lors de la sauvegarde de la structure');
            }

            const data = await response.json();
            console.log('Structure update response:', data);

            if (data.success) {
                this.showSuccess('Structure de scraping sauvegardée avec succès');

                // Add confirmation message to chat
                this.addMessage(`Structure "${structureData.name}" sauvegardée avec succès.`, 'ai');

                // Ask user if they want to be redirected to the structures tab
                if (confirm('Structure enregistrée. Voulez-vous accéder à la section Structures du tableau de bord?')) {
                    // Redirect to the structures tab
                    window.location.href = '/dashboard/#structures';
                }
            } else {
                throw new Error(data.message || 'Erreur lors de la sauvegarde de la structure');
            }
        } catch (error) {
            // Hide loading indicator
            this.hideLoading();

            console.error('Error saving structure:', error);
            this.showError('Erreur lors de la sauvegarde de la structure: ' + error.message);
        }
    }

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'message system-message success';
        successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
        this.chatMessages.appendChild(successDiv);
        this.scrollToBottom();

        setTimeout(() => {
            successDiv.classList.add('fade-out');
            setTimeout(() => successDiv.remove(), 300);
        }, 5000);
    }

    renderMessages(messages, prepend = false) {
        if (!messages || !Array.isArray(messages) || messages.length === 0) {
            return;
        }

        console.log(`Rendering ${messages.length} messages`);

        // If not prepending and it's the first load, clear the container
        if (!prepend && this.chatMessages.childElementCount === 0) {
            this.chatMessages.innerHTML = '';
        }

        // If prepending, we need to maintain scroll position
        const scrollPosition = this.chatMessages.scrollTop;
        const oldHeight = this.chatMessages.scrollHeight;

        // Add messages in chronological order
        messages.forEach(message => {
            try {
                if (message.is_user) {
                    // User message
                    this.addMessage(message.message, 'user', message.created_at);
                } else if (message.is_system) {
                    // System message
                    this.displayMessage('Système', message.message, 'system');
                } else if (message.is_action && message.action_type) {
                    // Action message
                    console.log('Processing action from history:', message.action_type);

                    const actionData = {
                        type: message.action_type,
                        status: message.status || 'success',
                        parameters: message.parameters || {},
                        created_at: message.created_at
                    };

                    if (message.action_result) {
                        actionData.result = message.action_result;
                    }

                    this.handleAIActions(actionData);
                } else if (message.structure) {
                    // Structure message with both response and structure
                    console.log('Processing structure from history:', message.structure);

                    // Add AI message first if available
                    if (message.response) {
                        this.addMessage(message.response, 'ai', message.created_at);
                    }

                    try {
                        // Convert string to object if needed
                        let structureData = message.structure;
                        if (typeof structureData === 'string') {
                            structureData = JSON.parse(structureData);
                        }

                        // Then handle the structure
                        this.handleStructureUpdate(structureData);
                    } catch (structureError) {
                        console.error('Error processing structure from history:', structureError);
                    }
                } else {
                    // AI message
                    this.addMessage(message.response || message.message, 'ai', message.created_at);
                }
            } catch (error) {
                console.error('Error rendering message:', error, message);
            }
        });

        // Restore scroll position if prepending
        if (prepend && this.chatMessages.scrollHeight > oldHeight) {
            const newScrollTop = this.chatMessages.scrollHeight - oldHeight + scrollPosition;
            this.chatMessages.scrollTop = newScrollTop;
        } else {
            // Scroll to bottom for new messages (if user was already at bottom)
            this.scrollToBottom();
        }
    }

    getEntityTypeName(type) {
        const types = {
            'mairie': 'Mairie',
            'entreprise': 'Entreprise',
            'b2b_lead': 'Lead B2B',
            'custom': 'Structure personnalisée',
            'company': 'Entreprise',
            'person': 'Personne',
            'event': 'Événement',
            'product': 'Produit'
        };
        return types[type] || type;
    }

    getStrategyName(strategy) {
        const strategies = {
            'web_scraping': 'Web Scraping',
            'api_scraping': 'API Scraping',
            'custom_scraping': 'Scraping personnalisé',
            'serp_scraping': 'Scraping de Résultats de Recherche',
            'social_scraping': 'Scraping de Réseaux Sociaux'
        };
        return strategies[strategy] || strategy;
    }

    getStrategyDescription(strategy) {
        const descriptions = {
            'web_scraping': 'Extraction de données directement depuis les sites web des mairies',
            'api_scraping': 'Utilisation d\'APIs officielles pour récupérer les données',
            'custom_scraping': 'Approche personnalisée combinant plusieurs méthodes',
            'serp_scraping': 'Extraction depuis les résultats de moteurs de recherche',
            'social_scraping': 'Collecte de données depuis les réseaux sociaux'
        };
        return descriptions[strategy] || 'Méthode d\'extraction de données';
    }

    getFieldTypeIcon(type) {
        const icons = {
            'text': 'fa-font',
            'email': 'fa-envelope',
            'phone': 'fa-phone',
            'url': 'fa-link',
            'number': 'fa-hashtag',
            'date': 'fa-calendar-alt'
        };
        return icons[type] || 'fa-question';
    }

    getFieldTypeDescription(type) {
        const descriptions = {
            'text': 'Texte',
            'email': 'Adresse email',
            'phone': 'Numéro de téléphone',
            'url': 'Adresse web (URL)',
            'number': 'Valeur numérique',
            'date': 'Date'
        };
        return descriptions[type] || type;
    }

    showNotification(title, message) {
        // Create a simple notification
        const notification = document.createElement('div');
        notification.className = 'chat-notification';
        notification.innerHTML = `
            <div class="notification-title">${title}</div>
            <div class="notification-message">${message}</div>
        `;

        // Add to DOM
        document.body.appendChild(notification);

        // Show with animation
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // Remove after a delay
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 5000);
    }

    // Helper method to create form fields
    addFormField(form, name, label, value, type, options = null) {
        const formGroup = document.createElement('div');
        formGroup.className = 'mb-3';

        const labelEl = document.createElement('label');
        labelEl.htmlFor = name;
        labelEl.className = 'form-label';
        labelEl.textContent = label;
        formGroup.appendChild(labelEl);

        if (type === 'select' && options) {
            const select = document.createElement('select');
            select.className = 'form-select';
            select.id = name;
            select.name = name;

            options.forEach(option => {
                const optionEl = document.createElement('option');
                optionEl.value = option.value;
                optionEl.textContent = option.label;
                if (option.value === value) {
                    optionEl.selected = true;
                }
                select.appendChild(optionEl);
            });

            formGroup.appendChild(select);
        } else {
            const input = document.createElement('input');
            input.type = type;
            input.className = 'form-control';
            input.id = name;
            input.name = name;
            input.value = value;
            formGroup.appendChild(input);
        }

        form.appendChild(formGroup);
    }

    // Method to add a structure field row to the form
    addStructureField(container, field = null) {
        try {
            const fieldRow = document.createElement('div');
            fieldRow.className = 'structure-field-row mb-2 d-flex align-items-center';

            // Field name input
            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.className = 'form-control me-2';
            nameInput.name = 'fieldName';
            nameInput.placeholder = 'Nom du champ';
            nameInput.value = field?.name || '';

            // Field type select
            const typeSelect = document.createElement('select');
            typeSelect.className = 'form-select me-2';
            typeSelect.name = 'fieldType';

            const fieldTypes = [
                { value: 'text', label: 'Texte' },
                { value: 'email', label: 'Email' },
                { value: 'phone', label: 'Téléphone' },
                { value: 'url', label: 'URL' },
                { value: 'number', label: 'Nombre' },
                { value: 'date', label: 'Date' }
            ];

            fieldTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.value;
                option.textContent = type.label;
                if (field?.type === type.value) {
                    option.selected = true;
                }
                typeSelect.appendChild(option);
            });

            // Required checkbox
            const requiredDiv = document.createElement('div');
            requiredDiv.className = 'form-check ms-2 me-2';

            const requiredCheck = document.createElement('input');
            requiredCheck.type = 'checkbox';
            requiredCheck.className = 'form-check-input';
            requiredCheck.name = 'fieldRequired';
            requiredCheck.id = `required-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
            requiredCheck.checked = field?.required || false;

            const requiredLabel = document.createElement('label');
            requiredLabel.className = 'form-check-label';
            requiredLabel.htmlFor = requiredCheck.id;
            requiredLabel.textContent = 'Requis';

            requiredDiv.appendChild(requiredCheck);
            requiredDiv.appendChild(requiredLabel);

            // Delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn btn-sm btn-danger ms-auto';
            deleteBtn.innerHTML = '<i class="fas fa-trash"></i>';
            deleteBtn.addEventListener('click', () => {
                fieldRow.remove();
            });

            // Assemble the row
            fieldRow.appendChild(nameInput);
            fieldRow.appendChild(typeSelect);
            fieldRow.appendChild(requiredDiv);
            fieldRow.appendChild(deleteBtn);

            // Add to container
            container.appendChild(fieldRow);
        } catch (error) {
            console.error('Error adding structure field:', error);
        }
    }

    // Method to create the structure modal if it doesn't exist
    createStructureModal() {
        // Check if modal already exists
        let modal = document.getElementById('structureModal');
        if (modal) {
            return modal;
        }

        // Create modal element
        modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'structureModal';
        modal.tabIndex = '-1';
        modal.setAttribute('aria-labelledby', 'structureModalLabel');
        modal.setAttribute('aria-hidden', 'true');

        // Create modal content
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="structureModalLabel">Détails de la structure</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <form id="structureForm">
                            <!-- Form fields will be added dynamically -->
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                        <button type="button" class="btn btn-primary" id="saveStructureBtn">Enregistrer</button>
                    </div>
                </div>
            </div>
        `;

        // Add to body
        document.body.appendChild(modal);

        return modal;
    }

    // Method to save structure data from form
    saveStructureFromForm(form) {
        const structure = {
            name: form.querySelector('[name="name"]').value,
            entity_type: form.querySelector('[name="entity_type"]').value,
            scraping_strategy: form.querySelector('[name="scraping_strategy"]').value,
            leads_target_per_day: form.querySelector('[name="leads_target_per_day"]').value,
            structure: []
        };

        // Get all structure fields
        const fieldRows = form.querySelectorAll('.structure-field-row');
        fieldRows.forEach(row => {
            const fieldName = row.querySelector('[name="fieldName"]').value;
            if (fieldName.trim()) {
                structure.structure.push({
                    name: fieldName,
                    type: row.querySelector('[name="fieldType"]').value,
                    required: row.querySelector('[name="fieldRequired"]').checked
                });
            }
        });

        return structure;
    }

    // Add displayMessage method to handle system messages
    displayMessage(sender, content, type) {
        // Types: system, success, error, warning, info
        const messageClass = type ? `system-message ${type}` : 'system-message';
        const iconClass = {
            'system': 'fa-info-circle',
            'success': 'fa-check-circle',
            'error': 'fa-exclamation-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle'
        }[type] || 'fa-info-circle';

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${messageClass}`;
        messageDiv.innerHTML = `<i class="fas ${iconClass}"></i> ${content}`;

        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();

        // Remove message after 5 seconds for some types
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                messageDiv.classList.add('fade-out');
                setTimeout(() => messageDiv.remove(), 300);
            }, 5000);
        }
    }

    handleStructureUpdate(structureData) {
        try {
            console.log('Handling structure update:', structureData);

            // Ensure structure data has required fields or set defaults
            if (!structureData) {
                console.error('Structure data is undefined or null');
                return;
            }

            // Apply defaults for missing fields
            structureData = {
                name: structureData.name || 'Structure de scraping',
                entity_type: structureData.entity_type || 'mairie',
                scraping_strategy: structureData.scraping_strategy || 'web_scraping',
                leads_target_per_day: structureData.leads_target_per_day || 10,
                structure: structureData.structure || [],
                ...structureData
            };

            // Create a structure update notification
            const updateBlock = document.createElement('div');
            updateBlock.className = 'structure-update-block';
            updateBlock.style.padding = '15px';
            updateBlock.style.border = '1px solid #4CAF50';
            updateBlock.style.borderRadius = '8px';
            updateBlock.style.marginBottom = '15px';
            updateBlock.style.backgroundColor = '#f9fff9';

            // Store the structure data as a data attribute for future reference
            updateBlock.dataset.structure = JSON.stringify(structureData);

            const header = document.createElement('div');
            header.className = 'structure-header';
            header.style.fontWeight = 'bold';
            header.style.fontSize = '16px';
            header.style.marginBottom = '10px';
            header.innerHTML = `<i class="fas fa-sitemap"></i> Structure de scraping détectée`;

            const content = document.createElement('div');
            content.className = 'structure-content';

            // Create a preview of the structure data with enhanced styling
            let previewHTML = '<div class="structure-info" style="margin-bottom: 15px;">';

            // Add entity type with icon
            const entityIcon = this.getEntityTypeIcon(structureData.entity_type);
            previewHTML += `<div class="structure-field" style="margin-bottom: 8px;"><i class="fas ${entityIcon}"></i> <strong>Type d'entité:</strong> ${this.getEntityTypeName(structureData.entity_type)}</div>`;

            // Add name
            previewHTML += `<div class="structure-field" style="margin-bottom: 8px;"><i class="fas fa-tag"></i> <strong>Nom:</strong> ${structureData.name || 'Non spécifié'}</div>`;

            // Add strategy with detailed explanation
            previewHTML += `<div class="structure-field" style="margin-bottom: 8px;"><i class="fas fa-robot"></i> <strong>Stratégie:</strong> ${this.getStrategyName(structureData.scraping_strategy)}</div>`;
            previewHTML += `<div class="structure-field-detail" style="margin-left: 25px; margin-bottom: 8px; font-size: 0.9em; color: #666;">${this.getStrategyDescription(structureData.scraping_strategy)}</div>`;

            // Add target with explanation
            previewHTML += `<div class="structure-field" style="margin-bottom: 8px;"><i class="fas fa-bullseye"></i> <strong>Objectif:</strong> ${structureData.leads_target_per_day || 'Non spécifié'} leads/jour</div>`;

            // Add fields with detailed information
            if (structureData.structure && Array.isArray(structureData.structure)) {
                previewHTML += `<div class="structure-field" style="margin-bottom: 8px;"><i class="fas fa-list"></i> <strong>Champs à collecter (${structureData.structure.length}):</strong></div>`;

                // Add a collapsible list of fields with types
                previewHTML += `<div class="structure-fields-list" style="margin-left: 25px; margin-bottom: 15px;">`;
                structureData.structure.forEach(field => {
                    const fieldTypeIcon = this.getFieldTypeIcon(field.type);
                    const isRequired = field.required ? '<span style="color: #ff0000;">*</span>' : '';
                    previewHTML += `
                        <div class="field-item" style="margin-bottom: 5px;">
                            <i class="fas ${fieldTypeIcon}"></i> 
                            <strong>${field.name}${isRequired}:</strong> 
                            <span style="color: #666;">${this.getFieldTypeDescription(field.type)}</span>
                        </div>`;
                });
                previewHTML += `</div>`;
            } else {
                previewHTML += `<div class="structure-field" style="margin-bottom: 8px; color: #E57373;"><i class="fas fa-exclamation-triangle"></i> <strong>Attention:</strong> Aucun champ défini dans cette structure</div>`;
            }

            // Add a description of the scraping opportunity
            let entityDescription = this.getEntityTypeName(structureData.entity_type).toLowerCase();
            let description = `Cette structure permettra de collecter des informations sur des ${entityDescription}`;

            if (structureData.name && structureData.name.includes('avec')) {
                // Try to extract context from the name if it contains "avec"
                const context = structureData.name.split('avec')[1].trim();
                description += ` avec ${context}`;
            } else {
                description += ` en utilisant la méthode de ${this.getStrategyName(structureData.scraping_strategy).toLowerCase()}`;
            }

            previewHTML += `<div class="structure-description" style="margin-top: 15px; padding: 10px; border-radius: 5px;">
                <i class="fas fa-info-circle"></i> 
                <strong>Description:</strong> 
                <p>${description}.</p>
            </div>`;

            previewHTML += '</div>';
            content.innerHTML = previewHTML;

            // Add action buttons
            const actions = document.createElement('div');
            actions.className = 'structure-actions mt-3';
            actions.style.display = 'flex';
            actions.style.gap = '10px';

            const viewButton = document.createElement('button');
            viewButton.className = 'btn btn-outline-primary';
            viewButton.innerHTML = '<i class="fas fa-eye"></i> Voir/Modifier';
            viewButton.addEventListener('click', () => this.showStructureDetails(structureData));

            const saveButton = document.createElement('button');
            saveButton.className = 'btn btn-success';
            saveButton.innerHTML = '<i class="fas fa-save"></i> Enregistrer';
            saveButton.addEventListener('click', () => this.saveStructureUpdate(structureData));

            actions.appendChild(viewButton);
            actions.appendChild(saveButton);

            // Assemble the block
            updateBlock.appendChild(header);
            updateBlock.appendChild(content);
            updateBlock.appendChild(actions);

            // Add to chat
            this.chatMessages.appendChild(updateBlock);
            this.scrollToBottom();

            // Add notification that this needs attention
            this.showNotification('Nouvelle structure de scraping détectée', 'Wizzy a détecté une structure de scraping. Cliquez pour voir les détails.');

            // Save the structure in session storage for recovery in case of page refresh
            try {
                const existingStructures = JSON.parse(sessionStorage.getItem('wizzy_structures') || '[]');
                existingStructures.push(structureData);
                sessionStorage.setItem('wizzy_structures', JSON.stringify(existingStructures));
            } catch (storageError) {
                console.warn('Could not save structure to session storage:', storageError);
            }

        } catch (error) {
            console.error('Error handling structure update:', error);
            this.showError('Erreur lors de l\'affichage de la structure de scraping');
        }
    }

    // Fallback method to show at least a minimal structure if the main one fails
    displayMinimalStructure(structureData) {
        console.log('Displaying minimal structure');

        if (!structureData || typeof structureData !== 'object') {
            console.error('Invalid structure data provided');
            return;
        }

        // Create a simple structure display
        const structureBlock = document.createElement('div');
        structureBlock.className = 'structure-fallback';
        structureBlock.style.padding = '15px';
        structureBlock.style.margin = '10px 0';
        structureBlock.style.border = '1px solid #4CAF50';
        structureBlock.style.borderRadius = '8px';
        structureBlock.style.backgroundColor = '#f9fff9';
        structureBlock.style.color = '#333';
        structureBlock.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';

        // Add header
        const header = document.createElement('div');
        header.style.fontWeight = 'bold';
        header.style.marginBottom = '10px';
        header.style.fontSize = '16px';
        header.style.color = '#2E7D32';
        header.innerHTML = '<i class="fas fa-sitemap"></i> Structure de scraping détectée';
        structureBlock.appendChild(header);

        // Add basic info
        const info = document.createElement('div');
        info.style.marginBottom = '10px';
        info.style.lineHeight = '1.6';

        // Get entity type icon
        const entityTypeIcon = this.getEntityTypeIcon ? this.getEntityTypeIcon(structureData.entity_type) : 'fa-building';

        info.innerHTML = `
            <div style="margin-bottom: 5px;"><i class="fas ${entityTypeIcon}"></i> <strong>Type d'entité:</strong> ${structureData.entity_type || 'Non spécifié'}</div>
            <div style="margin-bottom: 5px;"><i class="fas fa-tag"></i> <strong>Nom:</strong> ${structureData.name || 'Non spécifié'}</div>
            <div style="margin-bottom: 5px;"><i class="fas fa-robot"></i> <strong>Stratégie:</strong> ${structureData.scraping_strategy || 'Web scraping'}</div>
            <div style="margin-bottom: 5px;"><i class="fas fa-bullseye"></i> <strong>Objectif:</strong> ${structureData.leads_target_per_day || '10'} leads/jour</div>
        `;
        structureBlock.appendChild(info);

        // Add count of fields
        if (structureData.structure && Array.isArray(structureData.structure)) {
            const fieldsInfo = document.createElement('div');
            fieldsInfo.style.marginTop = '10px';
            fieldsInfo.style.marginBottom = '10px';
            fieldsInfo.innerHTML = `<div><i class="fas fa-list"></i> <strong>Champs à collecter (${structureData.structure.length}):</strong></div>`;

            // Create a small list of fields
            const fieldsList = document.createElement('div');
            fieldsList.style.marginLeft = '20px';
            fieldsList.style.marginTop = '5px';

            structureData.structure.forEach(field => {
                const fieldItem = document.createElement('div');
                fieldItem.style.marginBottom = '3px';
                fieldItem.style.fontSize = '0.9em';

                // If getFieldTypeIcon exists, use it, otherwise fallback to default
                const fieldIcon = this.getFieldTypeIcon ? this.getFieldTypeIcon(field.type) : 'fa-file-alt';
                const isRequired = field.required ? '<span style="color: #ff0000;">*</span>' : '';

                fieldItem.innerHTML = `
                    <i class="fas ${fieldIcon}"></i> 
                    <strong>${field.name}${isRequired}:</strong> 
                    <span style="color: #555;">${field.type}</span>
                `;
                fieldsList.appendChild(fieldItem);
            });

            fieldsInfo.appendChild(fieldsList);
            structureBlock.appendChild(fieldsInfo);
        }

        // Add a small description
        const description = document.createElement('div');
        description.style.marginTop = '10px';
        description.style.padding = '8px';
        description.style.backgroundColor = '#E8F5E9';
        description.style.borderRadius = '5px';
        description.style.fontSize = '0.9em';

        let entityDescription = structureData.entity_type ? structureData.entity_type.toLowerCase() : 'entités';
        description.innerHTML = `
            <i class="fas fa-info-circle"></i> 
            <strong>Description:</strong> 
            <span>Cette structure permettra de collecter des informations sur des ${entityDescription} en utilisant la méthode de web scraping.</span>
        `;
        structureBlock.appendChild(description);

        // Add action buttons
        const actions = document.createElement('div');
        actions.style.marginTop = '12px';
        actions.style.display = 'flex';
        actions.style.gap = '10px';

        const viewButton = document.createElement('button');
        viewButton.className = 'btn btn-sm btn-outline-primary';
        viewButton.innerHTML = '<i class="fas fa-eye"></i> Voir/Modifier';
        viewButton.addEventListener('click', () => this.showStructureDetails(structureData));

        const saveButton = document.createElement('button');
        saveButton.className = 'btn btn-sm btn-success';
        saveButton.innerHTML = '<i class="fas fa-save"></i> Enregistrer';
        saveButton.addEventListener('click', () => this.saveStructureUpdate(structureData));

        actions.appendChild(viewButton);
        actions.appendChild(saveButton);
        structureBlock.appendChild(actions);

        // Add to chat
        this.chatMessages.appendChild(structureBlock);
        this.scrollToBottom();
    }

    // Add CSS styles for loading indicator
    addCssStyles() {
        if (document.getElementById('wizzy-chat-styles')) {
            return; // Styles already added
        }

        const styleElement = document.createElement('style');
        styleElement.id = 'wizzy-chat-styles';
        styleElement.textContent = `
            .chat-loading-indicator {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(0, 0, 0, 0.4);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
            }
            
            .structure-update-block {
                animation: fadeIn 0.5s;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }
            
            #chatContainer {
                display: flex;
                flex-direction: column;
                height: 100%;
                width: 100%;
            }
            
            #chatMessages {
                flex: 1;
                overflow-y: auto;
                padding: 15px;
                height: calc(100% - 70px);
            }
            
            .chat-input-container {
                display: flex;
                padding: 10px;
                border-top: 1px solid #dee2e6;
                background: #f8f9fa;
            }
            
            #userInput {
                flex: 1;
                resize: none;
                min-height: 40px;
                max-height: 100px;
                padding: 8px 12px;
            }
            
            .chat-controls {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px;
                background: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            
            .chat-controls .btn-close {
                opacity: 0.7;
            }
            
            .chat-controls .btn-close:hover {
                opacity: 1;
            }
        `;
        document.head.appendChild(styleElement);
    }

    // Method to render structures in chat history
    renderHistoryStructures() {
        try {
            console.log('Rendering history structures...');

            // Find structure blocks in the current chat
            const structureBlocks = this.chatMessages.querySelectorAll('.structure-update-block');
            console.log(`Found ${structureBlocks.length} structure blocks in chat`);

            // Find elements with data-structure attribute
            const structureElements = this.chatMessages.querySelectorAll('[data-structure]');
            console.log(`Found ${structureElements.length} elements with data-structure attribute`);

            // Process all elements with structure data
            const allElements = [...structureBlocks, ...structureElements];

            allElements.forEach((element, index) => {
                try {
                    // Get structure data from data attribute
                    const structureData = element.dataset.structure;
                    if (!structureData) {
                        console.warn(`Element ${index} has no structure data`);
                        return;
                    }

                    // Parse structure data
                    const structureObj = this.parseStructureData(structureData);
                    if (!structureObj) {
                        console.warn(`Failed to parse structure data for element ${index}`);
                        return;
                    }

                    console.log(`Structure ${index} data:`, structureObj);

                    // Make sure the view and save buttons have proper event listeners
                    const viewButtons = element.querySelectorAll('.btn-outline-primary, .view-structure-btn');
                    const saveButtons = element.querySelectorAll('.btn-success, .save-structure-btn');

                    viewButtons.forEach(button => {
                        // Remove existing event listeners by cloning
                        const newButton = button.cloneNode(true);
                        button.parentNode.replaceChild(newButton, button);

                        // Add new event listener
                        newButton.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('View button clicked for structure', structureObj.name);
                            this.showStructureDetails(structureObj);
                        });
                    });

                    saveButtons.forEach(button => {
                        // Remove existing event listeners by cloning
                        const newButton = button.cloneNode(true);
                        button.parentNode.replaceChild(newButton, button);

                        // Add new event listener
                        newButton.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Save button clicked for structure', structureObj.name);
                            this.saveStructureUpdate(structureObj);
                        });
                    });

                    console.log(`Updated ${viewButtons.length} view buttons and ${saveButtons.length} save buttons`);
                } catch (error) {
                    console.error(`Error processing structure element ${index}:`, error);
                }
            });

            // Check for history UI elements
            const historyItems = document.querySelectorAll('.chat-history-item-structure');
            console.log(`Found ${historyItems.length} structure items in history UI`);

            historyItems.forEach((element, index) => {
                try {
                    // Get structure data
                    const structureData = element.dataset.structure;
                    if (!structureData) {
                        console.warn(`History item ${index} has no structure data`);
                        return;
                    }

                    // Parse structure data
                    const structureObj = this.parseStructureData(structureData);
                    if (!structureObj) {
                        console.warn(`Failed to parse structure data for history item ${index}`);
                        return;
                    }

                    console.log(`History structure ${index}:`, structureObj);

                    // Create a simplified structure preview
                    const preview = document.createElement('div');
                    preview.className = 'structure-preview p-2 border rounded mb-2';

                    const icon = this.getEntityTypeIcon(structureObj.entity_type);

                    // Create preview content
                    preview.innerHTML = `
                        <div class="d-flex align-items-center">
                            <i class="fas ${icon} me-2"></i>
                            <strong>${structureObj.name || 'Structure sans nom'}</strong>
                        </div>
                        <div class="text-muted small mt-1">
                            ${this.getEntityTypeName(structureObj.entity_type)} • 
                            ${this.getStrategyName(structureObj.scraping_strategy)} • 
                            ${structureObj.structure?.length || 0} champs
                        </div>
                        <div class="mt-2">
                            <button class="btn btn-sm btn-outline-primary view-structure-btn">
                                <i class="fas fa-eye"></i> Voir
                            </button>
                        </div>
                    `;

                    // Clear any existing content
                    element.innerHTML = '';
                    element.appendChild(preview);

                    // Add event listener to view button
                    const viewButton = preview.querySelector('.view-structure-btn');
                    if (viewButton) {
                        viewButton.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('History view button clicked for structure', structureObj.name);
                            this.showStructureDetails(structureObj);
                        });
                    }
                } catch (error) {
                    console.error(`Error rendering history structure ${index}:`, error);
                }
            });
        } catch (error) {
            console.error('Error in renderHistoryStructures:', error);
        }
    }

    // Helper method to parse structure data from various formats
    parseStructureData(data) {
        if (!data) return null;

        try {
            // If it's already an object, return it
            if (typeof data === 'object' && data !== null) {
                return data;
            }

            // If it's a string, try to parse as JSON
            if (typeof data === 'string') {
                return JSON.parse(data);
            }

            console.warn('Unknown structure data format:', data);
            return null;
        } catch (error) {
            console.error('Error parsing structure data:', error);
            return null;
        }
    }

    // Method to close the chat dialog box
    closeChat() {
        console.log('Executing closeChat method');

        // Approche agressive pour trouver le conteneur principal
        const findChatContainers = () => {
            return [
                // Sélecteurs principaux
                document.getElementById('chatContainer'),
                document.querySelector('.chat-container'),
                document.querySelector('.chat-wrapper'),
                document.querySelector('.chat-widget'),
                document.querySelector('.chat'),

                // Approche plus large en cherchant des attributs contenant "chat"
                document.querySelector('[id*="chat" i]'),
                document.querySelector('[class*="chat" i]'),

                // Chercher dans les ancêtres de boutons de fermeture
                ...(Array.from(document.querySelectorAll('#closeChat, .chat-close-btn, .btn-close'))
                    .map(btn => btn.closest('.chat, .chat-container, [id*="chat"], [class*="chat"]'))),

                // Chercher dans les éléments du DOM qui pourraient être des conteneurs de chat
                document.querySelector('.widget-container'),
                document.querySelector('.dialog'),
                document.querySelector('.modal:not(#structureModal)'),

                // Essayer de trouver via le contenu
                document.querySelector('div:has(#chatMessages)'),
                document.querySelector('div:has(.chat-messages)'),

                // Dernière tentative, recherche de tout élément qui contient un textarea et des boutons chat
                document.querySelector('div:has(textarea):has(button[id*="send" i])')
            ].filter(el => el != null);
        };

        const containers = findChatContainers();
        console.log(`Found ${containers.length} potential chat containers`, containers);

        let containerClosed = false;

        // Tenter de fermer chaque conteneur potentiel
        containers.forEach((container, index) => {
            try {
                console.log(`Attempting to hide container ${index}:`, container);

                // Vérifier si le conteneur est visible
                const style = window.getComputedStyle(container);
                if (style.display !== 'none') {
                    // Force le style à none avec !important
                    container.setAttribute('style', 'display: none !important');
                    containerClosed = true;
                    console.log(`Container ${index} hidden successfully`);
                }
            } catch (e) {
                console.error(`Error hiding container ${index}:`, e);
            }
        });

        // Si aucun conteneur n'a été fermé, essayer une approche plus agressive
        if (!containerClosed) {
            console.log('No containers closed with primary method, trying aggressive approach');

            // Essayer de trouver tout élément positionné en fixed/absolute qui pourrait être le chat
            const possibleFloatingElements = document.querySelectorAll('div[style*="position: fixed"], div[style*="position: absolute"]');
            console.log(`Found ${possibleFloatingElements.length} potential floating elements`);

            possibleFloatingElements.forEach((el, index) => {
                try {
                    // Vérifier si c'est probablement un élément de chat (contient des messages, textarea, boutons, etc.)
                    const containsTextarea = el.querySelector('textarea') !== null;
                    const containsMessages = el.querySelector('.message, #chatMessages, .chat-messages') !== null;
                    const containsSendButton = el.querySelector('button[id*="send" i], button[class*="send" i]') !== null;

                    if (containsTextarea || containsMessages || containsSendButton) {
                        console.log(`Found potential chat element ${index}:`, el);
                        el.setAttribute('style', el.getAttribute('style') + '; display: none !important;');
                        containerClosed = true;
                    }
                } catch (e) {
                    console.error(`Error checking floating element ${index}:`, e);
                }
            });
        }

        // Essayer une dernière approche désespérée si rien d'autre n'a fonctionné
        if (!containerClosed) {
            console.log('Trying last resort approach - hiding all potential chat-related elements');

            // 1. Cacher tous les éléments avec "chat" dans leur ID ou classe
            document.querySelectorAll('[id*="chat" i], [class*="chat" i]').forEach(el => {
                try {
                    // Ne pas cacher les boutons de toggle et les styles CSS !
                    if (el.id === 'toggleChat' || el.classList.contains('chat-toggle-btn') ||
                        el.id === 'wizzy-chat-styles' || el.tagName === 'STYLE') {
                        return;
                    }

                    // Cacher les autres éléments chat
                    console.log('Hiding chat element:', el);
                    el.setAttribute('style', 'display: none !important');
                } catch (e) {
                    console.error('Error hiding element:', e);
                }
            });

            // 2. Cacher le conteneur avec le contexte d'altitude Z le plus élevé qui contient "chat"
            const zIndexElements = Array.from(document.querySelectorAll('div[style*="z-index"]'))
                .filter(el => el.textContent.toLowerCase().includes('chat') ||
                    el.innerHTML.toLowerCase().includes('chat'));

            if (zIndexElements.length > 0) {
                try {
                    // Trouver l'élément avec le z-index le plus élevé
                    const topElement = zIndexElements.reduce((prev, curr) => {
                        const prevZ = parseInt(window.getComputedStyle(prev).zIndex) || 0;
                        const currZ = parseInt(window.getComputedStyle(curr).zIndex) || 0;
                        return prevZ > currZ ? prev : curr;
                    });

                    console.log('Hiding highest z-index chat element:', topElement);
                    topElement.setAttribute('style', 'display: none !important');
                    containerClosed = true;
                } catch (e) {
                    console.error('Error hiding z-index element:', e);
                }
            }
        }

        // Afficher le bouton de basculement
        const toggleButtons = [
            document.getElementById('toggleChat'),
            document.querySelector('.chat-toggle-btn'),
            document.querySelector('[id*="toggle" i][id*="chat" i]'),
            document.querySelector('[class*="toggle" i][class*="chat" i]')
        ].filter(el => el != null);

        console.log(`Found ${toggleButtons.length} potential toggle buttons`);

        // Afficher le premier bouton de basculement trouvé
        if (toggleButtons.length > 0) {
            toggleButtons[0].style.display = 'block';
            console.log('Toggle button displayed');
        } else {
            // Si aucun bouton de basculement n'est trouvé, essayer d'en créer un
            console.log('No toggle button found, attempting to create one');

            // Vérifier si un bouton de basculement existe déjà dans le DOM
            const existingToggle = document.querySelector('#toggleChat, .chat-toggle-btn, [id*="toggle" i][id*="chat" i]');

            if (!existingToggle) {
                try {
                    // Créer un nouveau bouton de basculement
                    const toggleBtn = document.createElement('button');
                    toggleBtn.id = 'toggleChat';
                    toggleBtn.className = 'chat-toggle-btn btn btn-primary';
                    toggleBtn.innerHTML = '<i class="fas fa-comments"></i> Chat';
                    toggleBtn.style.position = 'fixed';
                    toggleBtn.style.bottom = '20px';
                    toggleBtn.style.right = '20px';
                    toggleBtn.style.zIndex = '9999';
                    toggleBtn.style.borderRadius = '50%';
                    toggleBtn.style.width = '60px';
                    toggleBtn.style.height = '60px';
                    toggleBtn.style.boxShadow = '0 4px 8px rgba(0,0,0,0.2)';

                    // Ajouter un événement de clic utilisant reopenChat
                    toggleBtn.addEventListener('click', () => {
                        // D'abord, nettoyer tous les styles !important qui pourraient bloquer l'affichage
                        const elementsToClean = document.querySelectorAll('[style*="!important"]');
                        elementsToClean.forEach(el => {
                            // Vérifier si c'est un élément du chat (pas le toggle)
                            if (el.id !== 'toggleChat' && !el.classList.contains('chat-toggle-btn')) {
                                console.log('Removing style from element:', el);
                                el.removeAttribute('style');
                            }
                        });

                        // Réactiver les styles CSS
                        const styleElement = document.getElementById('wizzy-chat-styles');
                        if (styleElement) {
                            styleElement.removeAttribute('style');
                        }

                        // Application directe des styles au lieu d'utiliser le chatManager
                        const chatWindow = document.getElementById('chatWindow');
                        if (chatWindow) {
                            chatWindow.style.display = 'flex';
                            chatWindow.style.flexDirection = 'column';

                            const header = chatWindow.querySelector('.chat-header');
                            if (header) header.style.display = 'flex';

                            const messages = chatWindow.querySelector('#chatMessages');
                            if (messages) {
                                messages.style.display = 'flex';
                                messages.style.flex = '1';
                                messages.style.flexDirection = 'column';
                            }

                            const inputContainer = chatWindow.querySelector('.chat-input-container');
                            if (inputContainer) {
                                inputContainer.style.display = 'flex';

                                const input = inputContainer.querySelector('#userInput');
                                if (input) input.style.display = 'block';

                                const button = inputContainer.querySelector('#sendButton');
                                if (button) button.style.display = 'flex';
                            }

                            console.log('Chat styles directly applied');
                        } else {
                            // Si on ne trouve pas la fenêtre par ID, essayer par classe
                            console.log('ChatWindow not found by ID, trying generic selectors');

                            // Référence au chatManager
                            if (window.chatManager && typeof window.chatManager.reopenChat === 'function') {
                                window.chatManager.reopenChat();
                            } else {
                                // Fallback si chatManager n'est pas disponible
                                console.log('ChatManager not available, using fallback reopening method');

                                // Rechercher les éléments possibles du chat
                                const chatEls = document.querySelectorAll('[id*="chat" i]:not(#toggleChat), [class*="chat" i]:not(.chat-toggle-btn)');
                                chatEls.forEach(el => {
                                    // Utilisez flex pour les conteneurs principaux du chat
                                    if (el.id === 'chatWindow' || el.id === 'chatContainer' ||
                                        el.classList.contains('chat-window') || el.classList.contains('chat-container')) {
                                        el.style.display = 'flex';
                                        el.style.flexDirection = 'column';
                                    } else {
                                        el.style.display = 'block';
                                    }
                                });

                                // Restaurer spécifiquement les styles du conteneur d'input
                                const inputContainers = document.querySelectorAll('.chat-input-container');
                                inputContainers.forEach(container => {
                                    container.style.display = 'flex';
                                    container.style.padding = '10px';
                                    container.style.borderTop = '1px solid #dee2e6';
                                    container.style.background = '#f8f9fa';

                                    // Restaurer les styles de l'input textarea
                                    const textarea = container.querySelector('textarea');
                                    if (textarea) {
                                        textarea.style.display = 'block';
                                        textarea.style.flex = '1';
                                        textarea.style.resize = 'none';
                                        textarea.style.minHeight = '40px';
                                        textarea.style.maxHeight = '100px';
                                        textarea.style.padding = '8px 12px';
                                        textarea.style.border = '1px solid #ddd';
                                        textarea.style.borderRadius = '5px';
                                    }

                                    // Restaurer les styles du bouton d'envoi
                                    const sendButton = container.querySelector('button');
                                    if (sendButton) {
                                        sendButton.style.display = 'flex';
                                        sendButton.style.alignItems = 'center';
                                        sendButton.style.justifyContent = 'center';
                                        sendButton.style.marginLeft = '8px';
                                        sendButton.style.backgroundColor = '#007bff';
                                        sendButton.style.color = 'white';
                                        sendButton.style.border = 'none';
                                        sendButton.style.borderRadius = '5px';
                                        sendButton.style.padding = '8px 12px';
                                    }
                                });
                            }
                        }

                        // Forcer la visibilité après un court délai
                        setTimeout(() => {
                            const chatInput = document.querySelector('#userInput, .chat-input');
                            const sendButton = document.querySelector('#sendButton, .send-button');

                            if (chatInput) chatInput.style.display = 'block';
                            if (sendButton) sendButton.style.display = 'flex';
                        }, 100);

                        // Cacher le bouton toggle
                        toggleBtn.style.display = 'none';
                    });

                    // Ajouter au corps du document
                    document.body.appendChild(toggleBtn);
                    console.log('Created new toggle button');
                } catch (e) {
                    console.error('Error creating toggle button:', e);
                }
            }
        }

        return containerClosed;
    }

    // Method to force reinitialize chat UI elements
    reinitializeUI() {
        console.log('Manually reinitializing chat UI elements');

        // Try to find all relevant DOM elements
        const chatContainer = document.getElementById('chatContainer') || document.querySelector('.chat-container');
        const closeBtn = document.getElementById('closeChat') || document.querySelector('.chat-close-btn');
        const toggleBtn = document.getElementById('toggleChat') || document.querySelector('.chat-toggle-btn');

        console.log('Found elements:', {
            chatContainer: !!chatContainer,
            closeBtn: !!closeBtn,
            toggleBtn: !!toggleBtn
        });

        let newCloseBtn = null;
        let newToggleBtn = null;

        // Manually set up close button
        if (closeBtn) {
            console.log('Setting up close button manually');

            // Remove all existing event listeners
            newCloseBtn = closeBtn.cloneNode(true);
            if (closeBtn.parentNode) {
                closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
            }

            // Add new event listener
            newCloseBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Close button clicked (manual)');

                // Use dedicated method to close chat
                const closed = this.closeChat();
                console.log('Chat closed successfully:', closed);
            });
        } else {
            console.warn('Close button not found, trying fallback selector');
            // Try a more generic selector as fallback
            const genericCloseBtn = document.querySelector('.close, [aria-label="Close"], .btn-close, .close-btn');
            if (genericCloseBtn) {
                console.log('Found generic close button, attaching event listener');
                newCloseBtn = genericCloseBtn.cloneNode(true);
                if (genericCloseBtn.parentNode) {
                    genericCloseBtn.parentNode.replaceChild(newCloseBtn, genericCloseBtn);
                }

                newCloseBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    console.log('Generic close button clicked');

                    // Find closest modal or chat container
                    const container = genericCloseBtn.closest('.modal, .chat-container, #chatContainer');
                    if (container) {
                        container.style.display = 'none';
                        console.log('Container hidden via generic close button');
                    }

                    // Try to show toggle button
                    const altToggleBtn = document.querySelector('#toggleChat, .chat-toggle, .chat-toggle-btn');
                    if (altToggleBtn) {
                        altToggleBtn.style.display = 'block';
                    }
                });
            }
        }

        // Manually set up toggle button
        if (toggleBtn) {
            console.log('Setting up toggle button manually');

            // Remove all existing event listeners
            newToggleBtn = toggleBtn.cloneNode(true);
            if (toggleBtn.parentNode) {
                toggleBtn.parentNode.replaceChild(newToggleBtn, toggleBtn);
            }

            // Add new event listener using reopenChat
            newToggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('Toggle button clicked (manual)');

                // Utiliser la méthode dédiée pour réouvrir le chat
                this.reopenChat();
            });
        }

        // Debug element search for chat box
        console.log('Additional chat elements found:', {
            alternate: !!document.querySelector('.chat-widget, .chat-box, #chatbox'),
            byClass: !!document.querySelector('.chat'),
            byId: !!document.getElementById('chat')
        });

        // Reload history if available
        if (this.chatId) {
            console.log('Reloading chat history');
            this.loadChatHistory();
        }

        return {
            chatContainer,
            closeBtn: newCloseBtn,
            toggleBtn: newToggleBtn
        };
    }

    // Ajouter une nouvelle méthode pour réouvrir correctement le chat
    reopenChat() {
        console.log('Reopening chat with proper styling');

        // 0. Nettoyer les styles !important qui pourraient empêcher l'affichage
        this.cleanupImportantStyles();

        // 0.1 S'assurer que les styles CSS sont visibles
        const chatStyleSheet = document.getElementById('wizzy-chat-styles');
        if (chatStyleSheet) {
            console.log('Ensuring chat styles are visible');
            chatStyleSheet.style.display = '';  // Supprimer le style "display: none"
            chatStyleSheet.removeAttribute('style');  // Supprimer tous les attributs de style
        } else {
            console.log('Chat style sheet not found, recreating it');
            this.addCssStyles();  // Recréer les styles si nécessaire
        }

        // 1. Identifier tous les conteneurs potentiels
        const chatContainers = [
            document.getElementById('chatWindow'),
            document.getElementById('chatContainer'),
            document.querySelector('.chat-window'),
            document.querySelector('.chat-container')
        ].filter(el => el !== null);

        if (chatContainers.length === 0) {
            console.error('No chat containers found to reopen');
            return false;
        }

        console.log(`Found ${chatContainers.length} potential containers to reopen`);

        // 2. Restaurer chaque conteneur avec les styles corrects
        chatContainers.forEach(container => {
            // Assurer display: flex sur le conteneur principal
            container.style.display = 'flex';

            // Restaurer la structure flex-direction
            container.style.flexDirection = 'column';

            // Restaurer les éléments clés si présents
            const chatHeader = container.querySelector('.chat-header');
            if (chatHeader) {
                chatHeader.style.display = 'flex';
                chatHeader.style.justifyContent = 'space-between';
                chatHeader.style.alignItems = 'center';
            }

            const chatMessages = container.querySelector('#chatMessages, .chat-messages');
            if (chatMessages) {
                chatMessages.style.display = 'flex';
                chatMessages.style.flexDirection = 'column';
                chatMessages.style.flex = '1';
                chatMessages.style.overflowY = 'auto';
            }
        });

        // 3. Restaurer spécifiquement les styles de la zone d'input
        this.restoreChatInputStyles();

        // 4. Cacher le bouton toggle
        const toggleButtons = [
            document.getElementById('toggleChat'),
            document.querySelector('.chat-toggle-btn'),
            document.querySelector('[id*="toggle" i][id*="chat" i]')
        ].filter(el => el !== null);

        toggleButtons.forEach(button => {
            button.style.display = 'none';
        });

        // 5. Effectuer le scroll en bas pour voir les derniers messages
        this.scrollToBottom();

        // 6. Forcer la visibilité des éléments d'input après un court délai
        // Cela résout les problèmes de timing quand les styles ne sont pas immédiatement appliqués
        setTimeout(() => {
            this.restoreChatInputStyles();
        }, 100);

        return true;
    }

    // Ajouter une fonction qui restaure spécifiquement les styles pour la zone d'input
    restoreChatInputStyles() {
        console.log('Restoring chat input area styles');

        // Supprimer tout style !important qui pourrait persister
        const cleanupElements = document.querySelectorAll('[style*="!important"]');
        cleanupElements.forEach(el => {
            // Vérifier si c'est un élément de chat (sauf les boutons toggle)
            if ((el.id && el.id.toLowerCase().includes('chat') && el.id !== 'toggleChat') ||
                (el.className && el.className.toLowerCase().includes('chat') && !el.classList.contains('chat-toggle-btn'))) {
                console.log('Removing !important style from:', el);
                // Supprimer l'attribut style pour permettre aux styles CSS normaux de s'appliquer
                el.removeAttribute('style');
            }
        });

        // Trouver tous les conteneurs d'input potentiels
        const inputContainers = document.querySelectorAll('.chat-input-container');
        if (inputContainers.length === 0) {
            console.warn('No chat input containers found');
            return;
        }

        inputContainers.forEach((container, index) => {
            console.log(`Restoring styles for input container ${index}`);

            // Restaurer les styles du conteneur
            container.style.display = 'flex';
            container.style.padding = '10px';
            container.style.borderTop = '1px solid #dee2e6';
            container.style.background = '#f8f9fa';

            // Restaurer les styles de l'input textarea
            const textarea = container.querySelector('textarea');
            if (textarea) {
                textarea.style.display = 'block';
                textarea.style.flex = '1';
                textarea.style.resize = 'none';
                textarea.style.minHeight = '40px';
                textarea.style.maxHeight = '100px';
                textarea.style.padding = '8px 12px';
                textarea.style.border = '1px solid #ddd';
                textarea.style.borderRadius = '5px';
                textarea.style.fontFamily = 'inherit';
            }

            // Restaurer les styles du bouton d'envoi
            const sendButton = container.querySelector('button');
            if (sendButton) {
                sendButton.style.display = 'flex';
                sendButton.style.alignItems = 'center';
                sendButton.style.justifyContent = 'center';
                sendButton.style.marginLeft = '8px';
                sendButton.style.backgroundColor = '#007bff';
                sendButton.style.color = 'white';
                sendButton.style.border = 'none';
                sendButton.style.borderRadius = '5px';
                sendButton.style.padding = '8px 12px';
                sendButton.style.cursor = 'pointer';
            }
        });
    }

    // Méthode pour nettoyer et réappliquer correctement tous les styles du chat
    cleanupImportantStyles() {
        console.log('Cleaning up styles and forcing correct display of chat elements');

        // 1. Réinitialiser la feuille de style principale
        const styleElement = document.getElementById('wizzy-chat-styles');
        if (styleElement) {
            console.log('Restoring primary CSS style element');
            styleElement.removeAttribute('style');
        }

        // 2. Forcer l'affichage de la bulle et du bouton de chat
        const chatBubble = document.querySelector('.chat-bubble');
        if (chatBubble) {
            chatBubble.removeAttribute('style');
            chatBubble.style.position = 'fixed';
            chatBubble.style.bottom = '20px';
            chatBubble.style.right = '20px';
            chatBubble.style.zIndex = '1000';
        }

        // 3. Forcer les styles sur le conteneur principal du chat
        const chatWindow = document.getElementById('chatWindow') || document.querySelector('.chat-window');
        if (chatWindow) {
            // Supprimer tous les styles en ligne
            chatWindow.removeAttribute('style');

            // Appliquer les styles corrects
            chatWindow.style.position = 'fixed';
            chatWindow.style.bottom = '20px';
            chatWindow.style.right = '20px';
            chatWindow.style.width = '400px';
            chatWindow.style.height = '600px';
            chatWindow.style.background = 'white';
            chatWindow.style.borderRadius = '10px';
            chatWindow.style.boxShadow = '0 5px 25px rgba(0, 0, 0, 0.1)';
            chatWindow.style.display = 'flex';
            chatWindow.style.flexDirection = 'column';
            chatWindow.style.zIndex = '1000';
            chatWindow.style.transition = 'all 0.3s ease';

            // 4. Forcer les styles sur l'en-tête du chat
            const chatHeader = chatWindow.querySelector('.chat-header');
            if (chatHeader) {
                chatHeader.removeAttribute('style');
                chatHeader.style.padding = '15px';
                chatHeader.style.background = '#007bff';
                chatHeader.style.color = 'white';
                chatHeader.style.borderRadius = '10px 10px 0 0';
                chatHeader.style.display = 'flex';
                chatHeader.style.justifyContent = 'space-between';
                chatHeader.style.alignItems = 'center';

                // Restaurer les styles du titre
                const chatTitle = chatHeader.querySelector('.chat-title');
                if (chatTitle) {
                    chatTitle.removeAttribute('style');
                }

                // Restaurer les styles des actions
                const chatActions = chatHeader.querySelector('.chat-actions');
                if (chatActions) {
                    chatActions.removeAttribute('style');
                    chatActions.style.display = 'flex';
                    chatActions.style.gap = '10px';

                    // Restaurer les boutons
                    const buttons = chatActions.querySelectorAll('button');
                    buttons.forEach(button => {
                        button.removeAttribute('style');
                        button.style.background = 'none';
                        button.style.border = 'none';
                        button.style.color = 'white';
                        button.style.cursor = 'pointer';
                    });
                }
            }

            // 5. Forcer les styles sur le conteneur de messages
            const chatMessages = chatWindow.querySelector('#chatMessages, .chat-messages');
            if (chatMessages) {
                chatMessages.removeAttribute('style');
                chatMessages.style.flex = '1';
                chatMessages.style.padding = '15px';
                chatMessages.style.overflowY = 'auto';
                chatMessages.style.display = 'flex';
                chatMessages.style.flexDirection = 'column';
                chatMessages.style.gap = '10px';
                chatMessages.style.background = '#f8f9fa';
            }

            // 6. Forcer les styles sur le conteneur d'input
            const inputContainer = chatWindow.querySelector('.chat-input-container');
            if (inputContainer) {
                inputContainer.removeAttribute('style');
                inputContainer.style.display = 'flex';
                inputContainer.style.padding = '10px';
                inputContainer.style.borderTop = '1px solid #dee2e6';
                inputContainer.style.background = '#f8f9fa';

                // Restaurer les styles de textarea
                const userInput = inputContainer.querySelector('#userInput, .chat-input');
                if (userInput) {
                    userInput.removeAttribute('style');
                    userInput.style.display = 'block';
                    userInput.style.flex = '1';
                    userInput.style.resize = 'none';
                    userInput.style.minHeight = '40px';
                    userInput.style.maxHeight = '100px';
                    userInput.style.padding = '8px 12px';
                    userInput.style.border = '1px solid #ddd';
                    userInput.style.borderRadius = '5px';
                    userInput.style.fontFamily = 'inherit';
                }

                // Restaurer les styles du bouton d'envoi
                const sendButton = inputContainer.querySelector('#sendButton, .send-button');
                if (sendButton) {
                    sendButton.removeAttribute('style');
                    sendButton.style.display = 'flex';
                    sendButton.style.alignItems = 'center';
                    sendButton.style.justifyContent = 'center';
                    sendButton.style.marginLeft = '8px';
                    sendButton.style.backgroundColor = '#007bff';
                    sendButton.style.color = 'white';
                    sendButton.style.border = 'none';
                    sendButton.style.borderRadius = '5px';
                    sendButton.style.padding = '8px 12px';
                    sendButton.style.cursor = 'pointer';
                }
            }
        }

        // 7. Masquer le bouton toggle
        const toggleBtn = document.getElementById('toggleChat') || document.querySelector('.chat-toggle-btn');
        if (toggleBtn) {
            toggleBtn.style.display = 'none';
        }

        console.log('Chat styles forcefully restored');
    }
}

// Initialize chat when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    try {
        console.log('DOM loaded, initializing chat manager');
        window.chatManager = new ChatManager();

        // Directement configurer les écouteurs d'événements globaux pour le chat
        console.log('Setting up global event listeners for chat UI');

        // Écouteur global pour les clics sur les boutons toggle
        document.addEventListener('click', (e) => {
            // Vérifier si l'élément cliqué est un bouton toggle
            const isToggleButton =
                (e.target.id === 'toggleChat') ||
                e.target.classList.contains('chat-toggle-btn') ||
                (e.target.closest && (
                    e.target.closest('#toggleChat') ||
                    e.target.closest('.chat-toggle-btn')
                ));

            if (isToggleButton) {
                console.log('Toggle button click intercepted by global handler');

                // Force tous les éléments importants à être visibles
                const chatWindow = document.getElementById('chatWindow');
                if (chatWindow) {
                    console.log('Forcing chat window display from global handler');

                    // 1. Supprimer tous les styles
                    chatWindow.removeAttribute('style');

                    // 2. Appliquer les styles essentiels
                    chatWindow.style.display = 'flex';
                    chatWindow.style.flexDirection = 'column';
                    chatWindow.style.position = 'fixed';
                    chatWindow.style.bottom = '20px';
                    chatWindow.style.right = '20px';
                    chatWindow.style.width = '400px';
                    chatWindow.style.height = '600px';
                    chatWindow.style.zIndex = '1000';

                    // 3. Appliquer les styles aux enfants
                    const header = chatWindow.querySelector('.chat-header');
                    if (header) {
                        header.removeAttribute('style');
                        header.style.display = 'flex';
                        header.style.padding = '15px';
                    }

                    const messages = chatWindow.querySelector('#chatMessages');
                    if (messages) {
                        messages.removeAttribute('style');
                        messages.style.display = 'flex';
                        messages.style.flex = '1';
                        messages.style.overflowY = 'auto';
                    }

                    const inputContainer = chatWindow.querySelector('.chat-input-container');
                    if (inputContainer) {
                        inputContainer.removeAttribute('style');
                        inputContainer.style.display = 'flex';
                        inputContainer.style.padding = '10px';

                        const input = inputContainer.querySelector('#userInput');
                        if (input) {
                            input.removeAttribute('style');
                            input.style.display = 'block';
                            input.style.flex = '1';
                        }

                        const button = inputContainer.querySelector('#sendButton');
                        if (button) {
                            button.removeAttribute('style');
                            button.style.display = 'flex';
                        }
                    }

                    // 4. Masquer le bouton toggle
                    const toggleButton = document.getElementById('toggleChat');
                    if (toggleButton) toggleButton.style.display = 'none';
                }

                // Essayer d'utiliser le gestionnaire normal aussi
                if (window.chatManager && typeof window.chatManager.reopenChat === 'function') {
                    window.chatManager.reopenChat();
                }
            }
        }, true); // Capture phase pour intercepter avant tout autre gestionnaire

        // Écouteur global pour les clics sur les boutons de fermeture
        document.addEventListener('click', (e) => {
            // Vérifier si l'élément cliqué est un bouton de fermeture
            const isCloseButton =
                (e.target.id === 'closeChat') ||
                e.target.classList.contains('chat-close-btn') ||
                (e.target.closest && (
                    e.target.closest('#closeChat') ||
                    e.target.closest('.chat-close-btn')
                ));

            if (isCloseButton) {
                console.log('Close button click intercepted by global handler');

                // Cacher la fenêtre de chat
                const chatWindow = document.getElementById('chatWindow');
                if (chatWindow) {
                    chatWindow.style.display = 'none';
                }

                // Afficher le bouton toggle
                const toggleButton = document.getElementById('toggleChat');
                if (toggleButton) {
                    toggleButton.style.display = 'block';
                }

                // Essayer d'utiliser le gestionnaire normal aussi
                if (window.chatManager && typeof window.chatManager.closeChat === 'function') {
                    window.chatManager.closeChat();
                }
            }
        }, true); // Capture phase pour intercepter avant tout autre gestionnaire
    } catch (error) {
        console.error('Error initializing chat:', error);
    }
}); 