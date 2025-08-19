// Updated websocket.js to handle real-time agent streaming

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// WebSocket Management and Real-time Streaming
var websocket = null;
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;
var currentSessionId = null;

// Real-time agent output buffers
var agentOutputBuffers = {
    triage: [],
    context: [],
    analyst: []
};

function initWebSocket() {
    console.log('initWebSocket called with real-time streaming support');
    var protocol = window.location.protocol == 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';

    debugLogger.debugLog('Connecting to Real-time WebSocket: ' + wsUrl);
    progressManager.updateConnectionStatus('connecting');

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function(event) {
        debugLogger.debugLog('Real-time WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;
        ui.showStatus('Connected to Real-time SOC Analysis WebSocket', 'success');
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        var data = JSON.parse(event.data);
        debugLogger.debugLog('Real-time WebSocket message received - Type: ' + data.type);
        console.log('Full real-time WebSocket message:', data);
        handleRealtimeWebSocketMessage(data);
    };

    websocket.onclose = function(event) {
        debugLogger.debugLog('Real-time WebSocket connection closed: ' + event.code + ' - ' + event.reason);
        progressManager.updateConnectionStatus('disconnected');
        wsStats.connected = false;

        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            ui.showStatus('Connection lost. Reconnecting... (' + reconnectAttempts + '/' + maxReconnectAttempts + ')', 'warning');
            setTimeout(function() {
                initWebSocket();
                wsStats.reconnects++;
            }, 2000 * reconnectAttempts);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
            ui.showStatus('Connection failed. Please refresh the page.', 'error');
        }
    };

    websocket.onerror = function(error) {
        debugLogger.debugLog('Real-time WebSocket error: ' + error, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('Real-time WebSocket connection error', 'error');
    };
}

function handleRealtimeWebSocketMessage(data) {
    debugLogger.debugLog('Handling real-time WebSocket message type: ' + data.type);
    
    switch (data.type) {
        case 'connection_established':
            currentSessionId = data.session_id;
            debugLogger.debugLog('Connected with session ID: ' + data.session_id);
            
            // Show real-time features notification
            ui.showStatus('Real-time streaming enabled - agent outputs will appear live', 'info');
            break;

        case 'real_time_agent_output':
            // Handle real-time agent output as it arrives
            handleRealtimeAgentOutput(data);
            break;

        case 'priority_findings_update':
            // Handle immediate priority findings
            handlePriorityFindingsUpdate(data);
            break;

        case 'context_results_update':
            // Handle immediate context results
            handleContextResultsUpdate(data);
            break;

        case 'detailed_analysis_update':
            // Handle immediate detailed analysis
            handleDetailedAnalysisUpdate(data);
            break;

        case 'analysis_workflow_complete':
            // Handle final workflow completion
            handleWorkflowComplete(data);
            break;

        case 'workflow_rejected':
            // Handle workflow rejection
            handleWorkflowRejected(data);
            break;

        case 'real_time_error':
            // Handle real-time errors
            debugLogger.debugLog('Real-time error: ' + data.content, 'ERROR');
            ui.showStatus('Real-time error: ' + data.content, 'error');
            break;

        case 'UserInputRequestedEvent':
            // Handle AutoGen-style user input request (approval request)
            debugLogger.debugLog('User input requested (approval request) - Real-time');
            console.log('Real-time user input request data:', data);
            approvalWorkflow.handleApprovalRequest(data);
            break;

        case 'progress_update':
            // Handle traditional progress updates (still needed for overall progress)
            debugLogger.debugLog('Progress update received - Status: ' + data.status);
            console.log('Progress update data:', data);
            progressManager.handleProgressUpdate(data);
            break;

        case 'logs_retrieved':
            debugLogger.debugLog('Logs retrieved message received');
            progressManager.handleLogsRetrieved(data);
            break;

        case 'error':
            debugLogger.debugLog('Server error received: ' + data.message, 'ERROR');
            console.log('Server error data:', data);
            ui.showStatus('Error: ' + (data.message || data.content || 'Unknown error'), 'error');
            break;

        case 'pong':
            debugLogger.debugLog('Received pong from server');
            break;

        default:
            debugLogger.debugLog('Unknown real-time message type: ' + data.type, 'WARNING');
            console.log('Unknown real-time message data:', data);
    }
}

function handleRealtimeAgentOutput(data) {
    var agent = data.agent;
    var content = data.content;
    var timestamp = data.timestamp;
    var source = data.source;
    
    // Skip if agent type is unknown or if this is an initial system message
    if (!agent || agent === 'unknown' || !agentOutputBuffers[agent]) {
        debugLogger.debugLog('Skipping unknown or invalid agent output: ' + agent);
        return;
    }
    
    // Skip very long messages that are likely initial task descriptions
    if (content.length > 1500) {
        debugLogger.debugLog('Skipping long initial message from: ' + agent);
        return;
    }
    
    // Skip messages that look like task descriptions
    if (content.includes('ENHANCED SECURITY LOG ANALYSIS') || 
        content.includes('MULTI-STAGE WORKFLOW') ||
        content.includes('TriageSpecialist: Begin initial triage')) {
        debugLogger.debugLog('Skipping task description message from: ' + agent);
        return;
    }
    
    debugLogger.debugLog('Real-time output from ' + agent + ': ' + content.substring(0, 100) + '...');
    
    // Add to buffer for this agent
    agentOutputBuffers[agent].push({
        content: content,
        timestamp: timestamp,
        source: source
    });
    
    // Keep only last 20 messages per agent to prevent memory issues
    if (agentOutputBuffers[agent].length > 20) {
        agentOutputBuffers[agent].shift();
    }
    
    // Update agent status to active if not already
    ui.updateAgentStatus(agent, 'active');
    ui.showAgentSpinner(agent, true);
    
    // Format timestamp for display
    var displayTime = new Date(timestamp).toLocaleTimeString();
    
    // Update agent output with streaming content
    var formattedContent = '[' + displayTime + '] ' + content;
    
    // Append to existing output instead of replacing
    var outputElement = document.getElementById(agent + 'Output');
    if (outputElement) {
        var existingContent = outputElement.textContent;
        
        // If this is the first real-time message, clear the "waiting" text
        if (existingContent.includes('Waiting for') || existingContent.includes('waiting')) {
            outputElement.textContent = formattedContent;
        } else {
            // Append new content
            outputElement.textContent = existingContent + '\n\n' + formattedContent;
        }
        
        // Auto-scroll to bottom
        outputElement.scrollTop = outputElement.scrollHeight;
        
        // Add visual indicator for new content
        var agentCard = document.getElementById(agent + 'Card');
        if (agentCard) {
            agentCard.classList.add('active');
            
            // Add a brief flash effect for new content
            agentCard.style.transform = 'scale(1.02)';
            setTimeout(function() {
                agentCard.style.transform = '';
            }, 200);
        }
    }
    
    // Show notification for important messages
    if (content.toLowerCase().includes('priority') || 
        content.toLowerCase().includes('critical') || 
        content.toLowerCase().includes('complete')) {
        ui.showStatus(agent.charAt(0).toUpperCase() + agent.slice(1) + ': ' + content.substring(0, 80) + '...', 'info');
    }
}

function handlePriorityFindingsUpdate(data) {
    debugLogger.debugLog('Priority findings update received in real-time');
    var findings = data.data;
    
    if (findings && findings.threat_type && findings.source_ip) {
        var priority = findings.priority || 'medium';
        var threatType = findings.threat_type;
        var sourceIp = findings.source_ip;
        
        // Show immediate notification
        ui.showStatus('🚨 Priority ' + priority.toUpperCase() + ' threat: ' + threatType + ' from ' + sourceIp, 'warning');
        
        // Update triage agent to complete
        ui.updateAgentStatus('triage', 'complete');
        ui.showAgentSpinner('triage', false);
        
        // Show findings preview in triage output
        var triageOutput = document.getElementById('triageOutput');
        if (triageOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var findingsText = '[' + timestamp + '] ✅ PRIORITY FINDINGS:\n' +
                '🎯 Threat: ' + threatType + '\n' +
                '📍 Source: ' + sourceIp + '\n' +
                '⚠️ Priority: ' + priority.toUpperCase() + '\n' +
                '📊 Confidence: ' + (findings.confidence_score || 0.8) + '\n' +
                '📈 Events: ' + (findings.event_count || 'unknown');
            
            triageOutput.textContent += '\n\n' + findingsText;
            triageOutput.scrollTop = triageOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(40, 'Priority threat identified');
        
        debugLogger.debugLog('Priority findings processed: ' + threatType + ' from ' + sourceIp);
    }
}

function handleContextResultsUpdate(data) {
    debugLogger.debugLog('Context results update received in real-time');
    var results = data.data;
    
    if (results && results.documents) {
        var documentCount = results.documents.length;
        
        // Show immediate notification
        ui.showStatus('🔎 Found ' + documentCount + ' related historical incidents', 'info');
        
        // Update context agent to complete
        ui.updateAgentStatus('context', 'complete');
        ui.showAgentSpinner('context', false);
        
        // Show context preview in context output
        var contextOutput = document.getElementById('contextOutput');
        if (contextOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var contextText = '[' + timestamp + '] ✅ CONTEXT RESEARCH:\n' +
                '📚 Found: ' + documentCount + ' related incidents\n' +
                '🔍 Sources: ChromaDB historical analysis\n' +
                '📊 Relevance: High similarity patterns\n' +
                '✅ Status: Ready for deep analysis';
            
            contextOutput.textContent += '\n\n' + contextText;
            contextOutput.scrollTop = contextOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(70, 'Historical context analyzed');
        
        debugLogger.debugLog('Context results processed: ' + documentCount + ' documents');
    }
}

function handleDetailedAnalysisUpdate(data) {
    debugLogger.debugLog('Detailed analysis update received in real-time');
    var analysis = data.data;
    
    if (analysis && analysis.recommended_actions) {
        var actionCount = analysis.recommended_actions.length;
        
        // Show immediate notification
        ui.showStatus('👨‍💼 Analysis complete with ' + actionCount + ' recommendations', 'success');
        
        // Update analyst agent to complete
        ui.updateAgentStatus('analyst', 'complete');
        ui.showAgentSpinner('analyst', false);
        
        // Show analysis preview in analyst output
        var analystOutput = document.getElementById('analystOutput');
        if (analystOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var analysisText = '[' + timestamp + '] ✅ DEEP ANALYSIS COMPLETE:\n' +
                '🎯 Threat Assessment: ' + (analysis.threat_assessment?.severity || 'unknown') + '\n' +
                '📋 Recommendations: ' + actionCount + ' actions\n' +
                '💼 Business Impact: ' + (analysis.business_impact || 'Under review') + '\n' +
                '🔒 Status: Awaiting authorization';
            
            analystOutput.textContent += '\n\n' + analysisText;
            analystOutput.scrollTop = analystOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(95, 'Analysis complete - awaiting authorization');
        
        debugLogger.debugLog('Detailed analysis processed: ' + actionCount + ' recommendations');
    }
}

function handleWorkflowComplete(data) {
    debugLogger.debugLog('Real-time workflow completion received');
    
    if (data.was_rejected) {
        ui.showStatus('❌ Analysis workflow was rejected by user', 'warning');
        ui.updateProgress(100, 'Workflow rejected');
    } else {
        ui.showStatus('🎉 Multi-agent analysis completed successfully!', 'success');
        ui.updateProgress(100, 'Analysis complete');
        
        // Enable the analyze button again
        var analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
        
        // Show final results if available
        setTimeout(function() {
            showRealtimeResultsSummary();
        }, 1000);
    }
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    approvalWorkflow.setAwaitingApproval(false);
}

function handleWorkflowRejected(data) {
    debugLogger.debugLog('Real-time workflow rejection received');
    
    ui.showStatus('❌ ' + (data.content || 'Analysis workflow rejected'), 'error');
    ui.updateProgress(100, 'Rejected');
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    approvalWorkflow.setAwaitingApproval(false);
    
    // Enable the analyze button again
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function showRealtimeResultsSummary() {
    debugLogger.debugLog('Showing real-time results summary');
    
    // Create a summary from the real-time data we've collected
    var findings = [];
    
    // Check what we learned from each agent
    var triageBuffer = agentOutputBuffers.triage || [];
    var contextBuffer = agentOutputBuffers.context || [];
    var analystBuffer = agentOutputBuffers.analyst || [];
    
    if (triageBuffer.length > 0) {
        findings.push({
            title: '🚨 Triage Results',
            content: 'Initial threat assessment completed with priority classification and source identification.'
        });
    }
    
    if (contextBuffer.length > 0) {
        findings.push({
            title: '📚 Historical Context',
            content: 'Related historical incidents found and analyzed for pattern matching and threat correlation.'
        });
    }
    
    if (analystBuffer.length > 0) {
        findings.push({
            title: '🎯 Analysis Complete',
            content: 'Deep analysis completed with actionable recommendations and business impact assessment.'
        });
    }
    
    // Show the findings
    if (findings.length > 0) {
        ui.displayFinalResults({
            structured_findings: {
                priority_threat: {
                    priority: 'high',
                    threat_type: 'Multi-stage analysis',
                    brief_summary: 'Real-time analysis completed successfully'
                }
            },
            chroma_context: {}
        });
    }
}

function clearRealtimeBuffers() {
    debugLogger.debugLog('Clearing real-time agent output buffers');
    agentOutputBuffers = {
        triage: [],
        context: [],
        analyst: []
    };
}

// Export existing functions plus new real-time ones
function sendWebSocketMessage(message) {
    if (websocket && websocket.readyState == WebSocket.OPEN) {
        var messageString = JSON.stringify(message);
        websocket.send(messageString);
        wsStats.messages_sent++;
        debugLogger.debugLog('Real-time WebSocket message sent - Type: ' + message.type);
        console.log('Sent real-time WebSocket message:', message);
        return true;
    } else {
        debugLogger.debugLog('Real-time WebSocket not connected, cannot send message - ReadyState: ' + (websocket ? websocket.readyState : 'null'), 'ERROR');
        ui.showStatus('Not connected to server', 'error');
        return false;
    }
}

function showWebSocketStats() {
    var bufferSizes = Object.keys(agentOutputBuffers).map(function(agent) {
        return agent + ': ' + agentOutputBuffers[agent].length + ' messages';
    }).join(', ');
    
    var stats = 'Real-time WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection') + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        'Real-time Buffers: ' + bufferSizes;

    debugLogger.debugLog(stats);
    console.log('Real-time WebSocket Stats:', {
        connected: wsStats.connected,
        messages_sent: wsStats.messages_sent,
        messages_received: wsStats.messages_received,
        reconnects: wsStats.reconnects,
        connection_state: websocket ? websocket.readyState : 'No connection',
        session_id: currentSessionId,
        agent_buffers: agentOutputBuffers
    });
    ui.showStatus('Real-time WebSocket stats logged to debug console', 'info');
}

function testConnection() {
    debugLogger.debugLog('Testing real-time WebSocket connection');
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        if (sendWebSocketMessage({ type: 'ping' })) {
            ui.showStatus('Ping sent to real-time server', 'info');
        }
    } else {
        debugLogger.debugLog('Cannot test connection - Real-time WebSocket not ready. State: ' + (websocket ? websocket.readyState : 'null'), 'WARNING');
        ui.showStatus('Real-time WebSocket not connected', 'warning');
    }
}

function getCurrentSessionId() {
    return currentSessionId;
}

function getWebSocket() {
    return websocket;
}

function getConnectionStats() {
    return wsStats;
}

function getAgentOutputBuffers() {
    return agentOutputBuffers;
}

// Handle page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close(1000, 'Page unloading');
    }
});

export { 
    initWebSocket, 
    sendWebSocketMessage, 
    showWebSocketStats, 
    testConnection, 
    getCurrentSessionId, 
    getWebSocket, 
    getConnectionStats,
    clearRealtimeBuffers,
    getAgentOutputBuffers
};