// services/ai-agents/src/static/js/progressManager.js - FIRST UPDATE
// Remove complex handleProgressUpdate function - keep everything else the same

import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';

// Simple analysis state tracking
var analysisInProgress = false;

// REMOVED: handleProgressUpdate function - no longer needed
// The specific real-time messages in websocket.js will handle updates instead

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
    
    // Update UI
    document.getElementById('analyzeBtn').disabled = true;
    ui.resetAgentStates();
    ui.hideFindings();
    
    // KEEP: Dynamic import to avoid circular dependency
    import('./approvalWorkflow.js').then(approvalWorkflow => {
        approvalWorkflow.hideApprovalButtons();
    });

    ui.showStatus('Starting multi-agent analysis workflow...', 'info');
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

// REMOVED: updateAgentFromProgress function - no longer needed

function getAnalysisInProgress() {
    return analysisInProgress;
}

function setAnalysisInProgress(value) {
    debugLogger.debugLog('Setting analysis in progress to: ' + value);
    analysisInProgress = value;
}

export { 
    handleLogsRetrieved, 
    updateConnectionStatus, 
    updateLogCounter, 
    retrieveLogs, 
    startAnalysis,
    getAnalysisInProgress,
    setAnalysisInProgress
    // REMOVED: handleProgressUpdate, updateAgentFromProgress exports
};