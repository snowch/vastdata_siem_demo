// UPDATED: src/static/js/modules/websocket-manager.js - ADD TIMING DEBUG
// Add debugging to identify why findings show too early

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
    // CONNECTION MANAGEMENT - Same as before
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
    // MESSAGE ROUTING - WITH TIMING DEBUG
    // ============================================================================

    routeMessage(data) {
        const messageType = data.type;
        
        // ✅ ADD: Enhanced debugging for timing issues
        console.log(`📨 Received: ${messageType}`, {
            type: messageType,
            session_id: data.session_id,
            timestamp: new Date().toISOString()
        });
        
        if (!this.dashboard) {
            console.warn('No dashboard instance to route message to');
            return;
        }

        // ✅ ADD: Special debug for workflow completion messages
        if (messageType === 'analysis_complete' || messageType === 'workflow_complete') {
            console.log(`🔔 CRITICAL: Workflow completion message received!`, data);
            console.log(`🔍 Current workflow state:`, this.dashboard.workflowState);
        }

        // Simple, direct routing to dashboard methods
        switch (messageType) {
            case 'connection_established':
                this.dashboard.onConnectionEstablished(data);
                break;
                
            case 'logs_retrieved':
                this.dashboard.onLogsRetrieved(data);
                break;
                
            case 'triage_findings':
                // Backend finished triage processing → show results + approval
                console.log('📋 Triage findings - should show approval UI');
                this.dashboard.onTriageResults(data);
                break;
                
            case 'context_research':
                // Backend finished context processing → show results + approval
                console.log('📚 Context research - should show approval UI');
                this.dashboard.onContextResults(data);
                break;
                
            case 'analysis_recommendations':
                // Backend finished analyst processing → show results + approval
                console.log('🎯 Analyst recommendations - should show approval UI (NOT findings yet!)');
                this.dashboard.onAnalystResults(data);
                break;
                
            case 'approval_request':
                // This is handled automatically by the UI now
                console.log('📝 Approval request received (UI will handle)');
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
            case 'workflow_complete':
                // ✅ ADD: This should only happen AFTER final approval
                console.log('🏁 WORKFLOW COMPLETE - This should show findings panel');
                console.log('🔍 Approval state check:', this.dashboard.workflowState);
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
                // ✅ ADD: Debug unhandled messages that might trigger findings
                if (messageType.includes('complete') || messageType.includes('finish')) {
                    console.warn(`🚨 SUSPICIOUS: Unhandled completion message - might trigger findings early!`);
                }
                break;
        }
    }

    // ============================================================================
    // APPROVAL RESPONSE HELPER - WITH DEBUG
    // ============================================================================
    
    sendApprovalResponse(agentType, response) {
        console.log(`📤 Sending approval response for ${agentType}: ${response}`);
        
        const success = this.send({
            type: 'TextMessage',
            content: response,
            source: 'user'
        });
        
        if (success) {
            console.log('✅ Approval response sent successfully');
            
            // ✅ ADD: Debug the state changes
            console.log(`🔄 Completing ${agentType} and activating next`);
            
            // Complete current agent and activate next
            this.dashboard.uiManager.setAgentComplete(agentType);
            this.activateNextAgent(agentType);
            
        } else {
            console.error('❌ Failed to send approval response');
            this.dashboard.uiManager.showStatus('Failed to send response', 'error');
        }
        
        return success;
    }

    activateNextAgent(currentStage) {
        // Simple sequence: triage → context → analyst → done
        const sequence = { 'triage': 'context', 'context': 'analyst', 'analyst': null };
        const nextStage = sequence[currentStage];
        
        if (nextStage) {
            console.log(`🔄 Activating next agent: ${nextStage}`);
            this.dashboard.uiManager.setAgentActive(nextStage);
        } else {
            console.log('✅ No more agents to activate - workflow should end soon');
            console.log('⚠️ Findings panel should NOT show until backend sends completion message');
        }
    }

    // ============================================================================
    // MESSAGE SENDING - Same as before
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
    // UTILITIES - Same as before
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