// services/ai-agents/src/static/js/modules/websocket-manager.js - COMPLETE FIXED FILE
// Handles WebSocket communication with proper approval status updates

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
    // MESSAGE ROUTING - HANDLES CORRECT AGENT STATUS FLOW
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
                this.dashboard.onTriageComplete(data);
                break;
                
            case 'context_research':
                this.dashboard.onContextComplete(data);
                break;
                
            case 'analysis_recommendations':
                this.dashboard.onAnalysisComplete(data);
                break;
                
            case 'approval_request':
                this.dashboard.onApprovalRequest(data);
                break;

            // ============================================================================
            // CRITICAL: Agent Status Update Handling - Follows the Pattern
            // ============================================================================
            case 'agent_status_update':
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
                this.dashboard.onAnalysisComplete(data);
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
    // AGENT STATUS UPDATE HANDLER - IMPLEMENTS THE CORRECT PATTERN
    // ============================================================================
    handleAgentStatusUpdate(data) {
        const agent = data.agent;
        const status = data.status;
        const message = data.message;
        
        console.log(`🔄 Agent status update: ${agent} -> ${status}`);
        
        if (!agent || !status) {
            console.warn('Invalid agent status update:', data);
            return;
        }

        // PATTERN IMPLEMENTATION:
        // - When agent becomes "active": show spinner
        // - When agent becomes "complete": hide spinner, show results
        // - When agent becomes "awaiting-approval": show approval box (but status stays "complete")
        // - When approval given: hide approval box, next agent becomes "active"

        // Update the agent status in UI (this handles spinner show/hide automatically)
        this.dashboard.uiManager.updateAgent(agent, status);
        
        // CRITICAL: Hide approval UI when agent status changes from awaiting-approval
        // This happens when user clicks approve and backend activates next stage
        if (status !== 'awaiting-approval') {
            console.log(`🗑️ Clearing approval for ${agent} (status: ${status})`);
            this.dashboard.uiManager.hideApprovalForAgent(agent);
        }
        
        // Show status message if provided
        if (message) {
            this.dashboard.uiManager.showStatus(message, 'info');
        }
        
        // Handle specific status transitions with proper logging
        switch (status) {
            case 'active':
                console.log(`🔄 ${agent} agent is now processing (spinner should be visible)`);
                break;
            case 'complete':
                console.log(`✅ ${agent} agent completed (spinner should be hidden, results visible)`);
                break;
            case 'awaiting-approval':
                console.log(`⏳ ${agent} agent awaiting approval (approval box should be visible)`);
                break;
            case 'error':
                console.log(`❌ ${agent} agent error`);
                this.dashboard.uiManager.showStatus(`${agent} agent error`, 'error');
                break;
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