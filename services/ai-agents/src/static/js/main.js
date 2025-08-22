// services/ai-agents/src/static/js/main.js - CLEAN REFACTORED
// Simple, clean entry point with no backward compatibility

import { WebSocketManager } from './modules/websocket-manager.js';
import { UIManager } from './modules/ui-manager.js';
import { EventManager } from './modules/event-manager.js';
import { DebugManager } from './modules/debug-manager.js';

class SOCDashboard {
    constructor() {
        this.websocketManager = new WebSocketManager();
        this.uiManager = new UIManager();
        this.eventManager = new EventManager();
        this.debugManager = new DebugManager();
        
        this.analysisInProgress = false;
        this.currentSessionId = null;
    }

    async initialize() {
        console.log('🚀 Initializing SOC Dashboard - Clean Architecture');
        
        try {
            // Initialize managers in order
            await this.uiManager.initialize();
            await this.debugManager.initialize();
            await this.eventManager.initialize(this);
            await this.websocketManager.initialize(this);
            
            this.uiManager.showWelcome();
            console.log('✅ SOC Dashboard initialized successfully');
            
        } catch (error) {
            console.error('❌ Dashboard initialization failed:', error);
            this.uiManager.showError('Dashboard initialization failed: ' + error.message);
        }
    }

    // ============================================================================
    // PUBLIC API - Called by event handlers
    // ============================================================================

    async retrieveLogs() {
        if (!this.websocketManager.isConnected()) {
            this.uiManager.showStatus('Not connected to server', 'error');
            return;
        }

        this.uiManager.updateProgress(10, 'Retrieving logs...');
        this.websocketManager.send({ type: 'retrieve_logs' });
    }

    async startAnalysis() {
        const logInput = document.getElementById('logInput')?.value?.trim();
        
        if (!logInput) {
            this.uiManager.showStatus('Please provide security logs first', 'error');
            return;
        }

        if (this.analysisInProgress) {
            this.uiManager.showStatus('Analysis already in progress', 'warning');
            return;
        }

        if (!this.websocketManager.isConnected()) {
            this.uiManager.showStatus('Not connected to server', 'error');
            return;
        }

        this.analysisInProgress = true;
        this.uiManager.setAnalysisMode(true);
        this.uiManager.updateProgress(5, 'Starting analysis...');

        this.websocketManager.send({
            type: 'start_analysis',
            logs: logInput
        });
    }

    clearResults() {
        this.analysisInProgress = false;
        this.uiManager.clearAll();
        this.uiManager.showStatus('Results cleared', 'info');
    }

    // ============================================================================
    // WEBSOCKET EVENT HANDLERS - Called by WebSocketManager
    // ============================================================================

    onConnectionEstablished(data) {
        this.currentSessionId = data.session_id;
        this.uiManager.setConnectionStatus('connected');
        this.uiManager.showStatus('Connected to SOC system', 'success');
    }

    onConnectionLost() {
        this.uiManager.setConnectionStatus('disconnected');
        this.uiManager.showStatus('Connection lost', 'error');
    }

    onLogsRetrieved(data) {
        const logs = Array.isArray(data.logs) ? data.logs : [];
        const logText = logs.map(log => JSON.stringify(log)).join('\n');
        
        document.getElementById('logInput').value = logText;
        this.uiManager.updateLogCounter(logs.length);
        this.uiManager.showStatus(`Retrieved ${logs.length} log entries`, 'success');
        this.uiManager.updateProgress(0, 'Ready');
    }

    onTriageComplete(data) {
        this.uiManager.updateAgent('triage', 'complete', this.formatTriageOutput(data));
        this.uiManager.updateProgress(30, 'Triage complete');
    }

    onContextComplete(data) {
        this.uiManager.updateAgent('context', 'complete', this.formatContextOutput(data));
        this.uiManager.updateProgress(60, 'Context analysis complete');
    }

    onAnalysisComplete(data) {
        this.uiManager.updateAgent('analyst', 'complete', this.formatAnalysisOutput(data));
        this.uiManager.updateProgress(100, 'Analysis complete');
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
        this.uiManager.showStatus('Security analysis complete', 'success');
    }

    onApprovalRequest(data) {
        console.log('🔔 Approval request received:', data);
        
        this.uiManager.showApprovalRequest(data, (response) => {
            console.log('📤 Sending approval response:', response);
            
            const success = this.websocketManager.send({
                type: 'TextMessage',
                content: response,
                source: 'user'
            });
            
            if (success) {
                console.log('✅ Approval response sent successfully');
                // Don't hide approval here - wait for agent_status_update from backend
            } else {
                console.error('❌ Failed to send approval response');
                this.uiManager.showStatus('Failed to send response', 'error');
            }
        });
    }

    onError(data) {
        this.uiManager.showStatus(data.message, 'error');
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
    }

    // ============================================================================
    // FORMATTERS
    // ============================================================================

    formatTriageOutput(data) {
        const d = data.data;
        return `🚨 THREAT ASSESSMENT

⚠️  Priority: ${d.priority?.toUpperCase() || 'UNKNOWN'}
🎯 Threat: ${d.threat_type || 'Unknown'}
📍 Source: ${d.source_ip || 'Unknown'}
📊 Confidence: ${(d.confidence_score * 100 || 0).toFixed(1)}%

${d.brief_summary || 'Threat identified'}`;
    }

    formatContextOutput(data) {
        const d = data.data;
        return `📚 HISTORICAL CONTEXT

📊 Incidents Found: ${d.total_documents_found || 0}
🔍 Pattern Analysis: ${d.pattern_analysis || 'Analyzing...'}
📝 Confidence: ${d.confidence_assessment || 'Medium'}

Context analysis complete`;
    }

    formatAnalysisOutput(data) {
        const d = data.data;
        const actions = d.recommended_actions || [];
        return `🎯 SECURITY ANALYSIS

📋 Recommendations: ${actions.length} actions
💼 Business Impact: ${d.business_impact || 'Assessing...'}

Actions:
${actions.map((action, i) => `${i+1}. ${action}`).join('\n') || 'No actions identified'}`;
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', async () => {
    const dashboard = new SOCDashboard();
    window.socDashboard = dashboard; // For debugging
    await dashboard.initialize();
});