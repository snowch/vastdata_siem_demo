// Updated websocket.js to handle AutoGen-style messages

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// WebSocket Management and Stats
var websocket = null;
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;
var currentSessionId = null;

function initWebSocket() {
    console.log('initWebSocket called');
    var protocol = window.location.protocol == 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';

    debugLogger.debugLog('Connecting to WebSocket: ' + wsUrl);
    progressManager.updateConnectionStatus('connecting');

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function(event) {
        debugLogger.debugLog('WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;
        ui.showStatus('Connected to SOC Analysis WebSocket with Approval Workflow', 'success');
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        var data = JSON.parse(event.data);
        debugLogger.debugLog('WebSocket message received - Type: ' + data.type);
        console.log('Full WebSocket message:', data); // Add detailed logging
        handleWebSocketMessage(data);
    };

    websocket.onclose = function(event) {
        debugLogger.debugLog('WebSocket connection closed: ' + event.code + ' - ' + event.reason);
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
        debugLogger.debugLog('WebSocket error: ' + error, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('WebSocket connection error', 'error');
    };
}

function sendWebSocketMessage(message) {
    if (websocket && websocket.readyState == WebSocket.OPEN) {
        var messageString = JSON.stringify(message);
        websocket.send(messageString);
        wsStats.messages_sent++;
        debugLogger.debugLog('WebSocket message sent - Type: ' + message.type);
        console.log('Sent WebSocket message:', message); // Add detailed logging
        return true;
    } else {
        debugLogger.debugLog('WebSocket not connected, cannot send message - ReadyState: ' + (websocket ? websocket.readyState : 'null'), 'ERROR');
        ui.showStatus('Not connected to server', 'error');
        return false;
    }
}

function handleWebSocketMessage(data) {
    debugLogger.debugLog('Handling WebSocket message type: ' + data.type);
    
    switch (data.type) {
        case 'connection_established':
            currentSessionId = data.session_id;
            debugLogger.debugLog('Connected with session ID: ' + data.session_id);
            break;

        case 'UserInputRequestedEvent':
            // Handle AutoGen-style user input request (this is the approval request)
            debugLogger.debugLog('User input requested (approval request)');
            console.log('User input request data:', data);
            approvalWorkflow.handleApprovalRequest(data);
            break;

        case 'approval_request':
            // Legacy support for old-style approval requests
            debugLogger.debugLog('Legacy approval request received');
            console.log('Legacy approval request data:', data);
            approvalWorkflow.handleApprovalRequest(data);
            break;

        case 'approval_timeout':
            debugLogger.debugLog('Approval timeout received');
            approvalWorkflow.handleApprovalTimeout(data);
            break;

        case 'progress_update':
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
            debugLogger.debugLog('Unknown message type received: ' + data.type, 'WARNING');
            console.log('Unknown message data:', data);
    }
}

function showWebSocketStats() {
    var stats = 'WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection') + '\n' +
        'Session ID: ' + (currentSessionId || 'None');

    debugLogger.debugLog(stats);
    console.log('WebSocket Stats:', {
        connected: wsStats.connected,
        messages_sent: wsStats.messages_sent,
        messages_received: wsStats.messages_received,
        reconnects: wsStats.reconnects,
        connection_state: websocket ? websocket.readyState : 'No connection',
        session_id: currentSessionId
    });
    ui.showStatus('WebSocket stats logged to debug console', 'info');
}

function testConnection() {
    debugLogger.debugLog('Testing WebSocket connection');
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        if (sendWebSocketMessage({ type: 'ping' })) {
            ui.showStatus('Ping sent to server', 'info');
        }
    } else {
        debugLogger.debugLog('Cannot test connection - WebSocket not ready. State: ' + (websocket ? websocket.readyState : 'null'), 'WARNING');
        ui.showStatus('WebSocket not connected', 'warning');
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
    getConnectionStats 
};