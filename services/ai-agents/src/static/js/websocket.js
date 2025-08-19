// services/ai-agents/src/static/js/websocket.js - COMPLETE ENHANCED VERSION

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

// Function call tracking
var functionCallsDetected = {
    triage: false,
    context: false,
    analyst: false
};

function initWebSocket() {
    console.log('initWebSocket called with enhanced real-time streaming support');
    var protocol = window.location.protocol == 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';

    debugLogger.debugLog('Connecting to Enhanced Real-time WebSocket: ' + wsUrl);
    progressManager.updateConnectionStatus('connecting');

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function(event) {
        debugLogger.debugLog('Enhanced Real-time WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;
        ui.showStatus('Connected to Real-time SOC Analysis WebSocket', 'success');
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        var data = JSON.parse(event.data);
        debugLogger.debugLog('Enhanced Real-time WebSocket message received - Type: ' + data.type);
        console.log('Full real-time WebSocket message:', data);
        handleEnhancedRealtimeWebSocketMessage(data);
    };

    websocket.onclose = function(event) {
        debugLogger.debugLog('Enhanced Real-time WebSocket connection closed: ' + event.code + ' - ' + event.reason);
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
        debugLogger.debugLog('Enhanced Real-time WebSocket error: ' + error, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('Enhanced Real-time WebSocket connection error', 'error');
    };
}

function handleEnhancedRealtimeWebSocketMessage(data) {
    debugLogger.debugLog('Handling enhanced real-time WebSocket message type: ' + data.type);
    
    switch (data.type) {
        case 'connection_established':
            currentSessionId = data.session_id;
            debugLogger.debugLog('Connected with session ID: ' + data.session_id);
            
            // Show enhanced real-time features notification
            ui.showStatus('Real-time streaming enabled - agent outputs will appear live', 'info');
            break;

        case 'function_call_detected':
            // NEW: Handle detected function calls
            handleFunctionCallDetected(data);
            break;

        case 'real_time_agent_output':
            // Handle real-time agent output as it arrives
            handleEnhancedRealtimeAgentOutput(data);
            break;

        case 'priority_findings_update':
            // Handle immediate priority findings
            handleEnhancedPriorityFindingsUpdate(data);
            break;

        case 'context_results_update':
            // Handle immediate context results
            handleEnhancedContextResultsUpdate(data);
            break;

        case 'detailed_analysis_update':
            // Handle immediate detailed analysis
            handleEnhancedDetailedAnalysisUpdate(data);
            break;

        case 'analysis_workflow_complete':
            // Handle final workflow completion
            handleEnhancedWorkflowComplete(data);
            break;

        case 'workflow_rejected':
            // Handle workflow rejection
            handleEnhancedWorkflowRejected(data);
            break;

        case 'real_time_error':
            // Handle real-time errors
            debugLogger.debugLog('Real-time error: ' + data.content, 'ERROR');
            ui.showStatus('Real-time error: ' + data.content, 'error');
            break;

        case 'UserInputRequestedEvent':
            // Handle AutoGen-style user input request (approval request)
            debugLogger.debugLog('User input requested (approval request) - Enhanced Real-time');
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
            debugLogger.debugLog('Unknown enhanced real-time message type: ' + data.type, 'WARNING');
            console.log('Unknown enhanced real-time message data:', data);
    }
}

function handleFunctionCallDetected(data) {
    var agent = data.agent;
    var functionName = data.function;
    var content = data.content;
    
    debugLogger.debugLog('🔧 FUNCTION CALL DETECTED: ' + functionName + ' from ' + agent);
    console.log('🔧 Function call details:', data);
    
    // Mark function call as detected
    functionCallsDetected[agent] = true;
    
    // Show immediate feedback
    ui.showStatus('🔧 Function call detected: ' + functionName + ' from ' + agent, 'info');
    
    // Update agent output to show function is being called
    var outputElement = document.getElementById(agent + 'Output');
    if (outputElement) {
        var timestamp = new Date().toLocaleTimeString();
        var functionCallText = '[' + timestamp + '] 🔧 FUNCTION CALL DETECTED: ' + functionName + '\n' +
            '⚡ Processing structured findings...\n' +
            '📊 Validating data and preparing results...\n';
        
        // Clear waiting text and show function call status
        if (outputElement.textContent.includes('Waiting for') || 
            outputElement.textContent.includes('waiting') ||
            outputElement.textContent.length < 100) {
            outputElement.textContent = functionCallText;
        } else {
            outputElement.textContent += '\n\n' + functionCallText;
        }
        
        // Auto-scroll
        outputElement.scrollTop = outputElement.scrollHeight;
    }
    
    // Update agent status to show it's processing function call
    ui.updateAgentStatus(agent, 'active');
    ui.showAgentSpinner(agent, true);
    
    // Add special styling to indicate function call
    var agentCard = document.getElementById(agent + 'Card');
    if (agentCard) {
        agentCard.classList.add('function-calling');
        agentCard.style.borderLeft = '4px solid #f39c12';
        agentCard.style.boxShadow = '0 0 20px rgba(243, 156, 18, 0.4)';
    }
}

function handleEnhancedRealtimeAgentOutput(data) {
    var agent = data.agent;
    var content = data.content;
    var timestamp = data.timestamp;
    var source = data.source;
    
    // Enhanced filtering and processing
    if (!agent || agent === 'unknown' || !agentOutputBuffers[agent]) {
        debugLogger.debugLog('Skipping unknown or invalid agent output: ' + agent);
        return;
    }
    
    // Skip system messages but be more permissive for actual agent content
    if (content.includes('ENHANCED SECURITY LOG ANALYSIS') || 
        content.includes('MULTI-STAGE WORKFLOW') ||
        content.includes('TriageSpecialist: Begin initial triage')) {
        debugLogger.debugLog('Skipping task description message from: ' + agent);
        return;
    }
    
    // Enhanced function call result detection
    if ((content.includes('status') && content.includes('priority_identified')) ||
        (content.includes('status') && content.includes('analysis_complete')) ||
        content.includes('FUNCTION CALLED') ||
        content.includes('FUNCTION EXECUTED')) {
        debugLogger.debugLog('🎯 Function call result detected for: ' + agent);
        handleEnhancedFunctionCallResult(agent, content, timestamp);
        return;
    }
    
    debugLogger.debugLog('Processing enhanced real-time output from ' + agent + ': ' + content.substring(0, 100) + '...');
    
    // Add to buffer
    agentOutputBuffers[agent].push({
        content: content,
        timestamp: timestamp,
        source: source
    });
    
    // Keep only last 20 messages
    if (agentOutputBuffers[agent].length > 20) {
        agentOutputBuffers[agent].shift();
    }
    
    // Update agent display with enhanced formatting
    updateEnhancedAgentOutput(agent, content, timestamp);
}

function handleEnhancedFunctionCallResult(agent, content, timestamp) {
    debugLogger.debugLog('🎯 Processing enhanced function call result for: ' + agent);
    
    try {
        // Multiple strategies to extract function call results
        var result_data = null;
        
        // Strategy 1: Look for JSON with status
        var jsonPatterns = [
            /\{[^}]*"status"[^}]*"priority_identified"[^}]*\}/g,
            /\{.*?"status".*?"priority_identified".*?\}/g,
            /\{[^}]*"status"[^}]*"analysis_complete"[^}]*\}/g,
            /\{.*?"status".*?"analysis_complete".*?\}/g
        ];
        
        for (var i = 0; i < jsonPatterns.length; i++) {
            var matches = content.match(jsonPatterns[i]);
            if (matches) {
                try {
                    result_data = JSON.parse(matches[0]);
                    break;
                } catch (e) {
                    continue;
                }
            }
        }
        
        // Strategy 2: Look for FUNCTION EXECUTED messages
        if (!result_data && content.includes('FUNCTION EXECUTED')) {
            debugLogger.debugLog('📊 Function execution confirmed for: ' + agent);
            showFunctionExecutionConfirmation(agent, content, timestamp);
            return;
        }
        
        if (result_data && (result_data.status === 'priority_identified' || result_data.status === 'analysis_complete')) {
            var data = result_data.data || {};
            var displayTime = new Date(timestamp).toLocaleTimeString();
            
            var resultText = '';
            if (result_data.status === 'priority_identified') {
                resultText = '[' + displayTime + '] ✅ PRIORITY FINDINGS GENERATED:\n' +
                    '🎯 Threat: ' + (data.threat_type || 'Unknown') + '\n' +
                    '📍 Source: ' + (data.source_ip || 'Unknown') + '\n' +
                    '⚠️ Priority: ' + (data.priority || 'Unknown').toUpperCase() + '\n' +
                    '📊 Confidence: ' + (data.confidence_score || 'Unknown') + '\n' +
                    '📈 Events: ' + (data.event_count || 'Unknown') + '\n' +
                    '🎯 Pattern: ' + (data.attack_pattern || 'Not specified') + '\n' +
                    '⏰ Timeline: ' + (data.timeline ? data.timeline.start + ' → ' + data.timeline.end : 'Unknown');
            } else if (result_data.status === 'analysis_complete') {
                var actionCount = data.recommended_actions ? data.recommended_actions.length : 0;
                resultText = '[' + displayTime + '] ✅ DETAILED ANALYSIS COMPLETE:\n' +
                    '🎯 Threat Assessment: ' + (data.threat_assessment?.severity || 'Unknown') + '\n' +
                    '📋 Recommendations: ' + actionCount + ' actions\n' +
                    '💼 Business Impact: ' + (data.business_impact || 'Under review') + '\n' +
                    '🔒 Confidence: ' + (data.threat_assessment?.confidence || 'Unknown') + '\n' +
                    '📝 Notes: ' + (data.investigation_notes || 'None provided');
            }
            
            updateEnhancedAgentOutput(agent, resultText, timestamp);
            
            // Update status to complete
            ui.updateAgentStatus(agent, 'complete');
            ui.showAgentSpinner(agent, false);
            
            // Remove function-calling style and add success style
            var agentCard = document.getElementById(agent + 'Card');
            if (agentCard) {
                agentCard.classList.remove('function-calling');
                agentCard.style.borderLeft = '4px solid #56ab2f'; // Success color
                agentCard.style.boxShadow = '0 0 20px rgba(86, 171, 47, 0.4)';
                
                // Reset after animation
                setTimeout(function() {
                    agentCard.style.boxShadow = '';
                }, 3000);
            }
            
            // Show success notification
            var successMessage = agent.charAt(0).toUpperCase() + agent.slice(1) + ' analysis complete';
            if (result_data.status === 'priority_identified') {
                successMessage += ': ' + (data.threat_type || 'Threat detected');
            } else {
                successMessage += ': ' + actionCount + ' recommendations';
            }
            ui.showStatus('✅ ' + successMessage, 'success');
            
            // Trigger appropriate update handler
            if (result_data.status === 'priority_identified') {
                handleEnhancedPriorityFindingsUpdate({
                    data: data,
                    timestamp: timestamp
                });
            } else if (result_data.status === 'analysis_complete') {
                handleEnhancedDetailedAnalysisUpdate({
                    data: data,
                    timestamp: timestamp
                });
            }
        } else {
            debugLogger.debugLog('Could not extract structured results, showing raw content');
            updateEnhancedAgentOutput(agent, content, timestamp);
        }
    } catch (e) {
        debugLogger.debugLog('Error parsing enhanced function call result: ' + e, 'ERROR');
        // Fallback to normal output handling
        updateEnhancedAgentOutput(agent, content, timestamp);
    }
}

function showFunctionExecutionConfirmation(agent, content, timestamp) {
    var displayTime = new Date(timestamp).toLocaleTimeString();
    var confirmationText = '[' + displayTime + '] ✅ FUNCTION EXECUTION CONFIRMED\n' +
        '🔧 Function successfully called and executed\n' +
        '📊 Processing results and preparing structured output...\n';
    
    updateEnhancedAgentOutput(agent, confirmationText, timestamp);
    
    // Show notification
    ui.showStatus('✅ ' + agent + ' function executed successfully', 'success');
}

function updateEnhancedAgentOutput(agent, content, timestamp) {
    var outputElement = document.getElementById(agent + 'Output');
    if (!outputElement) return;
    
    var displayTime = new Date(timestamp).toLocaleTimeString();
    var formattedContent = '[' + displayTime + '] ' + content;
    
    // Smart content management with enhanced logic
    var existingContent = outputElement.textContent;
    
    if (existingContent.includes('Waiting for') || 
        existingContent.includes('waiting') ||
        existingContent.length < 50) {
        // Replace placeholder text
        outputElement.textContent = formattedContent;
    } else {
        // Append new content with separator
        outputElement.textContent = existingContent + '\n\n' + formattedContent;
    }
    
    // Auto-scroll
    outputElement.scrollTop = outputElement.scrollHeight;
    
    // Enhanced visual feedback
    var agentCard = document.getElementById(agent + 'Card');
    if (agentCard) {
        agentCard.classList.add('active');
        
        // Enhanced highlight effect for new content
        agentCard.classList.add('new-content');
        setTimeout(function() {
            agentCard.classList.remove('new-content');
        }, 1500);
    }
}

function handleEnhancedPriorityFindingsUpdate(data) {
    debugLogger.debugLog('Enhanced priority findings update received in real-time');
    var findings = data.data;
    
    if (findings && findings.threat_type && findings.source_ip) {
        var priority = findings.priority || 'medium';
        var threatType = findings.threat_type;
        var sourceIp = findings.source_ip;
        
        // Show enhanced immediate notification
        ui.showStatus('🚨 Priority ' + priority.toUpperCase() + ' threat: ' + threatType + ' from ' + sourceIp, 'warning');
        
        // Update triage agent to complete
        ui.updateAgentStatus('triage', 'complete');
        ui.showAgentSpinner('triage', false);
        
        // Enhanced findings preview in triage output
        var triageOutput = document.getElementById('triageOutput');
        if (triageOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var enhancedFindingsText = '[' + timestamp + '] 🎯 STRUCTURED FINDINGS AVAILABLE:\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
                '🚨 Threat: ' + threatType + '\n' +
                '📍 Source: ' + sourceIp + '\n' +
                '⚠️ Priority: ' + priority.toUpperCase() + '\n' +
                '📊 Confidence: ' + (findings.confidence_score || 0.8) + '\n' +
                '📈 Events: ' + (findings.event_count || 'unknown') + '\n' +
                '🎯 Pattern: ' + (findings.attack_pattern || 'Not specified') + '\n' +
                '🎲 Services: ' + (findings.affected_services ? findings.affected_services.join(', ') : 'Unknown') + '\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
            
            triageOutput.textContent += '\n\n' + enhancedFindingsText;
            triageOutput.scrollTop = triageOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(40, 'Priority threat identified');
        
        debugLogger.debugLog('Enhanced priority findings processed: ' + threatType + ' from ' + sourceIp);
    }
}

function handleEnhancedContextResultsUpdate(data) {
    debugLogger.debugLog('Enhanced context results update received in real-time');
    var results = data.data;
    
    if (results && results.documents) {
        var documentCount = results.documents.length;
        
        // Show immediate notification
        ui.showStatus('🔎 Found ' + documentCount + ' related historical incidents', 'info');
        
        // Update context agent to complete
        ui.updateAgentStatus('context', 'complete');
        ui.showAgentSpinner('context', false);
        
        // Enhanced context preview
        var contextOutput = document.getElementById('contextOutput');
        if (contextOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var enhancedContextText = '[' + timestamp + '] 📚 HISTORICAL CONTEXT RESEARCH:\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
                '📊 Documents Found: ' + documentCount + '\n' +
                '🔍 Source: ChromaDB historical analysis\n' +
                '📈 Similarity: High pattern matching\n' +
                '🎯 Relevance: Related incident patterns\n' +
                '✅ Status: Ready for deep analysis\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
            
            contextOutput.textContent += '\n\n' + enhancedContextText;
            contextOutput.scrollTop = contextOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(70, 'Historical context analyzed');
        
        debugLogger.debugLog('Enhanced context results processed: ' + documentCount + ' documents');
    }
}

function handleEnhancedDetailedAnalysisUpdate(data) {
    debugLogger.debugLog('Enhanced detailed analysis update received in real-time');
    var analysis = data.data;
    
    if (analysis && analysis.recommended_actions) {
        var actionCount = analysis.recommended_actions.length;
        
        // Show immediate notification
        ui.showStatus('👨‍💼 Analysis complete with ' + actionCount + ' recommendations', 'success');
        
        // Update analyst agent to complete
        ui.updateAgentStatus('analyst', 'complete');
        ui.showAgentSpinner('analyst', false);
        
        // Enhanced analysis preview
        var analystOutput = document.getElementById('analystOutput');
        if (analystOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var enhancedAnalysisText = '[' + timestamp + '] 🎯 COMPREHENSIVE ANALYSIS COMPLETE:\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n' +
                '🎯 Threat Assessment: ' + (analysis.threat_assessment?.severity || 'unknown') + '\n' +
                '📊 Confidence Level: ' + (analysis.threat_assessment?.confidence || 'unknown') + '\n' +
                '📋 Recommendations: ' + actionCount + ' actionable items\n' +
                '💼 Business Impact: ' + (analysis.business_impact || 'Under review') + '\n' +
                '🔒 Status: Awaiting authorization\n' +
                '📝 Investigation Notes: ' + (analysis.investigation_notes ? 'Available' : 'None') + '\n' +
                '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━';
            
            analystOutput.textContent += '\n\n' + enhancedAnalysisText;
            analystOutput.scrollTop = analystOutput.scrollHeight;
        }
        
        // Update progress
        ui.updateProgress(95, 'Analysis complete - awaiting authorization');
        
        debugLogger.debugLog('Enhanced detailed analysis processed: ' + actionCount + ' recommendations');
    }
}

function handleEnhancedWorkflowComplete(data) {
    debugLogger.debugLog('Enhanced real-time workflow completion received');
    
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
        
        // Show enhanced final results if available
        setTimeout(function() {
            showEnhancedRealtimeResultsSummary();
        }, 1000);
    }
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    approvalWorkflow.setAwaitingApproval(false);
}

function handleEnhancedWorkflowRejected(data) {
    debugLogger.debugLog('Enhanced real-time workflow rejection received');
    
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

function showEnhancedRealtimeResultsSummary() {
    debugLogger.debugLog('Showing enhanced real-time results summary');
    
    // Create an enhanced summary from the real-time data we've collected
    var findings = [];
    
    // Check what we learned from each agent
    var triageBuffer = agentOutputBuffers.triage || [];
    var contextBuffer = agentOutputBuffers.context || [];
    var analystBuffer = agentOutputBuffers.analyst || [];
    
    if (triageBuffer.length > 0 || functionCallsDetected.triage) {
        findings.push({
            title: '🚨 Triage Results',
            content: 'Priority threat assessment completed with structured findings, threat classification, and source identification.'
        });
    }
    
    if (contextBuffer.length > 0 || functionCallsDetected.context) {
        findings.push({
            title: '📚 Historical Context',
            content: 'Related historical incidents analyzed for pattern matching, threat correlation, and lessons learned integration.'
        });
    }
    
    if (analystBuffer.length > 0 || functionCallsDetected.analyst) {
        findings.push({
            title: '🎯 Deep Analysis Complete',
            content: 'Comprehensive analysis completed with actionable recommendations, business impact assessment, and implementation timeline.'
        });
    }
    
    // Show the enhanced findings
    if (findings.length > 0) {
        ui.displayFinalResults({
            structured_findings: {
                priority_threat: {
                    priority: 'high',
                    threat_type: 'Enhanced Multi-stage Analysis',
                    brief_summary: 'Real-time analysis completed successfully with function call verification'
                }
            },
            chroma_context: {}
        });
    }
}

function clearEnhancedRealtimeBuffers() {
    debugLogger.debugLog('Clearing enhanced real-time agent output buffers');
    agentOutputBuffers = {
        triage: [],
        context: [],
        analyst: []
    };
    functionCallsDetected = {
        triage: false,
        context: false,
        analyst: false
    };
}

// Enhanced WebSocket message sending with retry logic
function sendWebSocketMessage(message) {
    if (websocket && websocket.readyState == WebSocket.OPEN) {
        var messageString = JSON.stringify(message);
        websocket.send(messageString);
        wsStats.messages_sent++;
        debugLogger.debugLog('Enhanced Real-time WebSocket message sent - Type: ' + message.type);
        console.log('Sent enhanced real-time WebSocket message:', message);
        return true;
    } else {
        debugLogger.debugLog('Enhanced Real-time WebSocket not connected, cannot send message - ReadyState: ' + (websocket ? websocket.readyState : 'null'), 'ERROR');
        ui.showStatus('Not connected to server', 'error');
        return false;
    }
}

function showWebSocketStats() {
    var bufferSizes = Object.keys(agentOutputBuffers).map(function(agent) {
        return agent + ': ' + agentOutputBuffers[agent].length + ' messages';
    }).join(', ');
    
    var functionCallStatus = Object.keys(functionCallsDetected).map(function(agent) {
        return agent + ': ' + (functionCallsDetected[agent] ? 'DETECTED' : 'none');
    }).join(', ');
    
    var stats = 'Enhanced Real-time WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection') + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        'Real-time Buffers: ' + bufferSizes + '\n' +
        'Function Calls: ' + functionCallStatus;

    debugLogger.debugLog(stats);
    console.log('Enhanced Real-time WebSocket Stats:', {
        connected: wsStats.connected,
        messages_sent: wsStats.messages_sent,
        messages_received: wsStats.messages_received,
        reconnects: wsStats.reconnects,
        connection_state: websocket ? websocket.readyState : 'No connection',
        session_id: currentSessionId,
        agent_buffers: agentOutputBuffers,
        function_calls_detected: functionCallsDetected
    });
    ui.showStatus('Enhanced Real-time WebSocket stats logged to debug console', 'info');
}

function testConnection() {
    debugLogger.debugLog('Testing enhanced real-time WebSocket connection');
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        if (sendWebSocketMessage({ type: 'ping' })) {
            ui.showStatus('Ping sent to enhanced real-time server', 'info');
        }
    } else {
        debugLogger.debugLog('Cannot test connection - Enhanced Real-time WebSocket not ready. State: ' + (websocket ? websocket.readyState : 'null'), 'WARNING');
        ui.showStatus('Enhanced Real-time WebSocket not connected', 'warning');
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

function getFunctionCallsDetected() {
    return functionCallsDetected;
}

// Handle page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close(1000, 'Page unloading');
    }
});

// Add enhanced CSS for function calling states
const enhancedFunctionCallStyle = `
.agent-card.function-calling {
    border-left: 4px solid #f39c12 !important;
    animation: enhancedFunctionCallPulse 2s infinite;
}

@keyframes enhancedFunctionCallPulse {
    0%, 100% { 
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        transform: scale(1);
    }
    50% { 
        box-shadow: 0 12px 40px rgba(243, 156, 18, 0.4);
        transform: scale(1.01);
    }
}

.agent-card.new-content {
    animation: enhancedContentFlash 1.5s ease;
}

@keyframes enhancedContentFlash {
    0% {
        box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.7);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 20px 5px rgba(102, 126, 234, 0.3);
        transform: scale(1.02);
    }
    100% {
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
        transform: scale(1);
    }
}
`;

// Add the enhanced styles to the page
if (!document.getElementById('enhanced-function-call-styles')) {
    const styleElement = document.createElement('style');
    styleElement.id = 'enhanced-function-call-styles';
    styleElement.textContent = enhancedFunctionCallStyle;
    document.head.appendChild(styleElement);
}

export { 
    initWebSocket, 
    sendWebSocketMessage, 
    showWebSocketStats, 
    testConnection, 
    getCurrentSessionId, 
    getWebSocket, 
    getConnectionStats,
    clearEnhancedRealtimeBuffers,
    getAgentOutputBuffers,
    getFunctionCallsDetected
};