// services/ai-agents/src/static/js/modules/websocket-manager.js - CLEAN FLOW IMPLEMENTATION
// Handles WebSocket communication with simplified agent status flow

export class WebSocketManager {
    constructor() {
        this.websocket = null;
        this.dashboard = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.stats = {
            connected: false,
            messagesSent: 0,
            messagesReceived: 0
        };
    }

    async initialize(dashboard) {
        this.dashboard = dashboard;
        await this.connect();
        console.log('✅ WebSocket Manager initialized');
    }

    // ============================================================================
    // CONNECTION MANAGEMENT
    // ============================================================================

    async connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/analysis`;

        console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);

        try {
            this.websocket = new WebSocket(wsUrl);
            this.attachEventListeners();
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.handleConnectionError();
        }
    }

    attachEventListeners() {
        this.websocket.onopen = (event) => this.handleOpen(event);
        this.websocket.onmessage = (event) => this.handleMessage(event);
        this.websocket.onclose = (event) => this.handleClose(event);
        this.websocket.onerror = (error) => this.handleError(error);
    }

    handleOpen(event) {
        console.log('✅ WebSocket connected');
        this.stats.connected = true;
        this.reconnectAttempts = 0;
        
        if (this.dashboard) {
            this.dashboard.uiManager.setConnectionStatus('connecting');
        }
    }

    handleMessage(event) {
        this.stats.messagesReceived++;
        
        try {
            const data = JSON.parse(event.data);
            this.routeMessage(data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }

    handleClose(event) {
        console.log(`🔌 WebSocket closed: ${event.code} - ${event.reason}`);
        this.stats.connected = false;
        
        if (this.dashboard) {
            this.dashboard.onConnectionLost();
        }

        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
        }
    }

    handleError(error) {
        console.error('WebSocket error:', error);
        if (this.dashboard) {
            this.dashboard.uiManager.showStatus('Connection error', 'error');
        }
    }

    attemptReconnect() {
        this.reconnectAttempts++;
        const delay = 2000 * this.reconnectAttempts;
        
        console.log(`🔄 Reconnecting in ${delay}ms... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }

    // ============================================================================
    // MESSAGE ROUTING - CLEAN FLOW IMPLEMENTATION
    // ============================================================================

    routeMessage(data) {
        const messageType = data.type;
        
        console.log(`📨 Received: ${messageType}`);
        
        if (!this.dashboard) {
            console.warn('No dashboard instance to route message to');
            return;
        }

        // Route to appropriate dashboard handler
        switch (messageType) {
            case 'connection_established':
                this.dashboard.onConnectionEstablished(data);
                break;
                
            case 'logs_retrieved':
                this.dashboard.onLogsRetrieved(data);
                break;
                
            case 'triage_findings':
                // CLEAN FLOW: Triage completed its processing, show results and request approval
                this.dashboard.onTriageComplete(data);
                break;
                
            case 'context_research':
                // CLEAN FLOW: Context completed its processing, show results and request approval
                this.dashboard.onContextComplete(data);
                break;
                
            case 'analysis_recommendations':
                // CLEAN FLOW: Analyst completed its processing, show results and request approval
                this.dashboard.onAnalysisComplete(data);
                break;
                
            case 'approval_request':
                // CLEAN FLOW: Backend is requesting approval for a stage
                this.handleApprovalRequest(data);
                break;
                
            case 'workflow_progress':
                if (data.progress_percentage !== undefined) {
                    this.dashboard.uiManager.updateProgress(
                        data.progress_percentage, 
                        data.current_stage
                    );
                }
                break;
                
            case 'analysis_complete':
                this.dashboard.onWorkflowComplete(data);
                break;
                
            case 'error':
                this.dashboard.onError(data);
                break;
                
            case 'pong':
                this.dashboard.uiManager.showStatus('🏓 Server responding', 'info');
                break;
                
            default:
                console.log(`⚠️ Unhandled message type: ${messageType}`);
                break;
        }
    }

    // ============================================================================
    // APPROVAL REQUEST HANDLING - SIMPLIFIED
    // ============================================================================
    
    handleApprovalRequest(data) {
        console.log('🔔 Approval request received:', data);
        
        const stage = this.determineStage(data);
        const prompt = data.prompt || data.content || 'Approval required';
        
        // Show approval UI for this stage
        this.dashboard.uiManager.showApprovalForAgent(stage, prompt, (response) => {
            console.log(`📤 Sending approval response for ${stage}: ${response}`);
            
            const success = this.send({
                type: 'TextMessage',
                content: response,
                source: 'user'
            });
            
            if (success) {
                console.log('✅ Approval response sent successfully');
                // Hide approval UI since response was sent
                this.dashboard.uiManager.hideApprovalForAgent(stage);
                // Set agent to complete status
                this.dashboard.uiManager.updateAgent(stage, 'complete');
                // Activate next agent if applicable
                this.activateNextAgent(stage);
            } else {
                console.error('❌ Failed to send approval response');
                this.dashboard.uiManager.showStatus('Failed to send response', 'error');
            }
        });
    }

    determineStage(data) {
        // Simple stage detection
        if (data.stage) return data.stage;
        
        const content = (data.content || data.prompt || '').toLowerCase();
        if (content.includes('threat') || content.includes('investigate')) return 'triage';
        if (content.includes('context') || content.includes('historical')) return 'context';
        if (content.includes('recommend') || content.includes('action')) return 'analyst';
        
        return 'triage'; // Default
    }

    activateNextAgent(currentStage) {
        // Activate the next agent in sequence
        const sequence = { 'triage': 'context', 'context': 'analyst', 'analyst': null };
        const nextStage = sequence[currentStage];
        
        if (nextStage) {
            console.log(`🔄 Activating next agent: ${nextStage}`);
            this.dashboard.uiManager.updateAgent(nextStage, 'active');
        } else {
            console.log('✅ No more agents to activate - workflow ending');
        }
    }

    // ============================================================================
    // MESSAGE SENDING
    // ============================================================================

    send(message) {
        if (!this.isConnected()) {
            console.error('Cannot send message - not connected');
            if (this.dashboard) {
                this.dashboard.uiManager.showStatus('Not connected to server', 'error');
            }
            return false;
        }

        try {
            const messageString = JSON.stringify(message);
            this.websocket.send(messageString);
            this.stats.messagesSent++;
            
            console.log(`📤 Sent: ${message.type}`);
            return true;
        } catch (error) {
            console.error('Failed to send message:', error);
            return false;
        }
    }

    // ============================================================================
    // UTILITIES
    // ============================================================================

    isConnected() {
        return this.websocket && this.websocket.readyState === WebSocket.OPEN;
    }

    getStats() {
        return {
            ...this.stats,
            readyState: this.websocket?.readyState || 'CLOSED',
            reconnectAttempts: this.reconnectAttempts
        };
    }

    test() {
        if (this.isConnected()) {
            this.send({ type: 'ping' });
            return true;
        } else {
            if (this.dashboard) {
                this.dashboard.uiManager.showStatus('Not connected', 'warning');
            }
            return false;
        }
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close(1000, 'Client disconnect');
        }
    }
}

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.socDashboard?.websocketManager) {
        window.socDashboard.websocketManager.disconnect();
    }
});