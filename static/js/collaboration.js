/**
 * Course Outline Collaboration Interface
 * 
 * This script provides real-time collaboration functionality for course outline
 * analysis, allowing multiple users to annotate and review documents simultaneously.
 */

class CollaborationInterface {
    constructor(documentId, currentUserId, currentUsername) {
        this.documentId = documentId;
        this.currentUserId = currentUserId;
        this.currentUsername = currentUsername;
        this.socket = null;
        this.onlineUsers = new Set();
        this.selectionRange = null;
        this.currentSelection = null;
        
        // Initialize the interface
        this.initialize();
    }
    
    /**
     * Initialize the collaboration interface
     */
    initialize() {
        // Connect to Socket.IO
        this.connectToSocket();
        
        // Set up event listeners
        this.setupDocumentListeners();
        this.setupAnnotationListeners();
        this.setupChatListeners();
        
        // Load existing data
        this.loadExistingChatMessages();
        this.highlightExistingAnnotations();
        
        // Set up cleanup on page unload
        window.addEventListener('beforeunload', () => {
            this.socket.emit('leave_document', { document_id: this.documentId });
        });
    }
    
    /**
     * Connect to the Socket.IO server
     */
    connectToSocket() {
        this.socket = io();
        
        // Connection event
        this.socket.on('connect', () => {
            console.log('Connected to Socket.IO server');
            this.socket.emit('join_document', { document_id: this.documentId });
            this.addUserToOnlineList(this.currentUserId, this.currentUsername);
        });
        
        // Disconnection event
        this.socket.on('disconnect', () => {
            console.log('Disconnected from Socket.IO server');
        });
        
        // User joined event
        this.socket.on('user_joined', (data) => {
            console.log(`User ${data.username} joined`);
            this.addUserToOnlineList(data.user_id, data.username);
            this.addSystemMessage(`${data.username} joined the document`);
        });
        
        // User left event
        this.socket.on('user_left', (data) => {
            console.log(`User ${data.username} left`);
            this.removeUserFromOnlineList(data.user_id);
            this.addSystemMessage(`${data.username} left the document`);
        });
        
        // New annotation event
        this.socket.on('new_annotation', (data) => {
            console.log('New annotation received:', data);
            this.addAnnotationToList(data);
            this.highlightAnnotatedText(data);
        });
        
        // Annotation updated event
        this.socket.on('annotation_updated', (data) => {
            console.log('Annotation updated:', data);
            this.updateAnnotationInList(data);
            this.updateAnnotationHighlight(data);
        });
        
        // Annotation deleted event
        this.socket.on('annotation_deleted', (data) => {
            console.log('Annotation deleted:', data);
            this.removeAnnotationFromList(data.id);
            this.removeAnnotationHighlight(data.id);
        });
        
        // Chat message event
        this.socket.on('chat_message', (data) => {
            console.log('Chat message received:', data);
            this.addChatMessage(data, data.user_id === this.currentUserId);
        });
    }
    
    /**
     * Set up event listeners for document interaction
     */
    setupDocumentListeners() {
        const documentDisplay = document.getElementById('document-display');
        if (!documentDisplay) return;
        
        // Track text selection for annotations
        documentDisplay.addEventListener('mouseup', () => {
            const selection = window.getSelection();
            if (selection.toString().trim().length > 0) {
                // Get the selected range
                const range = selection.getRangeAt(0);
                this.selectionRange = range;
                
                // Calculate selection position
                // This simple approach works for plain text, but you might need
                // a more sophisticated approach for complex documents
                const position = JSON.stringify({
                    startOffset: range.startOffset,
                    endOffset: range.endOffset,
                    startContainerPath: this.getNodePath(range.startContainer),
                    endContainerPath: this.getNodePath(range.endContainer),
                    selectedText: selection.toString()
                });
                
                this.currentSelection = {
                    text: selection.toString(),
                    position: position
                };
                
                // Highlight the add annotation button
                const addAnnotationBtn = document.getElementById('add-annotation-btn');
                if (addAnnotationBtn) {
                    addAnnotationBtn.classList.add('btn-pulse');
                }
            } else {
                this.currentSelection = null;
                this.selectionRange = null;
                
                const addAnnotationBtn = document.getElementById('add-annotation-btn');
                if (addAnnotationBtn) {
                    addAnnotationBtn.classList.remove('btn-pulse');
                }
            }
        });
        
        // Handle clicking on annotated text
        documentDisplay.addEventListener('click', (e) => {
            const annotationMarker = e.target.closest('.annotation-marker');
            if (annotationMarker) {
                const annotationId = annotationMarker.dataset.annotationId;
                this.showAnnotationTooltip(annotationMarker, annotationId);
            }
        });
    }
    
    /**
     * Set up event listeners for annotations
     */
    setupAnnotationListeners() {
        // Add annotation button
        const addAnnotationBtn = document.getElementById('add-annotation-btn');
        if (addAnnotationBtn) {
            addAnnotationBtn.addEventListener('click', () => {
                if (this.currentSelection) {
                    // Show the selected text in the modal
                    const selectedTextElem = document.getElementById('selected-text');
                    if (selectedTextElem) {
                        selectedTextElem.textContent = this.currentSelection.text;
                    }
                    
                    const positionDataElem = document.getElementById('position-data');
                    if (positionDataElem) {
                        positionDataElem.value = this.currentSelection.position;
                    }
                    
                    // Show the modal
                    const modal = document.getElementById('annotationModal');
                    if (modal) {
                        new bootstrap.Modal(modal).show();
                    }
                } else {
                    alert('Please select text to annotate first.');
                }
            });
        }
        
        // Save annotation button
        const saveAnnotationBtn = document.getElementById('save-annotation-btn');
        if (saveAnnotationBtn) {
            saveAnnotationBtn.addEventListener('click', () => {
                const annotationText = document.getElementById('annotation-text');
                const positionData = document.getElementById('position-data');
                
                if (!annotationText || !positionData || !annotationText.value.trim()) {
                    alert('Please enter an annotation.');
                    return;
                }
                
                // Send annotation to server
                fetch(`/document/${this.documentId}/add_annotation`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        text: annotationText.value.trim(),
                        position: positionData.value
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.text();
                })
                .then(() => {
                    // Close the modal
                    const modal = document.getElementById('annotationModal');
                    if (modal) {
                        bootstrap.Modal.getInstance(modal).hide();
                    }
                    
                    // Clear the form
                    if (annotationText) {
                        annotationText.value = '';
                    }
                })
                .catch(error => {
                    console.error('Error adding annotation:', error);
                    alert('Error adding annotation. Please try again.');
                });
            });
        }
        
        // Annotation list item clicks
        const annotationsList = document.getElementById('annotations-list');
        if (annotationsList) {
            annotationsList.addEventListener('click', (e) => {
                const annotationItem = e.target.closest('.annotation-list-item');
                if (annotationItem) {
                    const annotationId = annotationItem.dataset.id;
                    const position = annotationItem.dataset.position;
                    
                    try {
                        // Highlight the annotation in the document
                        this.scrollToAnnotation(annotationId, JSON.parse(position));
                    } catch (error) {
                        console.error('Error parsing annotation position:', error);
                    }
                }
            });
        }
    }
    
    /**
     * Set up event listeners for chat
     */
    setupChatListeners() {
        // Send button
        const chatSendBtn = document.getElementById('chat-send-btn');
        if (chatSendBtn) {
            chatSendBtn.addEventListener('click', () => {
                this.sendChatMessage();
            });
        }
        
        // Enter key in input
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.sendChatMessage();
                }
            });
        }
    }
    
    /**
     * Send a chat message
     */
    sendChatMessage() {
        const messageInput = document.getElementById('chat-input');
        if (!messageInput) return;
        
        const message = messageInput.value.trim();
        if (message) {
            this.socket.emit('new_chat_message', {
                document_id: this.documentId,
                message: message
            });
            
            messageInput.value = '';
        }
    }
    
    /**
     * Load existing chat messages from the server
     */
    loadExistingChatMessages() {
        // Add welcome message
        this.addSystemMessage('Welcome to the collaboration chat');
        
        // In a real implementation, you would fetch existing messages from the server
        // For example:
        // fetch(`/api/document/${this.documentId}/chat_messages`)
        //     .then(response => response.json())
        //     .then(messages => {
        //         messages.forEach(message => {
        //             this.addChatMessage(message, message.user_id === this.currentUserId);
        //         });
        //     });
    }
    
    /**
     * Highlight existing annotations in the document
     */
    highlightExistingAnnotations() {
        const annotationItems = document.querySelectorAll('.annotation-list-item');
        annotationItems.forEach(item => {
            try {
                const annotationId = item.dataset.id;
                const position = JSON.parse(item.dataset.position);
                
                // Highlight the annotation in the document
                this.highlightAnnotatedText({
                    id: annotationId,
                    position: position
                });
            } catch (error) {
                console.error('Error parsing annotation position:', error);
            }
        });
    }
    
    /**
     * Add a user to the online users list
     */
    addUserToOnlineList(userId, username) {
        if (this.onlineUsers.has(userId)) return;
        
        this.onlineUsers.add(userId);
        
        const onlineUsersList = document.getElementById('online-users-list');
        if (!onlineUsersList) return;
        
        const userItem = document.createElement('li');
        userItem.className = 'list-group-item py-1';
        userItem.dataset.userId = userId;
        userItem.innerHTML = `
            <span class="user-presence-indicator user-presence-online"></span>
            ${username}
        `;
        
        onlineUsersList.appendChild(userItem);
    }
    
    /**
     * Remove a user from the online users list
     */
    removeUserFromOnlineList(userId) {
        if (!this.onlineUsers.has(userId)) return;
        
        this.onlineUsers.delete(userId);
        
        const userItem = document.querySelector(`#online-users-list li[data-user-id="${userId}"]`);
        if (userItem) {
            userItem.remove();
        }
    }
    
    /**
     * Add a system message to the chat
     */
    addSystemMessage(message) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;
        
        const messageElement = document.createElement('div');
        messageElement.className = 'text-center my-2';
        messageElement.innerHTML = `<small class="text-muted">${message}</small>`;
        
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    /**
     * Add a chat message to the chat window
     */
    addChatMessage(message, isSelf) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;
        
        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${isSelf ? 'chat-message-self' : 'chat-message-other'}`;
        
        // Format the timestamp
        const timestamp = message.timestamp ? new Date(message.timestamp) : new Date();
        const formattedTime = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageElement.innerHTML = `
            ${!isSelf ? `<div class="chat-username">${message.username}</div>` : ''}
            <div>${message.message}</div>
            <div class="chat-timestamp">${formattedTime}</div>
        `;
        
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    /**
     * Add an annotation to the list
     */
    addAnnotationToList(annotation) {
        const annotationsList = document.getElementById('annotations-list');
        if (!annotationsList) return;
        
        // Remove "No annotations yet" message if present
        const noAnnotationsItem = annotationsList.querySelector('li:only-child');
        if (noAnnotationsItem && noAnnotationsItem.textContent === 'No annotations yet') {
            noAnnotationsItem.remove();
        }
        
        // Create new annotation list item
        const annotationItem = document.createElement('li');
        annotationItem.className = 'list-group-item annotation-list-item';
        annotationItem.dataset.id = annotation.id;
        annotationItem.dataset.position = typeof annotation.position === 'string' 
            ? annotation.position 
            : JSON.stringify(annotation.position);
        
        // Format the timestamp
        const timestamp = annotation.created_at ? new Date(annotation.created_at) : new Date();
        const formattedTime = timestamp.toLocaleString([], { 
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        annotationItem.innerHTML = `
            <div class="d-flex justify-content-between">
                <span class="fw-bold">${annotation.username}</span>
                <small class="text-muted">${formattedTime}</small>
            </div>
            <p class="mb-0">${annotation.text}</p>
        `;
        
        annotationsList.appendChild(annotationItem);
    }
    
    /**
     * Update an annotation in the list
     */
    updateAnnotationInList(annotation) {
        const annotationItem = document.querySelector(`.annotation-list-item[data-id="${annotation.id}"]`);
        if (annotationItem) {
            annotationItem.querySelector('p').textContent = annotation.text;
            
            // Update timestamp if provided
            if (annotation.updated_at) {
                const timestamp = new Date(annotation.updated_at);
                const formattedTime = timestamp.toLocaleString([], { 
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
                
                const timeElement = annotationItem.querySelector('small.text-muted');
                if (timeElement) {
                    timeElement.textContent = formattedTime;
                }
            }
        }
    }
    
    /**
     * Remove an annotation from the list
     */
    removeAnnotationFromList(annotationId) {
        const annotationItem = document.querySelector(`.annotation-list-item[data-id="${annotationId}"]`);
        if (annotationItem) {
            annotationItem.remove();
            
            // If no annotations left, add 'No annotations yet' message
            const annotationsList = document.getElementById('annotations-list');
            if (annotationsList && annotationsList.children.length === 0) {
                annotationsList.innerHTML = '<li class="list-group-item">No annotations yet</li>';
            }
        }
    }
    
    /**
     * Highlight text in the document based on annotation position
     */
    highlightAnnotatedText(annotation) {
        try {
            const documentDisplay = document.getElementById('document-display');
            if (!documentDisplay) return;
            
            const position = typeof annotation.position === 'string' 
                ? JSON.parse(annotation.position) 
                : annotation.position;
            
            // This is a simplified implementation that works for plain text
            // In a real application, you would need a more sophisticated approach
            if (position.startContainerPath && position.endContainerPath) {
                // More complex positioning using node paths
                // Not implemented in this example
                console.log('Complex positioning not implemented');
            } else if (position.startOffset !== undefined && position.endOffset !== undefined) {
                // Simple text-based positioning
                // Find the text node that contains the selected text
                const textNodes = this.getTextNodes(documentDisplay);
                
                for (const node of textNodes) {
                    const nodeText = node.textContent;
                    if (position.selectedText && nodeText.includes(position.selectedText)) {
                        // Found the node containing the selected text
                        const startOffset = nodeText.indexOf(position.selectedText);
                        const endOffset = startOffset + position.selectedText.length;
                        
                        // Split the text node into three parts: before, selected, after
                        const range = document.createRange();
                        range.setStart(node, startOffset);
                        range.setEnd(node, endOffset);
                        
                        // Create the highlight element
                        const highlightElement = document.createElement('span');
                        highlightElement.className = 'annotation-marker';
                        highlightElement.dataset.annotationId = annotation.id;
                        highlightElement.title = 'Click to view annotation';
                        
                        // Replace the selected text with the highlight element
                        range.surroundContents(highlightElement);
                        break;
                    }
                }
            }
        } catch (error) {
            console.error('Error highlighting annotation:', error);
        }
    }
    
    /**
     * Update the highlighting of an annotation
     */
    updateAnnotationHighlight(annotation) {
        const highlightElement = document.querySelector(`.annotation-marker[data-annotation-id="${annotation.id}"]`);
        if (highlightElement) {
            // Update tooltip or other properties if needed
        }
    }
    
    /**
     * Remove the highlighting of an annotation
     */
    removeAnnotationHighlight(annotationId) {
        const highlightElement = document.querySelector(`.annotation-marker[data-annotation-id="${annotationId}"]`);
        if (highlightElement) {
            // Get the text content
            const textContent = highlightElement.textContent;
            
            // Replace the highlight element with plain text
            highlightElement.parentNode.replaceChild(document.createTextNode(textContent), highlightElement);
        }
    }
    
    /**
     * Show a tooltip for an annotation
     */
    showAnnotationTooltip(marker, annotationId) {
        // Remove any existing tooltips
        const existingTooltips = document.querySelectorAll('.annotation-tooltip');
        existingTooltips.forEach(tooltip => tooltip.remove());
        
        // Find the annotation data
        const annotationItem = document.querySelector(`.annotation-list-item[data-id="${annotationId}"]`);
        if (!annotationItem) return;
        
        // Get the annotation data
        const username = annotationItem.querySelector('.fw-bold').textContent;
        const timestamp = annotationItem.querySelector('.text-muted').textContent;
        const text = annotationItem.querySelector('p').textContent;
        
        // Create the tooltip
        const tooltip = document.createElement('div');
        tooltip.className = 'annotation-tooltip';
        tooltip.innerHTML = `
            <div class="annotation-author">${username}</div>
            <div class="annotation-date">${timestamp}</div>
            <div class="annotation-text">${text}</div>
            <div class="mt-2">
                <button class="btn btn-sm btn-outline-secondary close-tooltip-btn">Close</button>
            </div>
        `;
        
        // Position the tooltip near the marker
        const markerRect = marker.getBoundingClientRect();
        const documentDisplay = document.getElementById('document-display');
        if (!documentDisplay) return;
        
        const documentRect = documentDisplay.getBoundingClientRect();
        
        tooltip.style.top = `${markerRect.bottom - documentRect.top + documentDisplay.scrollTop + 10}px`;
        tooltip.style.left = `${markerRect.left - documentRect.left + documentDisplay.scrollLeft}px`;
        
        // Add the tooltip to the document display
        documentDisplay.appendChild(tooltip);
        
        // Add event listener to close the tooltip
        tooltip.querySelector('.close-tooltip-btn').addEventListener('click', () => {
            tooltip.remove();
        });
        
        // Close the tooltip when clicking outside
        document.addEventListener('click', function closeTooltip(e) {
            if (!tooltip.contains(e.target) && e.target !== marker) {
                tooltip.remove();
                document.removeEventListener('click', closeTooltip);
            }
        });
    }
    
    /**
     * Scroll to an annotation in the document
     */
    scrollToAnnotation(annotationId, position) {
        const highlightElement = document.querySelector(`.annotation-marker[data-annotation-id="${annotationId}"]`);
        if (highlightElement) {
            // Scroll to the highlight element
            highlightElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Flash the highlight element to make it more visible
            highlightElement.classList.add('flash-highlight');
            setTimeout(() => {
                highlightElement.classList.remove('flash-highlight');
            }, 1500);
        } else if (position && position.selectedText) {
            // Try to find the text in the document
            const documentDisplay = document.getElementById('document-display');
            if (!documentDisplay) return;
            
            // Search for the text
            const textNodes = this.getTextNodes(documentDisplay);
            for (const node of textNodes) {
                const nodeText = node.textContent;
                if (nodeText.includes(position.selectedText)) {
                    // Found the node containing the selected text
                    node.parentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    break;
                }
            }
        }
    }
    
    /**
     * Get all text nodes in an element
     */
    getTextNodes(element) {
        const textNodes = [];
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );
        
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }
        
        return textNodes;
    }
    
    /**
     * Get the path to a node from its root element
     */
    getNodePath(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            node = node.parentNode;
        }
        
        const path = [];
        let current = node;
        
        while (current && current !== document.body) {
            let index = 0;
            let sibling = current;
            
            while (sibling) {
                if (sibling.nodeName === current.nodeName) {
                    index++;
                }
                sibling = sibling.previousElementSibling;
            }
            
            path.unshift(`${current.nodeName.toLowerCase()}:${index}`);
            current = current.parentNode;
        }
        
        return path.join('/');
    }
}

// Initialize the collaboration interface when the page loads, but only for document view pages
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a document view page
    const documentDisplay = document.getElementById('document-display');
    
    // Only initialize collaboration on document view pages
    if (documentDisplay) {
        const documentIdElement = document.getElementById('document-id');
        const currentUserIdElement = document.getElementById('current-user-id');
        const currentUsernameElement = document.getElementById('current-username');
        
        if (documentIdElement && currentUserIdElement && currentUsernameElement) {
            const documentId = documentIdElement.value;
            const currentUserId = currentUserIdElement.value;
            const currentUsername = currentUsernameElement.value;
            
            new CollaborationInterface(documentId, currentUserId, currentUsername);
        } else {
            console.error('Missing required elements for collaboration interface');
        }
    }
});