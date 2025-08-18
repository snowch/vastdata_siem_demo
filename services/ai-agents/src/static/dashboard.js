// Global variables using traditional JavaScript
var analysisInProgress = false;
var websocket = null;
var debugMode = false;
var debugMessages = [];
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;

// WebSocket Management with ES5 syntax
function initWebSocket() {
    var protocol = window.location.protocol == 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';
    
    debugLog('Connecting to WebSocket: ' + wsUrl);
    updateConnectionStatus('connecting');
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function(event) {
        debugLog('WebSocket connection established');
        updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;
        showStatus('Connected to SOC Analysis WebSocket', 'success');
    };
    
    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        var data = JSON.parse(event.data);
        debugLog('WebSocket message received: ' + data.type);
        handleWebSocketMessage(data);
    };
    
    websocket.onclose = function(event) {
        debugLog('WebSocket connection closed: ' + event.code + ' - ' + event.reason);
        updateConnectionStatus('disconnected');
        wsStats.connected = false;
        
        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            showStatus('Connection lost. Reconnecting... (' + reconnectAttempts + '/' + maxReconnectAttempts + ')', 'warning');
            setTimeout(function() {
                initWebSocket();
                wsStats.reconnects++;
            }, 2000 * reconnectAttempts);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
            showStatus('Connection failed. Please refresh the page.', 'error');
        }
    };
    
    websocket.onerror = function(error) {
        debugLog('WebSocket error: ' + error, 'ERROR');
        updateConnectionStatus('error');
        showStatus('WebSocket connection error', 'error');
    };
}

function sendWebSocketMessage(message) {
    if (websocket && websocket.readyState == WebSocket.OPEN) {
        websocket.send(JSON.stringify(message));
        wsStats.messages_sent++;
        debugLog('WebSocket message sent: ' + message.type);
        return true;
    } else {
        debugLog('WebSocket not connected, cannot send message', 'ERROR');
        showStatus('Not connected to server', 'error');
        return false;
    }
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'connection_established':
            debugLog('Connected with session ID: ' + data.session_id);
            break;
            
        case 'progress_update':
            handleProgressUpdate(data);
            break;
            
        case 'logs_retrieved':
            handleLogsRetrieved(data);
            break;
            
        case 'error':
            showStatus('Error: ' + data.message, 'error');
            debugLog('Server error: ' + data.message, 'ERROR');
            break;
            
        case 'pong':
            debugLog('Received pong from server');
            break;
            
        default:
            debugLog('Unknown message type: ' + data.type, 'WARNING');
    }
}

function handleProgressUpdate(data) {
    debugLog('Progress update: ' + data.status + ' - ' + data.progress_percent + '%');
    
    // Update progress bar
    updateProgress(data.progress_percent, data.status.replace('_', ' '));
    
    // Update agent statuses and outputs
    updateAgentFromProgress(data, 'triage');
    updateAgentFromProgress(data, 'context');
    updateAgentFromProgress(data, 'analyst');
    
    // Check if completed
    if (data.completed) {
        analysisInProgress = false;
        document.getElementById('analyzeBtn').disabled = false;
        
        if (data.results) {
            displayFinalResults({
                structured_findings: data.results.structured_findings,
                chroma_context: data.results.chroma_context
            });
        }
        
        if (data.error) {
            showStatus('Analysis completed with errors: ' + data.error, 'error');
        } else {
            showStatus('Multi-agent analysis completed successfully!', 'success');
        }
        
        updateProgress(0, 'Ready');
    }
}

function handleLogsRetrieved(data) {
    var logs = data.logs;
    var logCount = Array.isArray(logs) ? logs.length : 'unknown';
    debugLog('Received ' + logCount + ' logs from server');
    
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
    showStatus(data.message || 'Logs retrieved successfully!', 'success');
}

function updateConnectionStatus(status) {
    var indicator = document.getElementById('connectionIndicator');
    var statusText = document.getElementById('connectionStatus');
    
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

// Debug Mode Functions
function toggleDebugMode() {
    debugMode = !debugMode;
    var toggle = document.getElementById('debugToggle');
    var panel = document.getElementById('debugPanel');
    
    if (debugMode) {
        toggle.textContent = '🔧 Debug ON';
        toggle.classList.add('debug-mode');
        panel.style.display = 'block';
        debugLog('Debug mode enabled');
        showStatus('Debug mode enabled - detailed WebSocket logging active', 'info');
    } else {
        toggle.textContent = '🔧 Debug Mode';
        toggle.classList.remove('debug-mode');
        panel.style.display = 'none';
        showStatus('Debug mode disabled', 'info');
    }
}

function debugLog(message, level) {
    if (typeof level == 'undefined') level = 'INFO';
    if (!debugMode) return;
    
    var timestamp = new Date().toISOString();
    var logEntry = '[' + timestamp + '] [' + level + '] ' + message;
    debugMessages.push(logEntry);
    
    var debugLogElement = document.getElementById('debugLog');
    debugLogElement.textContent = debugMessages.slice(-100).join('\n');
    debugLogElement.scrollTop = debugLogElement.scrollHeight;
    
    console.log(logEntry);
}

function clearDebugLog() {
    debugMessages = [];
    document.getElementById('debugLog').textContent = 'Debug log cleared.';
}

function exportDebugLog() {
    var blob = new Blob([debugMessages.join('\n')], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'soc-websocket-debug-' + new Date().toISOString().slice(0, 19) + '.log';
    a.click();
    URL.revokeObjectURL(url);
    debugLog('Debug log exported');
}

function showWebSocketStats() {
    var stats = 'WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection');
    
    debugLog(stats);
    showStatus('WebSocket stats logged to debug console', 'info');
}

function testConnection() {
    if (sendWebSocketMessage({ type: 'ping' })) {
        showStatus('Ping sent to server', 'info');
    }
}

// Enhanced log counter
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
    
    document.getElementById('logCounter').textContent = eventCount + ' events';
    debugLog('Log counter updated: ' + eventCount + ' events');
}

function retrieveLogs() {
    showStatus('Retrieving logs via WebSocket...', 'info');
    updateProgress(10, 'Fetching logs...');
    debugLog('Requesting log retrieval via WebSocket');

    if (sendWebSocketMessage({ type: 'retrieve_logs' })) {
        // Response will be handled by WebSocket message handler
    } else {
        showStatus('Failed to send log retrieval request', 'error');
        updateProgress(0, 'Error');
    }
}

function startAnalysis() {
    var logInput = document.getElementById('logInput').value.trim();
    if (!logInput) {
        showStatus('Please provide security logs before starting analysis.', 'error');
        return;
    }

    if (analysisInProgress) {
        showStatus('Analysis already in progress...', 'warning');
        return;
    }

    if (!websocket || websocket.readyState != WebSocket.OPEN) {
        showStatus('Not connected to server. Please refresh the page.', 'error');
        return;
    }

    debugLog('Starting WebSocket analysis workflow');
    analysisInProgress = true;
    document.getElementById('analyzeBtn').disabled = true;
    resetAgentStates();
    hideFindings();

    showStatus('Starting multi-agent analysis via WebSocket...', 'info');
    updateProgress(5, 'Initializing agents...');

    if (sendWebSocketMessage({ 
        type: 'start_analysis', 
        logs: logInput 
    })) {
        debugLog('Analysis request sent via WebSocket');
    } else {
        analysisInProgress = false;
        document.getElementById('analyzeBtn').disabled = false;
        updateProgress(0, 'Error');
    }
}

function updateAgentFromProgress(progress, agentType) {
    var agentOutputs = progress.agent_outputs[agentType] || [];
    var currentAgent = progress.current_agent;
    
    // Update agent status based on progress
    if (currentAgent == agentType && !progress.completed) {
        updateAgentStatus(agentType, 'active');
        showAgentSpinner(agentType, true);
        document.getElementById(agentType + 'Card').classList.add('active');
    } else if (agentOutputs.length > 0 || progress.completed) {
        updateAgentStatus(agentType, 'complete');
        showAgentSpinner(agentType, false);
        document.getElementById(agentType + 'Card').classList.remove('active');
    }
    
    // Update agent output with latest messages
    if (agentOutputs.length > 0) {
        var latestOutput = agentOutputs[agentOutputs.length - 1];
        var timestamp = new Date(latestOutput.timestamp).toLocaleTimeString();
        showAgentOutput(agentType, '[' + timestamp + '] ' + latestOutput.message);
    }
}

function displayFinalResults(results) {
    debugLog('Displaying final analysis results');
    var panel = document.getElementById('findingsPanel');
    var content = document.getElementById('findingsContent');
    
    // Extract priority from structured findings
    var priority = 'medium';
    if (results.structured_findings && results.structured_findings.priority_threat) {
        var threatPriority = results.structured_findings.priority_threat.priority;
        if (threatPriority) {
            priority = threatPriority.toLowerCase();
        }
    }
    
    // Set priority indicator
    var priorityElement = document.getElementById('priorityIndicator');
    priorityElement.textContent = priority.toUpperCase();
    priorityElement.className = 'priority-indicator priority-' + priority;
    
    // Create findings cards from structured data
    var findings = [];
    
    if (results.structured_findings.priority_threat) {
        var threat = results.structured_findings.priority_threat;
        findings.push({
            title: '🚨 Priority Threat',
            content: (threat.threat_type || 'Unknown threat') + ' detected from ' + 
                    (threat.source_ip || 'unknown source') + '. ' + 
                    (threat.brief_summary || 'No summary available.')
        });
        debugLog('Priority threat identified: ' + threat.threat_type + ' from ' + threat.source_ip);
    }
    
    if (results.chroma_context && !results.chroma_context.error) {
        var contextCount = results.chroma_context.documents ? results.chroma_context.documents.length : 0;
        findings.push({
            title: '📚 Historical Context',
            content: 'Found ' + contextCount + ' related historical incidents to provide context for this analysis.'
        });
        debugLog('Historical context found: ' + contextCount + ' related incidents');
    }
    
    if (results.structured_findings.detailed_analysis) {
        var analysis = results.structured_findings.detailed_analysis;
        var actionCount = analysis.recommended_actions ? analysis.recommended_actions.length : 0;
        findings.push({
            title: '🎯 Analysis Complete',
            content: 'Deep analysis completed with ' + actionCount + ' recommended actions. Business impact: ' + 
                    (analysis.business_impact || 'Under assessment') + '.'
        });
        debugLog('Detailed analysis completed: ' + actionCount + ' recommendations');
    }
    
    // Fallback if no structured findings
    if (findings.length == 0) {
        findings.push({
            title: '✅ Analysis Complete',
            content: 'Multi-agent analysis completed successfully. Check individual agent outputs above for detailed findings and recommendations.'
        });
    }
    
    content.innerHTML = findings.map(function(finding) {
        return '<div class="finding-card">' +
            '<h4>' + finding.title + '</h4>' +
            '<p>' + finding.content + '</p>' +
            '</div>';
    }).join('');
    
    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth' });
    debugLog('Final results panel displayed');
}

function showStatus(message, type) {
    var toastContainer = getOrCreateToastContainer();
    var toast = createToast(message, type);
    toastContainer.appendChild(toast);
    
    setTimeout(function() {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);
    
    debugLog('Status: ' + message, type.toUpperCase());
    console.log('[' + type.toUpperCase() + '] ' + message);
}

function getOrCreateToastContainer() {
    var container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}

function createToast(message, type) {
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    return toast;
}

function updateAgentStatus(agent, status) {
    var element = document.getElementById(agent + 'Status');
    element.className = 'status-badge status-' + status;
    element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    debugLog('Agent ' + agent + ' status updated to: ' + status);
}

function showAgentOutput(agent, text) {
    document.getElementById(agent + 'Output').textContent = text;
    debugLog('Agent ' + agent + ' output updated');
}

function showAgentSpinner(agent, show) {
    var spinner = document.getElementById(agent + 'Spinner');
    var output = document.getElementById(agent + 'Output');
    
    if (show) {
        spinner.style.display = 'flex';
        output.style.opacity = '0.3';
    } else {
        spinner.style.display = 'none';
        output.style.opacity = '1';
    }
}

function updateProgress(percent, statusText) {
    document.getElementById('progressBar').style.width = percent + '%';
    var progressTextElement = document.getElementById('progressText');
    if (statusText) {
        progressTextElement.textContent = statusText;
    } else {
        progressTextElement.textContent = percent > 0 ? percent + '%' : 'Ready';
    }
}

function resetAgentStates() {
    debugLog('Resetting all agent states');
    var agents = ['triage', 'context', 'analyst'];
    var outputTexts = {
        triage: 'Waiting for analysis to begin...',
        context: 'Waiting for triage completion...',
        analyst: 'Waiting for context research...'
    };
    
    for (var i = 0; i < agents.length; i++) {
        var agent = agents[i];
        updateAgentStatus(agent, 'pending');
        showAgentSpinner(agent, false);
        document.getElementById(agent + 'Card').classList.remove('active');
        showAgentOutput(agent, outputTexts[agent]);
    }
}

function hideFindings() {
    document.getElementById('findingsPanel').style.display = 'none';
}

function clearResults() {
    debugLog('Clearing all results and resetting dashboard');
    document.getElementById('logInput').value = '';
    document.getElementById('logCounter').textContent = '0 events';
    resetAgentStates();
    hideFindings();
    updateProgress(0, 'Ready');
    analysisInProgress = false;
    document.getElementById('analyzeBtn').disabled = false;
    
    // Clear WebSocket stats
    wsStats.messages_sent = 0;
    wsStats.messages_received = 0;
    showStatus('Dashboard cleared and reset', 'info');
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.shiftKey && e.key == 'D') {
        e.preventDefault();
        toggleDebugMode();
    }
    
    if (e.ctrlKey && e.shiftKey && e.key == 'C') {
        e.preventDefault();
        clearResults();
    }
    
    if (e.ctrlKey && e.shiftKey && e.key == 'A') {
        e.preventDefault();
        if (!analysisInProgress) {
            startAnalysis();
        }
    }
});

// Monitor textarea changes for log counter
document.getElementById('logInput').addEventListener('input', function(e) {
    updateLogCounter(e.target.value);
});

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    resetAgentStates();
    initWebSocket();
    
    // Welcome message
    showStatus('Welcome to SOC Agent WebSocket Dashboard! Connecting to server...', 'info');
    
    // Show keyboard shortcuts in console
    setTimeout(function() {
        console.log('💡 SOC Dashboard Shortcuts:');
        console.log('  • Ctrl+Shift+D → Toggle debug mode');
        console.log('  • Ctrl+Shift+A → Start analysis');
        console.log('  • Ctrl+Shift+C → Clear results');
        debugLog('WebSocket dashboard initialized successfully');
    }, 2000);
});

// Handle page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close(1000, 'Page unloading');
    }
});
