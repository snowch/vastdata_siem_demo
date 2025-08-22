// services/ai-agents/src/static/js/modules/websocket-client.js
// Refactored WebSocket client - focused on connection management

import * as debugLogger from '../debugLogger.js';
import * as ui from '../ui.js';
import * as progressManager from '../progressManager.js';

export class WebSocketClient {
    constructor() {
        this.websocket = null;
        this.stats = {
            connected: false,
            messages_sent: 0,
            messages_received: 0,
            reconnects: 0
        };
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.currentSessionId = null;
        this.messageHandlers = new Map();
        
        this.setupDefaultHandlers();
    }

    // ============================================================================
    // CONNECTION MANAGEMENT
    // ============================================================================

    async connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/analysis`;

        debugLogger.debugLog(`🔌 Connecting to WebSocket: ${wsUrl}`);
        progressManager.updateConnectionStatus('connecting');

        try {
            this.websocket = new WebSocket(wsUrl);
            this.attachEventListeners();
        } catch (error) {
            debugLogger.debugLog(`❌ WebSocket connection failed: ${error}`, 'ERROR');
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
        debugLogger.debugLog('✅ WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        this.stats.connected = true;
        this.reconnectAttempts = 0;
        
        ui.showStatus('🔌 Connected to security analysis system', 'success');
    }

    handleMessage(event) {
        this.stats.messages_received++;
        
        try {
            const data = JSON.parse(event.data);
            this.routeMessage(data);
        } catch (error) {
            debugLogger.debugLog(`❌ Error parsing WebSocket message: ${error}`, 'ERROR');
        }
    }

    handleClose(event) {
        debugLogger.debugLog(`🔌 WebSocket connection closed: ${event.code} - ${event.reason}`);
        progressManager.updateConnectionStatus('disconnected');
        this.stats.connected = false;

        if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
        } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            ui.showStatus('❌ Connection failed. Please refresh the page.', 'error');
        }
    }

    handleError(error) {
        debugLogger.debugLog(`❌ WebSocket error: ${error}`, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('❌ WebSocket connection error', 'error');
    }

    async attemptReconnect() {
        this.reconnectAttempts++;
        const delay = 2000 * this.reconnectAttempts;
        
        ui.showStatus(`🔄 Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
        
        setTimeout(() => {
            this.connect();
        }, delay);
    }

    // ============================================================================
    // MESSAGE HANDLING
    // ============================================================================

    setupDefaultHandlers() {
        // System messages
        this.registerHandler('connection_established', (data) => {
            this.currentSessionId = data.session_id;
            debugLogger.debugLog(`✅ Session established: ${this.currentSessionId}`);
        });

        this.registerHandler('error', (data) => {
            ui.showStatus(`❌ ${data.message}`, 'error');
        });

        this.registerHandler('logs_retrieved', (data) => {
            progressManager.handleLogsRetrieved(data);
        });

        this.registerHandler('pong', () => {
            ui.showStatus('🏓 Server responding', 'info');
        });

        // Analysis workflow messages
        this.registerHandler('triage_findings', (data) => {
            this.handleSecurityFindings('triage', data);
        });

        this.registerHandler('context_research', (data) => {
            this.handleSecurityFindings('context', data);
        });

        this.registerHandler('analysis_recommendations', (data) => {
            this.handleSecurityFindings('analyst', data);
        });

        this.registerHandler('workflow_progress', (data) => {
            ui.updateProgress(data.progress_percentage, data.current_stage);
        });

        this.registerHandler('analysis_complete', (data) => {
            this.handleAnalysisComplete(data);
        });

        this.registerHandler('approval_request', (data) => {
            this.handleApprovalRequest(data);
        });
    }

    registerHandler(messageType, handler) {
        this.messageHandlers.set(messageType, handler);
    }

    routeMessage(data) {
        const messageType = data.type;
        
        debugLogger.debugLog(`📨 Received: ${messageType}`);
        
        const handler = this.messageHandlers.get(messageType);
        if (handler) {
            try {
                handler(data);
            } catch (error) {
                debugLogger.debugLog(`❌ Error handling ${messageType}: ${error}`, 'ERROR');
            }
        } else {
            debugLogger.debugLog(`⚠️ No handler for message type: ${messageType}`, 'WARNING');
        }
    }

    // ============================================================================
    // DOMAIN-SPECIFIC HANDLERS
    // ============================================================================

    handleSecurityFindings(agentType, data) {
        const agentData = data.data;
        
        // Update agent status
        ui.updateAgentStatus(agentType, 'complete');
        
        // Show agent-specific content
        this.displayAgentFindings(agentType, agentData);
        
        // Show notification
        const notification = this.buildNotificationMessage(agentType, agentData);
        ui.showStatus(notification, 'info');
    }

    displayAgentFindings(agentType, data) {
        let content = '';
        
        switch (agentType) {
            case 'triage':
                content = this.formatTriageFindings(data);
                break;
            case 'context':
                content = this.formatContextFindings(data);
                break;
            case 'analyst':
                content = this.formatAnalystFindings(data);
                break;
        }
        
        ui.showAgentOutput(agentType, content);
        
        // Mark agent card as active
        const agentCard = document.getElementById(`${agentType}Card`);
        if (agentCard) {
            agentCard.classList.add('active');
        }
    }

    formatTriageFindings(data) {
        return `🚨 THREAT ASSESSMENT
        
⚠️  Priority: ${data.priority?.toUpperCase() || 'UNKNOWN'}
🎯 Threat: ${data.threat_type || 'Unknown threat type'}
📍 Source: ${data.source_ip || 'Unknown source'}
🎯 Targets: ${data.target_hosts?.join(', ') || 'Multiple systems'}
📊 Confidence: ${((data.confidence_score || 0) * 100).toFixed(1)}%

📋 Summary: ${data.brief_summary || 'Threat identified and classified'}`;
    }

    formatContextFindings(data) {
        return `📚 HISTORICAL CONTEXT
        
📊 Related Incidents: ${data.total_documents_found || 0}
🔍 Pattern Analysis: ${data.pattern_analysis || 'Analysis in progress'}
📝 Search Queries: ${data.search_queries?.join(', ') || 'Standard patterns'}

📋 Assessment: ${data.confidence_assessment || 'Correlation analysis complete'}`;
    }

    formatAnalystFindings(data) {
        const actions = data.recommended_actions || [];
        const actionsText = actions.length > 0 
            ? actions.map((action, i) => `   ${i + 1}. ${action}`).join('\n')
            : '   No specific actions identified';

        return `🎯 SECURITY ANALYSIS
        
📊 Recommendations: ${actions.length} actions identified
💼 Business Impact: ${data.business_impact || 'Under assessment'}

📋 Recommended Actions:
${actionsText}

📝 Notes: ${data.investigation_notes || 'Analysis complete'}`;
    }

    buildNotificationMessage(agentType, data) {
        switch (agentType) {
            case 'triage':
                const priority = data.priority || 'unknown';
                const threat = data.threat_type || 'security threat';
                return `🚨 ${priority.toUpperCase()} priority ${threat} detected`;
            
            case 'context':
                const incidents = data.total_documents_found || 0;
                return `📚 Found ${incidents} related security incidents`;
            
            case 'analyst':
                const recommendations = data.recommended_actions?.length || 0;
                return `🎯 Analysis complete: ${recommendations} recommendations`;
            
            default:
                return `✅ ${agentType} analysis complete`;
        }
    }

    handleAnalysisComplete(data) {
        ui.updateProgress(100, 'Analysis Complete');
        
        if (data.success) {
            ui.showStatus('🎉 Security analysis completed successfully!', 'success');
        } else {
            ui.showStatus('⚠️ Analysis completed with issues', 'warning');
        }
        
        // Re-enable analyze button
        progressManager.setAnalysisInProgress(false);
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
    }

    handleApprovalRequest(data) {
        // Delegate to approval workflow module
        import('./approval-workflow.js').then(approvalModule => {
            approvalModule.handleApprovalRequest(data);
        });
    }

    // ============================================================================
    // PUBLIC API
    // ============================================================================

    sendMessage(message) {
        if (!this.isConnected()) {
            debugLogger.debugLog('❌ Cannot send message - not connected', 'ERROR');
            ui.showStatus('❌ Not connected to server', 'error');
            return false;
        }

        try {
            const messageString = JSON.stringify(message);
            this.websocket.send(messageString);
            this.stats.messages_sent++;
            
            debugLogger.debugLog(`📤 Sent: ${message.type}`);
            return true;
        } catch (error) {
            debugLogger.debugLog(`❌ Failed to send message: ${error}`, 'ERROR');
            return false;
        }
    }

    isConnected() {
        return this.websocket && this.websocket.readyState === WebSocket.OPEN;
    }

    getStats() {
        return { 
            ...this.stats, 
            session_id: this.currentSessionId,
            ready_state: this.websocket?.readyState || 'CLOSED'
        };
    }

    testConnection() {
        if (this.isConnected()) {
            this.sendMessage({ 
                type: 'ping', 
                session_id: this.currentSessionId 
            });
            ui.showStatus('🏓 Testing connection...', 'info');
        } else {
            ui.showStatus('❌ Not connected', 'warning');
        }
    }

    showStats() {
        const stats = this.getStats();
        const statsText = `WebSocket Statistics:
Connected: ${stats.connected}
Messages Sent: ${stats.messages_sent}
Messages Received: ${stats.messages_received}
Session ID: ${stats.session_id || 'None'}
Ready State: ${stats.ready_state}`;

        debugLogger.debugLog(statsText);
        ui.showStatus('📊 WebSocket stats logged to console', 'info');
    }

    disconnect() {
        if (this.websocket) {
            this.websocket.close(1000, 'Client disconnect');
        }
    }
}

// ============================================================================
// SINGLETON INSTANCE AND EXPORTS
// ============================================================================

const wsClient = new WebSocketClient();

// Export for backward compatibility
export function initWebSocket() {
    return wsClient.connect();
}

export function sendWebSocketMessage(message) {
    return wsClient.sendMessage(message);
}

export function getWebSocket() {
    return wsClient.websocket;
}

export function showWebSocketStats() {
    return wsClient.showStats();
}

export function testConnection() {
    return wsClient.testConnection();
}

export function getCurrentSessionId() {
    return wsClient.currentSessionId;
}

// Handle page unload
window.addEventListener('beforeunload', () => {
    wsClient.disconnect();
});

// Export the client instance for advanced usage
export { wsClient };