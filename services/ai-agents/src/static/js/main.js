// UPDATED: src/static/js/main.js - FIX FINDINGS TIMING
// Only show findings panel AFTER final analyst approval

import { WebSocketManager } from './modules/websocket-manager.js';
import { UIManager } from './modules/ui-manager.js';
import { EventManager } from './modules/event-manager.js';
import { DebugManager } from './modules/debug-manager.js';
import { FindingsManager } from './modules/findings-manager.js';

class SOCDashboard {
    constructor() {
        this.websocketManager = new WebSocketManager();
        this.uiManager = new UIManager();
        this.eventManager = new EventManager();
        this.debugManager = new DebugManager();
        this.findingsManager = new FindingsManager();
        
        this.analysisInProgress = false;
        this.currentSessionId = null;
        
        // ✅ FIX: Track workflow state more precisely
        this.workflowState = {
            triageComplete: false,
            contextComplete: false,
            analystComplete: false,
            finalApprovalGiven: false
        };
    }

    async initialize() {
        console.log('🚀 Initializing SOC Dashboard - Clean Flow with Findings');
        
        try {
            // Initialize managers in order
            await this.uiManager.initialize();
            await this.debugManager.initialize();
            await this.findingsManager.initialize();
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

        // ✅ FIX: Reset workflow state
        this.workflowState = {
            triageComplete: false,
            contextComplete: false,
            analystComplete: false,
            finalApprovalGiven: false
        };

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
        
        // Clear findings and reset state
        this.findingsManager.clearResults();
        this.findingsManager.hidePanel();
        
        // ✅ FIX: Reset workflow state
        this.workflowState = {
            triageComplete: false,
            contextComplete: false,
            analystComplete: false,
            finalApprovalGiven: false
        };
        
        this.uiManager.showStatus('Results cleared', 'info');
    }

    exportResults() {
        if (this.findingsManager.hasResults()) {
            const success = this.findingsManager.exportResults('json');
            if (success) {
                this.uiManager.showStatus('Results exported successfully', 'success');
            } else {
                this.uiManager.showStatus('Export failed', 'error');
            }
        } else {
            this.uiManager.showStatus('No results to export', 'warning');
        }
    }

    // ============================================================================
    // WEBSOCKET EVENT HANDLERS - Fixed Timing
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
        
        // Store results for final display
        this.findingsManager.storeTriageResults(data.data);
        this.workflowState.triageComplete = true;
        
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
        
        // Store results for final display
        this.findingsManager.storeContextResults(data.data);
        this.workflowState.contextComplete = true;
        
        const output = this.formatContextOutput(data);
        
        // Show results and approval UI
        this.uiManager.setAgentAwaitingDecision('context', output, (response) => {
            this.websocketManager.sendApprovalResponse('context', response);
        });
        
        this.uiManager.updateProgress(60, 'Context complete - awaiting approval');
    }

    // STEP 4: Backend completed analyst → show results + approval (BUT NO FINDINGS YET!)
    onAnalystResults(data) {
        console.log('✅ Analyst results received');
        
        // Store results for final display
        this.findingsManager.storeAnalystResults(data.data);
        this.workflowState.analystComplete = true;
        
        const output = this.formatAnalysisOutput(data);
        
        // ✅ FIX: Show results and approval UI - but DON'T show findings panel yet!
        this.uiManager.setAgentAwaitingDecision('analyst', output, (response) => {
            console.log('📝 Analyst approval response:', response);
            this.workflowState.finalApprovalGiven = true;
            this.websocketManager.sendApprovalResponse('analyst', response);
        });
        
        this.uiManager.updateProgress(90, 'Analysis complete - awaiting final approval');
        
        // ✅ IMPORTANT: Do NOT show findings panel here!
        console.log('⚠️ Analyst results ready - waiting for approval before showing findings');
    }

    // STEP 5: Entire workflow complete → NOW show findings panel
    onWorkflowComplete(data) {
        console.log('✅ Entire workflow complete');
        
        // ✅ FIX: Only show findings if all approvals were given
        if (!this.workflowState.finalApprovalGiven) {
            console.warn('⚠️ Workflow marked complete but final approval not given - not showing findings');
            return;
        }
        
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
        this.uiManager.updateProgress(100, 'Workflow complete');
        
        // ✅ NOW it's safe to show consolidated findings panel
        console.log('🎯 All approvals complete - showing findings panel');
        const success = this.findingsManager.showPanel();
        
        if (success) {
            this.uiManager.showStatus('Security analysis complete - Full results displayed below', 'success');
        } else {
            this.uiManager.showStatus('Analysis complete - Error displaying results panel', 'warning');
        }
    }

    onError(data) {
        this.uiManager.showStatus(data.message, 'error');
        this.analysisInProgress = false;
        this.uiManager.setAnalysisMode(false);
        
        // Reset state on error
        this.workflowState = {
            triageComplete: false,
            contextComplete: false,
            analystComplete: false,
            finalApprovalGiven: false
        };
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

✅ Analysis complete. Ready for FINAL authorization.
⚠️ Findings panel will appear after approval.`;
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', async () => {
    const dashboard = new SOCDashboard();
    window.socDashboard = dashboard; // For debugging
    await dashboard.initialize();
});


// ============================================================================
// DEBUGGING: Add this to help identify the timing issue
// ============================================================================

// Add this debug info to the console
console.log(`
🔧 DEBUG: Findings Panel Timing Fix Applied
- Findings will only show AFTER final analyst approval
- Check console for: "🎯 All approvals complete - showing findings panel"
- If findings show too early, check WebSocket message routing
`);