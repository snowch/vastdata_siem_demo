// services/ai-agents/src/static/js/main.js - CLEAN FLOW IMPLEMENTATION
// Simple, clean dashboard following the correct agent status pattern

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
        console.log('🚀 Initializing SOC Dashboard - Clean Flow');
        
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

        console.log('🚀 Starting analysis - CLEAN FLOW');
        
        this.analysisInProgress = true;
        this.uiManager.setAnalysisMode(true);
        this.uiManager.updateProgress(5, 'Starting analysis...');

        // CLEAN FLOW: Start with triage active (shows spinner)
        this.uiManager.updateAgent('triage', 'active');

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
    // WEBSOCKET EVENT HANDLERS - CLEAN FLOW IMPLEMENTATION
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

    // CLEAN FLOW: When backend completes triage processing
    onTriageComplete(data) {
        console.log('✅ Triage processing complete - showing results and requesting approval');
        
        // Stop triage spinner, show results, transition to awaiting-approval
        // The approval request will be handled separately by websocket manager
        const output = this.formatTriageOutput(data);
        this.uiManager.updateAgent('triage', 'awaiting-approval', output);
        this.uiManager.updateProgress(30, 'Triage complete - awaiting approval');
    }

    // CLEAN FLOW: When backend completes context processing  
    onContextComplete(data) {
        console.log('✅ Context processing complete - showing results and requesting approval');
        
        const output = this.formatContextOutput(data);
        this.uiManager.updateAgent('context', 'awaiting-approval', output);
        this.uiManager.updateProgress(60, 'Context complete - awaiting approval');
    }

    // CLEAN FLOW: When backend completes analyst processing
    onAnalysisComplete(data) {
        console.log('✅ Analysis processing complete - showing results and requesting approval');
        
        const output = this.formatAnalysisOutput(data);
        this.uiManager.updateAgent('analyst', 'awaiting-approval', output);
        this.uiManager.updateProgress(90, 'Analysis complete - awaiting approval');
    }

    // CLEAN FLOW: When entire workflow is complete
    onWorkflowComplete(data) {
        console.log('✅ Entire workflow complete');
        
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
        this.uiManager.updateProgress(100, 'Workflow complete');
        this.uiManager.showStatus('Security analysis workflow complete', 'success');
    }

    onError(data) {
        this.uiManager.showStatus(data.message, 'error');
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
    }

    // ============================================================================
    // OUTPUT FORMATTERS
    // ============================================================================

    formatTriageOutput(data) {
        const d = data.data;
        return `🚨 THREAT ASSESSMENT

⚠️  Priority: ${d.priority?.toUpperCase() || 'UNKNOWN'}
🎯 Threat: ${d.threat_type || 'Unknown'}
📍 Source: ${d.source_ip || 'Unknown'}
📊 Confidence: ${(d.confidence_score * 100 || 0).toFixed(1)}%

${d.brief_summary || 'Threat identified'}

✅ Triage analysis complete. Ready for approval.`;
    }

    formatContextOutput(data) {
        const d = data.data;
        return `📚 HISTORICAL CONTEXT

📊 Incidents Found: ${d.total_documents_found || 0}
🔍 Pattern Analysis: ${d.pattern_analysis || 'Analyzing...'}
📝 Confidence: ${d.confidence_assessment || 'Medium'}

✅ Context research complete. Ready for validation.`;
    }

    formatAnalysisOutput(data) {
        const d = data.data;
        const actions = d.recommended_actions || [];
        return `🎯 SECURITY ANALYSIS

📋 Recommendations: ${actions.length} actions
💼 Business Impact: ${d.business_impact || 'Assessing...'}

Actions:
${actions.map((action, i) => `${i+1}. ${action}`).join('\n') || 'No actions identified'}

✅ Analysis complete. Ready for authorization.`;
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', async () => {
    const dashboard = new SOCDashboard();
    window.socDashboard = dashboard; // For debugging
    await dashboard.initialize();
});