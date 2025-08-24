// FIXED: src/static/js/modules/websocket-manager.js - PRESERVE AGENT RESULTS
// Fixed: Agent results are properly preserved when moving to next stage

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
        
        console.log(`📨 Received: ${messageType}`, {
            type: messageType,
            session_id: data.session_id,
            timestamp: new Date().toISOString()
        });
        
        if (!this.dashboard) {
            console.warn('No dashboard instance to route message to');
            return;
        }

        // Special debug for workflow completion messages
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
                console.log('📋 Triage findings - should show approval UI');
                this.dashboard.onTriageResults(data);
                break;
                
            case 'context_research':
                console.log('📚 Context research - should show approval UI');
                this.dashboard.onContextResults(data);
                break;
                
            case 'analysis_recommendations':
                console.log('🎯 Analyst recommendations - should show approval UI (NOT findings yet!)');
                this.dashboard.onAnalystResults(data);
                break;
                
            case 'approval_request':
                console.log('📝 Approval request received (UI will handle)');
                break;
                
            case 'agent_status_update':
                // 🔧 FIX: Handle backend agent status updates
                this.handleAgentStatusUpdate(data);
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
                if (messageType.includes('complete') || messageType.includes('finish')) {
                    console.warn(`🚨 SUSPICIOUS: Unhandled completion message - might trigger findings early!`);
                }
                break;
        }
    }

    // ============================================================================
    // APPROVAL RESPONSE HELPER - 🔧 FIXED: Don't overwrite results
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
            console.log(`🔄 Completing ${agentType} and activating next`);
            
            // 🔧 FIX: Just complete the agent, don't activate next here
            // The backend will handle the flow and send the next agent's results
            this.dashboard.uiManager.setAgentComplete(agentType);
            
            // 🔧 REMOVED: Don't call activateNextAgent here as it can interfere
            // Let the backend control the flow through normal message routing
            console.log(`✅ ${agentType} marked as complete - waiting for backend to continue workflow`);
            
        } else {
            console.error('❌ Failed to send approval response');
            this.dashboard.uiManager.showStatus('Failed to send response', 'error');
        }
        
        return success;
    }

    // 🔧 REMOVED: activateNextAgent method - let backend control flow
    // This was causing the UI to reset agent outputs prematurely

    // ============================================================================
    // AGENT STATUS UPDATE HANDLER - NEW
    // ============================================================================
    
    handleAgentStatusUpdate(data) {
        const { agent, status } = data;
        console.log(`📊 Backend agent status update: ${agent} → ${status}`);
        console.log(`🔍 Full agent status data:`, data);
        
        // Map backend agent names to frontend names
        const agentMapping = {
            'triage': 'triage',
            'context': 'context', 
            'analyst': 'analyst',
            'TriageSpecialist': 'triage',
            'ContextAgent': 'context',
            'SeniorAnalystSpecialist': 'analyst'
        };
        
        const frontendAgent = agentMapping[agent] || agent;
        
        // 🔧 FIX: Smart logic - don't reactivate completed agents
        if (status === 'active' && this.dashboard) {
            // Check if this agent already has results and is complete
            const currentState = this.dashboard.uiManager.agentStates[frontendAgent];
            const hasResults = this.dashboard.uiManager.agentOutputs[frontendAgent] && 
                             this.dashboard.uiManager.agentOutputs[frontendAgent].length > 100; // Has substantial results
            
            if (currentState === 'complete' && hasResults) {
                console.log(`🚫 Ignoring activation of completed agent ${frontendAgent} - results already preserved`);
                return; // Don't reactivate completed agents with results
            }
            
            // Backend is telling us to activate this agent
            console.log(`🔄 Backend activating agent: ${agent} → ${frontendAgent}`);
            this.dashboard.uiManager.setAgentActive(frontendAgent);
        } else if (status === 'complete' && this.dashboard) {
            // Backend is telling us this agent completed
            console.log(`✅ Backend completed agent: ${agent} → ${frontendAgent}`);
            // Note: Don't override if we already marked it complete with results
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