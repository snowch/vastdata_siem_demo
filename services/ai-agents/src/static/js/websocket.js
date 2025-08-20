// services/ai-agents/src/static/js/websocket.js - DEBUG VERSION
// Complete file with debug logging for priority_findings_update issue

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

// NEW: Simple progress tracking based on specific events
var workflowProgress = {
    triage: 0,     // 0 = pending, 1 = active, 2 = complete
    context: 0,    
    analyst: 0,
    overall: 0     // Calculated from stages: 0-100%
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

    // 👈 MODIFIED: Add extensive debug logging to existing onmessage handler
    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        
        try {
            var data = JSON.parse(event.data);
            
            // 🚀 DEBUG LOGGING: Log every raw WebSocket message
            debugLogger.debugLog('📨 RAW WebSocket message received - Type: ' + data.type);
            console.log('📨 RAW WebSocket message:', data);
            
            // 🎯 SPECIFIC CHECK: Look for our missing message type
            if (data.type === 'priority_findings_update') {
                console.log('🎯 RAW MESSAGE: priority_findings_update detected in raw WebSocket data!');
                console.log('🎯 RAW DATA:', JSON.stringify(data, null, 2));
                debugLogger.debugLog('🎯 CRITICAL: priority_findings_update message received via WebSocket');
            } else {
                console.log('📝 RAW MESSAGE: Type "' + data.type + '" (not priority_findings_update)');
            }
            
            // Call the existing message handler
            handleEnhancedRealtimeWebSocketMessage(data);
            
        } catch (e) {
            console.error('❌ Error parsing WebSocket message:', e);
            console.error('❌ Raw message data:', event.data);
            debugLogger.debugLog('❌ WebSocket message parse error: ' + e, 'ERROR');
        }
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

// NEW: Smart progress calculation based on completed stages
function updateOverallProgress() {
    var progress = 0;
    var statusText = 'Initializing';
    
    // Each stage contributes to overall progress
    if (workflowProgress.triage >= 1) {
        progress += 30;  // Triage active/complete
        statusText = 'Analyzing Threats';
    }
    if (workflowProgress.triage >= 2) {
        progress += 10;  // Triage complete
        statusText = 'Triage Complete';
    }
    if (workflowProgress.context >= 1) {
        progress += 20; // Context active  
        statusText = 'Researching Historical Context';
    }
    if (workflowProgress.context >= 2) {
        progress += 10; // Context complete
        statusText = 'Context Research Complete';
    }
    if (workflowProgress.analyst >= 1) {
        progress += 20; // Analysis active
        statusText = 'Deep Analysis in Progress';
    }
    if (workflowProgress.analyst >= 2) {
        progress += 10; // Analysis complete
        statusText = 'Analysis Complete';
    }
    
    workflowProgress.overall = progress;
    
    // Update UI with calculated progress
    ui.updateProgress(progress, statusText);
    
    debugLogger.debugLog('Smart progress calculated: ' + progress + '% - ' + statusText);
}

// NEW: Reset workflow progress for new analysis
function resetWorkflowProgress() {
    workflowProgress = { triage: 0, context: 0, analyst: 0, overall: 0 };
    functionCallsDetected = { triage: false, context: false, analyst: false };
    agentOutputBuffers = { triage: [], context: [], analyst: [] };
    debugLogger.debugLog('Workflow progress reset');
}

// 👈 MODIFIED: Add extensive debug logging to message handler
function handleEnhancedRealtimeWebSocketMessage(data) {
    // 🚀 DEBUG LOGGING: Log every message that enters the handler
    debugLogger.debugLog('🔍 FRONTEND: Processing message type: ' + data.type);
    console.log('🔍 FRONTEND DEBUG: Full message entering handler:', data);
    
    // 🎯 SPECIFIC CHECK: Critical logging for our target message
    if (data.type === 'priority_findings_update') {
        console.log('🎯 FRONTEND DEBUG: priority_findings_update message received in handler!', data);
        console.log('🎯 FRONTEND DEBUG: About to call handleEnhancedPriorityFindingsUpdate');
        debugLogger.debugLog('🎯 CRITICAL: priority_findings_update entering switch statement');
    } else {
        console.log('📝 FRONTEND DEBUG: Message type "' + data.type + '" - not priority_findings_update');
    }
    
    switch (data.type) {
        case 'connection_established':
            currentSessionId = data.session_id;
            debugLogger.debugLog('Connected with session ID: ' + data.session_id);
            
            // Reset progress for new session
            resetWorkflowProgress();
            
            // Show enhanced real-time features notification
            ui.showStatus('Real-time streaming enabled - agent outputs will appear live', 'info');
            break;

        case 'function_call_detected':
            // Handle detected function calls
            handleFunctionCallDetected(data);
            break;

        case 'real_time_agent_output':
            // Handle real-time agent output as it arrives
            handleEnhancedRealtimeAgentOutput(data);
            break;

        case 'priority_findings_update':
            console.log('🎯 FRONTEND: Handling priority_findings_update in switch case');
            debugLogger.debugLog('🎯 CRITICAL: priority_findings_update switch case triggered');
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
            debugLogger.debugLog('🚨 FRONTEND: Unknown enhanced real-time message type: ' + data.type, 'WARNING');
            console.log('🚨 FRONTEND: Unknown enhanced real-time message data:', data);
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
    
    // NEW: Mark agent as active when receiving output
    if (workflowProgress[agent] === 0) {
        workflowProgress[agent] = 1;
        ui.updateAgentStatus(agent, 'active');
        ui.showAgentSpinner(agent, true);
        updateOverallProgress();
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

// 👈 MODIFIED: Add extensive debug logging to priority findings handler
function handleEnhancedPriorityFindingsUpdate(data) {
    console.log('🎯 FRONTEND: handleEnhancedPriorityFindingsUpdate called with data:', data);
    debugLogger.debugLog('🎯 CRITICAL: handleEnhancedPriorityFindingsUpdate function executing');
    
    var findings = data.data;
    
    if (findings && findings.threat_type && findings.source_ip) {
        var priority = findings.priority || 'medium';
        var threatType = findings.threat_type;
        var sourceIp = findings.source_ip;
        var targetHosts = findings.target_hosts || [];
        var attackPattern = findings.attack_pattern || 'Unknown pattern';
        var confidence = findings.confidence_score || 0;
        var eventCount = findings.event_count || 0;
        
        console.log('🎯 FRONTEND: Processing priority findings - ' + threatType + ' from ' + sourceIp);
        debugLogger.debugLog('🎯 CRITICAL: Processing priority findings: ' + threatType);
        
        // Show enhanced immediate notification
        ui.showStatus('🚨 Priority ' + priority.toUpperCase() + ' threat: ' + threatType + ' from ' + sourceIp, 'warning');
        
        // 👈 CRITICAL: Update the triage agent card with structured findings
        var triageOutput = document.getElementById('triageOutput');
        if (triageOutput) {
            console.log('🎯 FRONTEND: Updating triageOutput element');
            var timestamp = new Date().toLocaleTimeString();
            var structuredOutput = '[' + timestamp + '] ✅ TRIAGE ANALYSIS COMPLETE:\n' +
                '🎯 Threat Type: ' + threatType + '\n' +
                '📍 Source IP: ' + sourceIp + '\n' +
                '🎯 Target Hosts: ' + targetHosts.join(', ') + '\n' +
                '⚠️ Priority: ' + priority.toUpperCase() + '\n' +
                '📊 Confidence: ' + (confidence * 100).toFixed(1) + '%\n' +
                '📈 Events: ' + eventCount + '\n' +
                '🔍 Attack Pattern: ' + attackPattern + '\n' +
                '⏰ Timeline: ' + (findings.timeline ? findings.timeline.start + ' → ' + findings.timeline.end : 'Unknown') + '\n' +
                '📋 Summary: ' + (findings.brief_summary || 'No summary available');
            
            triageOutput.textContent = structuredOutput;
            triageOutput.scrollTop = triageOutput.scrollHeight;
            
            console.log('🎯 FRONTEND: triageOutput updated successfully');
            debugLogger.debugLog('🎯 CRITICAL: triageOutput element updated with structured findings');
        } else {
            console.error('❌ FRONTEND: triageOutput element not found!');
            debugLogger.debugLog('❌ CRITICAL: triageOutput element not found', 'ERROR');
        }
        
        // Update progress tracking
        workflowProgress.triage = 2; // Complete
        ui.updateAgentStatus('triage', 'complete');
        ui.showAgentSpinner('triage', false);
        updateOverallProgress();
        
        // Add visual feedback to triage card
        var triageCard = document.getElementById('triageCard');
        if (triageCard) {
            triageCard.classList.add('active');
            triageCard.style.borderLeft = '4px solid #56ab2f'; // Success color
            
            // Highlight effect
            triageCard.classList.add('new-content');
            setTimeout(function() {
                triageCard.classList.remove('new-content');
            }, 1500);
            
            console.log('🎯 FRONTEND: triageCard visual feedback applied');
        } else {
            console.error('❌ FRONTEND: triageCard element not found!');
        }
        
        console.log('🎯 FRONTEND: Priority findings processing completed successfully');
        debugLogger.debugLog('🎯 CRITICAL: Priority findings processed and displayed: ' + threatType + ' from ' + sourceIp);
    } else {
        console.error('❌ FRONTEND: Invalid findings data structure:', findings);
        debugLogger.debugLog('❌ CRITICAL: Invalid findings data in handleEnhancedPriorityFindingsUpdate', 'ERROR');
    }
}

function handleEnhancedContextResultsUpdate(data) {
    debugLogger.debugLog('Enhanced context results update received in real-time');
    var results = data.data;
    
    if (results && results.documents) {
        var documentCount = results.documents.length;
        
        // Show immediate notification
        ui.showStatus('🔎 Found ' + documentCount + ' related historical incidents', 'info');
        
        // NEW: Update progress tracking
        workflowProgress.context = 2; // Complete
        ui.updateAgentStatus('context', 'complete');
        ui.showAgentSpinner('context', false);
        updateOverallProgress();
        
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
        
        // NEW: Update progress tracking
        workflowProgress.analyst = 2; // Complete
        ui.updateAgentStatus('analyst', 'complete');
        ui.showAgentSpinner('analyst', false);
        updateOverallProgress();
        
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
        
        // Show enhanced final results if available
        setTimeout(function() {
            showEnhancedRealtimeResultsSummary();
        }, 1000);
    }
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    approvalWorkflow.setAwaitingApproval(false);
    
    // Enable the analyze button again
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
    
    // Reset for next analysis
    setTimeout(resetWorkflowProgress, 2000);
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
    
    // Reset for next analysis
    setTimeout(resetWorkflowProgress, 2000);
}

// Keep all the other existing functions unchanged...
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
                    brief_summary: 'Real-time analysis completed successfully with smart progress tracking'
                }
            },
            chroma_context: {}
        });
    }
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
    
    var progressStatus = Object.keys(workflowProgress).map(function(stage) {
        return stage + ': ' + workflowProgress[stage];
    }).join(', ');
    
    var stats = 'Enhanced Real-time WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection') + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        'Smart Progress: ' + progressStatus + '\n' +
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
        smart_progress: workflowProgress,
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

// NEW: Export workflow progress for debugging
function getWorkflowProgress() {
    return workflowProgress;
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
    getAgentOutputBuffers,
    getFunctionCallsDetected,
    getWorkflowProgress
};