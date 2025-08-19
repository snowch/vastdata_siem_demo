// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';
import * as approvalWorkflow from './approvalWorkflow.js';

// Progress and Agent Status Updates
var analysisInProgress = false;

function handleProgressUpdate(data) {
    debugLogger.debugLog('Progress update received - Status: ' + data.status + ', Progress: ' + data.progress_percent + '%');
    
    // Add detailed logging for debugging
    console.log('Full progress update data:', data);
    
    // Handle approval-specific statuses
    if (data.status === 'awaiting_approval') {
        debugLogger.debugLog('Status is awaiting_approval - should be handled by approval_request message');
        return;
    } else if (data.status === 'approved') {
        debugLogger.debugLog('Status is approved - updating triage to complete');
        ui.updateAgentStatus('triage', 'complete');
        ui.showAgentOutput('triage', 'Analysis approved. Continuing to context research...');
    } else if (data.status === 'rejected') {
        debugLogger.debugLog('Status is rejected - stopping analysis');
        analysisInProgress = false;
        document.getElementById('analyzeBtn').disabled = false;
        ui.updateAgentStatus('triage', 'rejected');
        ui.showStatus('Analysis rejected by user', 'warning');
        return;
    } else {
        debugLogger.debugLog('Status is: ' + data.status + ' - processing normally');
    }
    
    // Update progress bar
    ui.updateProgress(data.progress_percent, data.status.replace('_', ' '));
    
    // Update agent statuses and outputs
    updateAgentFromProgress(data, 'triage');
    updateAgentFromProgress(data, 'context');
    updateAgentFromProgress(data, 'analyst');
    
    // Check if completed
    if (data.completed) {
        debugLogger.debugLog('Analysis completed - cleaning up');
        analysisInProgress = false;
        approvalWorkflow.setAwaitingApproval(false);
        document.getElementById('analyzeBtn').disabled = false;
        approvalWorkflow.hideApprovalButtons();
        
        if (data.results) {
            if (data.results.was_rejected) {
                debugLogger.debugLog('Results indicate analysis was rejected');
                ui.showStatus('Analysis was rejected by user', 'warning');
                ui.updateProgress(100, 'Rejected');
            } else {
                debugLogger.debugLog('Analysis completed successfully - displaying results');
                ui.displayFinalResults({
                    structured_findings: data.results.structured_findings,
                    chroma_context: data.results.chroma_context
                });
                ui.showStatus('Multi-agent analysis completed successfully!', 'success');
            }
        }
        
        if (data.error) {
            debugLogger.debugLog('Analysis completed with error: ' + data.error);
            ui.showStatus('Analysis completed with errors: ' + data.error, 'error');
        }
        
        if (!data.results || !data.results.was_rejected) {
            ui.updateProgress(0, 'Ready');
        }
    }
}

function handleLogsRetrieved(data) {
    var logs = data.logs;
    var logCount = Array.isArray(logs) ? logs.length : 'unknown';
    debugLogger.debugLog('Received ' + logCount + ' logs from server');
    
    // Convert logs to flattened JSON format
    var logText = '';
    if (Array.isArray(logs)) {
        logText = logs.map(function(record) {
            return JSON.stringify(record);
        }).join('\n');
    } else {
        logText = JSON.stringify(logs);
    }
    
    document.getElementById('logInput').value = logText;
    updateLogCounter(logText);
    ui.showStatus(data.message || 'Logs retrieved successfully!', 'success');
}

function updateConnectionStatus(status) {
    var indicator = document.getElementById('connectionIndicator');
    var statusText = document.getElementById('connectionStatus');
    
    if (!indicator || !statusText) {
        debugLogger.debugLog('Connection status elements not found', 'WARNING');
        return;
    }
    
    indicator.className = 'status-indicator';
    
    switch (status) {
        case 'connected':
            indicator.classList.add('connected');
            statusText.textContent = 'Connected';
            break;
        case 'connecting':
            indicator.classList.add('connecting');
            statusText.textContent = 'Connecting...';
            break;
        case 'disconnected':
            statusText.textContent = 'Disconnected';
            break;
        case 'error':
            statusText.textContent = 'Error';
            break;
    }
}

function updateLogCounter(logData) {
    var eventCount = 0;
    try {
        if (typeof logData == 'string') {
            var lines = logData.split('\n').filter(function(line) {
                return line.trim();
            });
            eventCount = lines.filter(function(line) {
                var trimmed = line.trim();
                return trimmed.charAt(0) == '{' && trimmed.charAt(trimmed.length - 1) == '}';
            }).length;
            
            if (eventCount == 0 && lines.length > 0) {
                eventCount = lines.length;
            }
        } else if (Array.isArray(logData)) {
            eventCount = logData.length;
        }
    } catch (e) {
        eventCount = logData.split('\n').filter(function(line) {
            return line.trim();
        }).length;
    }
    
    var logCounter = document.getElementById('logCounter');
    if (logCounter) {
        logCounter.textContent = eventCount + ' events';
    }
    debugLogger.debugLog('Log counter updated: ' + eventCount + ' events');
}

function retrieveLogs() {
    debugLogger.debugLog('Retrieve logs button clicked');
    ui.showStatus('Retrieving logs via WebSocket...', 'info');
    ui.updateProgress(10, 'Fetching logs...');
    debugLogger.debugLog('Requesting log retrieval via WebSocket');

    if (websocket.sendWebSocketMessage({ type: 'retrieve_logs' })) {
        debugLogger.debugLog('Log retrieval request sent successfully');
    } else {
        debugLogger.debugLog('Failed to send log retrieval request', 'ERROR');
        ui.showStatus('Failed to send log retrieval request', 'error');
        ui.updateProgress(0, 'Error');
    }
}

function startAnalysis() {
    debugLogger.debugLog('Start analysis button clicked');
    
    var logInput = document.getElementById('logInput').value.trim();
    if (!logInput) {
        debugLogger.debugLog('No logs provided - showing error', 'WARNING');
        ui.showStatus('Please provide security logs before starting analysis.', 'error');
        return;
    }

    if (analysisInProgress) {
        debugLogger.debugLog('Analysis already in progress - ignoring request', 'WARNING');
        ui.showStatus('Analysis already in progress...', 'warning');
        return;
    }

    var ws = websocket.getWebSocket();
    if (!ws || ws.readyState != WebSocket.OPEN) {
        debugLogger.debugLog('WebSocket not connected - cannot start analysis', 'ERROR');
        ui.showStatus('Not connected to server. Please refresh the page.', 'error');
        return;
    }

    debugLogger.debugLog('Starting WebSocket analysis workflow');
    
    // Set initial state
    analysisInProgress = true;
    approvalWorkflow.setAwaitingApproval(false);
    
    // Update UI
    document.getElementById('analyzeBtn').disabled = true;
    ui.resetAgentStates();
    ui.hideFindings();
    approvalWorkflow.hideApprovalButtons();

    ui.showStatus('Starting multi-agent analysis with approval workflow...', 'info');
    ui.updateProgress(5, 'Initializing agents...');

    var message = { 
        type: 'start_analysis', 
        logs: logInput 
    };
    
    debugLogger.debugLog('Sending analysis request: ' + JSON.stringify({type: message.type, logsLength: logInput.length}));
    
    if (websocket.sendWebSocketMessage(message)) {
        debugLogger.debugLog('Analysis request sent successfully via WebSocket');
    } else {
        debugLogger.debugLog('Failed to send analysis request', 'ERROR');
        analysisInProgress = false;
        document.getElementById('analyzeBtn').disabled = false;
        ui.updateProgress(0, 'Error');
    }
}

function updateAgentFromProgress(progress, agentType) {
    var agentOutputs = progress.agent_outputs[agentType] || [];
    var currentAgent = progress.current_agent;
    
    debugLogger.debugLog('Updating agent ' + agentType + ' - Current: ' + currentAgent + ', Outputs: ' + agentOutputs.length);
    
    // Update agent status based on progress
    if (currentAgent == agentType && !progress.completed) {
        debugLogger.debugLog('Setting agent ' + agentType + ' to active');
        ui.updateAgentStatus(agentType, 'active');
        ui.showAgentSpinner(agentType, true);
        var card = document.getElementById(agentType + 'Card');
        if (card) {
            card.classList.add('active');
        }
    } else if (agentOutputs.length > 0 || progress.completed) {
        if (agentType !== 'triage' || !approvalWorkflow.getAwaitingApproval()) {
            debugLogger.debugLog('Setting agent ' + agentType + ' to complete');
            ui.updateAgentStatus(agentType, 'complete');
            ui.showAgentSpinner(agentType, false);
            var card = document.getElementById(agentType + 'Card');
            if (card) {
                card.classList.remove('active');
            }
        }
    }
    
    // Update agent output with latest messages
    if (agentOutputs.length > 0) {
        var latestOutput = agentOutputs[agentOutputs.length - 1];
        var timestamp = new Date(latestOutput.timestamp).toLocaleTimeString();
        if (agentType !== 'triage' || !approvalWorkflow.getAwaitingApproval()) {
            ui.showAgentOutput(agentType, '[' + timestamp + '] ' + latestOutput.message);
        }
    }
}

function getAnalysisInProgress() {
    return analysisInProgress;
}

function setAnalysisInProgress(value) {
    debugLogger.debugLog('Setting analysis in progress to: ' + value);
    analysisInProgress = value;
}

export { 
    handleProgressUpdate, 
    handleLogsRetrieved, 
    updateConnectionStatus, 
    updateLogCounter, 
    retrieveLogs, 
    startAnalysis, 
    updateAgentFromProgress,
    getAnalysisInProgress,
    setAnalysisInProgress
};