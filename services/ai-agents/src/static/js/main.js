// services/ai-agents/src/static/js/main.js - CLEAN SIMPLIFIED FLOW
// Simple dashboard with predictable agent flow: active → awaiting-decision → complete

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
    // USER ACTIONS - Simple API
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

        // STEP 1: Start triage (active state with spinner)
        this.uiManager.setAgentActive('triage');

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
    // WEBSOCKET EVENT HANDLERS - Clean Simple Flow
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

    // STEP 2: Backend completed triage → show results + approval
    onTriageResults(data) {
        console.log('✅ Triage results received');
        
        const output = this.formatTriageOutput(data);
        
        // Show results and approval UI
        this.uiManager.setAgentAwaitingDecision('triage', output, (response) => {
            this.websocketManager.sendApprovalResponse('triage', response);
        });
        
        this.uiManager.updateProgress(30, 'Triage complete - awaiting approval');
    }

    // STEP 3: Backend completed context → show results + approval
    onContextResults(data) {
        console.log('✅ Context results received');
        
        const output = this.formatContextOutput(data);
        
        // Show results and approval UI
        this.uiManager.setAgentAwaitingDecision('context', output, (response) => {
            this.websocketManager.sendApprovalResponse('context', response);
        });
        
        this.uiManager.updateProgress(60, 'Context complete - awaiting approval');
    }

    // STEP 4: Backend completed analyst → show results + approval
    onAnalystResults(data) {
        console.log('✅ Analyst results received');
        
        const output = this.formatAnalysisOutput(data);
        
        // Show results and approval UI
        this.uiManager.setAgentAwaitingDecision('analyst', output, (response) => {
            this.websocketManager.sendApprovalResponse('analyst', response);
        });
        
        this.uiManager.updateProgress(90, 'Analysis complete - awaiting approval');
    }

    // STEP 5: Entire workflow complete
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
    // OUTPUT FORMATTERS - Same as before
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