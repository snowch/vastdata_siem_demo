// services/ai-agents/src/static/js/websocket.js - CLEAN ARCHITECTURE VERSION
// WebSocket client with message type validation and clean architecture support

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// ============================================================================
// CLEAN MESSAGE ARCHITECTURE GLOBALS
// ============================================================================

var websocket = null;
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0, type_validation_errors: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;
var currentSessionId = null;

// Clean Architecture State
var supportedMessageTypes = {
    results: [],
    status: [],
    interaction: [],
    control: [],
    all_types: []
};
var messageTypeValidationEnabled = false;
var cleanArchitectureEnabled = false;

// Agent state tracking
var agentStates = {
    triage: { status: 'pending', has_findings: false },
    context: { status: 'pending', has_research: false },
    analyst: { status: 'pending', has_recommendations: false }
};

// Workflow progress tracking
var workflowProgress = {
    current_stage: 'initializing',
    progress_percentage: 0,
    completed_stages: [],
    estimated_time_remaining: null
};

// ============================================================================
// MESSAGE TYPE VALIDATION
// ============================================================================

function validateMessageType(messageType) {
    // Validate that a message type is supported by the server
    if (!messageTypeValidationEnabled) {
        debugLogger.debugLog('🔧 Message type validation disabled, accepting: ' + messageType);
        return true;
    }
    
    if (!supportedMessageTypes.all_types.includes(messageType)) {
        debugLogger.debugLog('❌ CLEAN ARCH: Unsupported message type: ' + messageType, 'ERROR');
        wsStats.type_validation_errors++;
        
        ui.showStatus('⚠️ Received unsupported message type: ' + messageType, 'warning');
        return false;
    }
    
    debugLogger.debugLog('✅ CLEAN ARCH: Valid message type: ' + messageType);
    return true;
}

function getMessageCategory(messageType) {
    // Get the category for a message type
    
    // Handle core control messages even before types are advertised
    const coreControlTypes = [
        'connection_established', 
        'message_types_advertisement', 
        'error', 
        'logs_retrieved', 
        'ping', 
        'pong'
    ];
    
    if (coreControlTypes.includes(messageType)) {
        return 'control';
    }
    
    // Handle core interaction types
    const coreInteractionTypes = [
        'approval_request',
        'approval_response', 
        'approval_timeout'
    ];
    
    if (coreInteractionTypes.includes(messageType)) {
        return 'interaction';
    }
    
    // Check against advertised types if available
    for (const [category, types] of Object.entries(supportedMessageTypes)) {
        if (category !== 'all_types' && types.includes(messageType)) {
            return category;
        }
    }
    
    return 'unknown';
}

function logMessageTypeStats() {
    // Log statistics about message type validation
    console.log('📊 CLEAN ARCH: Message Type Statistics:', {
        validation_enabled: messageTypeValidationEnabled,
        supported_types_count: supportedMessageTypes.all_types.length,
        validation_errors: wsStats.type_validation_errors,
        categories: {
            results: supportedMessageTypes.results.length,
            status: supportedMessageTypes.status.length,
            interaction: supportedMessageTypes.interaction.length,
            control: supportedMessageTypes.control.length
        }
    });
}

// ============================================================================
// WEBSOCKET INITIALIZATION
// ============================================================================

function initWebSocket() {
    console.log('🚀 CLEAN ARCH: Initializing WebSocket with clean message architecture support');
    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';

    debugLogger.debugLog('🔌 CLEAN ARCH: Connecting to WebSocket: ' + wsUrl);
    progressManager.updateConnectionStatus('connecting');

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function(event) {
        debugLogger.debugLog('✅ CLEAN ARCH: WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;
        ui.showStatus('🔌 Connected to Clean Architecture SOC Analysis WebSocket', 'success');
        
        // Reset clean architecture state
        cleanArchitectureEnabled = false;
        messageTypeValidationEnabled = false;
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        
        try {
            var data = JSON.parse(event.data);
            
            debugLogger.debugLog('📨 CLEAN ARCH: Raw WebSocket message received - Type: ' + data.type);
            console.log('📨 CLEAN ARCH: Raw message:', data);
            
            // Handle the message using clean architecture
            handleCleanArchitectureMessage(data);
            
        } catch (e) {
            console.error('❌ Error parsing WebSocket message:', e);
            console.error('❌ Raw message data:', event.data);
            debugLogger.debugLog('❌ WebSocket message parse error: ' + e, 'ERROR');
        }
    };

    websocket.onclose = function(event) {
        debugLogger.debugLog('🔌 CLEAN ARCH: WebSocket connection closed: ' + event.code + ' - ' + event.reason);
        progressManager.updateConnectionStatus('disconnected');
        wsStats.connected = false;

        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            ui.showStatus('🔄 Connection lost. Reconnecting... (' + reconnectAttempts + '/' + maxReconnectAttempts + ')', 'warning');
            setTimeout(function() {
                initWebSocket();
                wsStats.reconnects++;
            }, 2000 * reconnectAttempts);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
            ui.showStatus('❌ Connection failed. Please refresh the page.', 'error');
        }
    };

    websocket.onerror = function(error) {
        debugLogger.debugLog('❌ CLEAN ARCH: WebSocket error: ' + error, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('❌ Clean Architecture WebSocket connection error', 'error');
    };
}

// ============================================================================
// CLEAN ARCHITECTURE MESSAGE HANDLER
// ============================================================================

function handleCleanArchitectureMessage(data) {
    // Main message handler for clean architecture messages
    var messageType = data.type;
    var category = getMessageCategory(messageType);
    
    debugLogger.debugLog('🔍 CLEAN ARCH: Processing ' + category + '/' + messageType + ' message');
    
    // Validate message type if validation is enabled
    if (!validateMessageType(messageType)) {
        return; // Skip invalid message types
    }
    
    // Route to appropriate handler based on category and type
    switch (category) {
        case 'control':
            handleControlMessage(data);
            break;
            
        case 'results':
            handleResultsMessage(data);
            break;
            
        case 'status':
            handleStatusMessage(data);
            break;
            
        case 'interaction':
            handleInteractionMessage(data);
            break;
            
        default:
            // Handle unknown categories (might be custom or new message types)
            handleUnknownMessage(data);
            break;
    }
}

// ============================================================================
// CATEGORY-SPECIFIC MESSAGE HANDLERS
// ============================================================================

function handleControlMessage(data) {
    // Handle control category messages
    var messageType = data.type;
    
    debugLogger.debugLog('🎛️ CLEAN ARCH: Handling control message: ' + messageType);
    
    switch (messageType) {
        case 'connection_established':
            handleConnectionEstablished(data);
            break;
            
        case 'message_types_advertisement':
            handleMessageTypesAdvertisement(data);
            break;
            
        case 'analysis_complete':
            handleAnalysisComplete(data);
            break;
            
        case 'workflow_rejected':
            handleWorkflowRejected(data);
            break;
            
        case 'error':
            handleErrorMessage(data);
            break;
            
        case 'logs_retrieved':
            handleLogsRetrieved(data);
            break;
            
        case 'pong':
            handlePongMessage(data);
            break;
            
        default:
            debugLogger.debugLog('⚠️ CLEAN ARCH: Unknown control message type: ' + messageType, 'WARNING');
            break;
    }
}

function handleResultsMessage(data) {
    // Handle results category messages
    var messageType = data.type;
    
    debugLogger.debugLog('📊 CLEAN ARCH: Handling results message: ' + messageType);
    
    switch (messageType) {
        case 'triage_findings':
            handleTriageFindings(data);
            break;
            
        case 'context_research':
            handleContextResearch(data);
            break;
            
        case 'analysis_recommendations':
            handleAnalysisRecommendations(data);
            break;
            
        default:
            debugLogger.debugLog('⚠️ CLEAN ARCH: Unknown results message type: ' + messageType, 'WARNING');
            break;
    }
}

function handleStatusMessage(data) {
    // Handle status category messages
    var messageType = data.type;
    
    debugLogger.debugLog('📈 CLEAN ARCH: Handling status message: ' + messageType);
    
    switch (messageType) {
        case 'agent_status_update':
            handleAgentStatusUpdate(data);
            break;
            
        case 'agent_function_detected':
            handleAgentFunctionDetected(data);
            break;
            
        case 'agent_output_stream':
            handleAgentOutputStream(data);
            break;
            
        case 'workflow_progress':
            handleWorkflowProgress(data);
            break;
            
        default:
            debugLogger.debugLog('⚠️ CLEAN ARCH: Unknown status message type: ' + messageType, 'WARNING');
            break;
    }
}

function handleInteractionMessage(data) {
    // Handle interaction category messages
    var messageType = data.type;
    
    debugLogger.debugLog('👤 CLEAN ARCH: Handling interaction message: ' + messageType);
    
    switch (messageType) {
        case 'approval_request':
            handleApprovalRequest(data);
            break;
            
        case 'approval_timeout':
            handleApprovalTimeout(data);
            break;
            
        default:
            debugLogger.debugLog('⚠️ CLEAN ARCH: Unknown interaction message type: ' + messageType, 'WARNING');
            break;
    }
}

function handleUnknownMessage(data) {
    // Handle messages with unknown categories
    debugLogger.debugLog('❓ CLEAN ARCH: Unknown message category for type: ' + data.type, 'WARNING');
    
    // Log the message details for debugging
    console.log('❓ CLEAN ARCH: Unknown message details:', data);
    
    // Show warning to user
    ui.showStatus('⚠️ Received unknown message type: ' + data.type, 'warning');
}

// ============================================================================
// SPECIFIC MESSAGE HANDLERS
// ============================================================================

function handleConnectionEstablished(data) {
    // Handle connection established message
    currentSessionId = data.session_id;
    var features = data.features || [];
    var serverInfo = data.server_info || {};
    
    debugLogger.debugLog('✅ CLEAN ARCH: Connected with session ID: ' + currentSessionId);
    debugLogger.debugLog('🔧 CLEAN ARCH: Server features: ' + features.join(', '));
    debugLogger.debugLog('📋 CLEAN ARCH: Server info: ' + JSON.stringify(serverInfo));
    
    // Check if clean architecture is enabled
    if (features.includes('clean_message_architecture')) {
        cleanArchitectureEnabled = true;
        debugLogger.debugLog('✅ CLEAN ARCH: Clean message architecture enabled');
    }
    
    if (features.includes('type_validation')) {
        // Don't enable validation yet - wait for message types advertisement
        debugLogger.debugLog('🔧 CLEAN ARCH: Type validation available, waiting for type advertisement');
    }
    
    ui.showStatus('🚀 Connected to Clean Architecture SOC Analysis (v' + (serverInfo.version || 'unknown') + ')', 'success');
}

function handleMessageTypesAdvertisement(data) {
    // Handle message types advertisement
    if (data.supported_types) {
        supportedMessageTypes = data.supported_types;
        messageTypeValidationEnabled = true;
        
        debugLogger.debugLog('📢 CLEAN ARCH: Received ' + supportedMessageTypes.all_types.length + ' supported message types');
        debugLogger.debugLog('📋 CLEAN ARCH: Message categories: ' + Object.keys(supportedMessageTypes).join(', '));
        
        // Log type breakdown
        console.log('📊 CLEAN ARCH: Supported Message Types:', supportedMessageTypes);
        
        ui.showStatus('📢 Message types advertised - ' + supportedMessageTypes.all_types.length + ' types supported', 'info');
        
        // Now enable full clean architecture features
        if (cleanArchitectureEnabled) {
            ui.showStatus('✅ Clean Architecture fully enabled with type validation', 'success');
        }
    } else {
        debugLogger.debugLog('⚠️ CLEAN ARCH: No supported_types in advertisement message', 'WARNING');
    }
}

function handleTriageFindings(data) {
    // Handle structured triage findings
    var findings = data.data;
    
    if (findings && findings.threat_type && findings.source_ip) {
        var priority = findings.priority || 'medium';
        var threatType = findings.threat_type;
        var sourceIp = findings.source_ip;
        var targetHosts = findings.target_hosts || [];
        var attackPattern = findings.attack_pattern || 'Unknown pattern';
        var confidence = findings.confidence_score || 0;
        var eventCount = findings.event_count || 0;
        
        debugLogger.debugLog('🎯 CLEAN ARCH: Triage findings - ' + threatType + ' from ' + sourceIp);
        
        // Update agent state
        agentStates.triage.status = 'complete';
        agentStates.triage.has_findings = true;
        
        // Show notification
        ui.showStatus('🚨 Priority ' + priority.toUpperCase() + ' threat: ' + threatType + ' from ' + sourceIp, 'warning');
        
        // Update triage agent display
        var triageOutput = document.getElementById('triageOutput');
        if (triageOutput) {
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
        }
        
        // Update UI
        ui.updateAgentStatus('triage', 'complete');
        var triageCard = document.getElementById('triageCard');
        if (triageCard) {
            triageCard.classList.add('active');
            triageCard.style.borderLeft = '4px solid #56ab2f';
        }
        
        debugLogger.debugLog('✅ CLEAN ARCH: Triage findings processed and displayed');
    } else {
        debugLogger.debugLog('❌ CLEAN ARCH: Invalid triage findings data', 'ERROR');
    }
}

function handleContextResearch(data) {
    // Handle structured context research results
    var research = data.data;
    
    if (research) {
        var documentCount = research.total_documents_found || 0;
        var queries = research.search_queries || [];
        
        debugLogger.debugLog('📚 CLEAN ARCH: Context research - ' + documentCount + ' documents found');
        
        // Update agent state
        agentStates.context.status = 'complete';
        agentStates.context.has_research = true;
        
        // Show notification
        ui.showStatus('🔎 Found ' + documentCount + ' related historical incidents', 'info');
        
        // Update context agent display
        var contextOutput = document.getElementById('contextOutput');
        if (contextOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var researchOutput = '[' + timestamp + '] ✅ CONTEXT RESEARCH COMPLETE:\n' +
                '🔍 Search Queries: ' + queries.join(', ') + '\n' +
                '📚 Documents Found: ' + documentCount + '\n' +
                '📊 Pattern Analysis: ' + (research.pattern_analysis || 'None provided') + '\n' +
                '💡 Recommendations: ' + (research.recommendations || []).join(', ') + '\n' +
                '🎯 Confidence: ' + (research.confidence_assessment || 'Unknown');
            
            contextOutput.textContent = researchOutput;
            contextOutput.scrollTop = contextOutput.scrollHeight;
        }
        
        // Update UI
        ui.updateAgentStatus('context', 'complete');
        var contextCard = document.getElementById('contextCard');
        if (contextCard) {
            contextCard.classList.add('active');
            contextCard.style.borderLeft = '4px solid #56ab2f';
        }
        
        debugLogger.debugLog('✅ CLEAN ARCH: Context research processed and displayed');
    } else {
        debugLogger.debugLog('❌ CLEAN ARCH: Invalid context research data', 'ERROR');
    }
}

function handleAnalysisRecommendations(data) {
    // Handle structured analysis recommendations
    var analysis = data.data;
    
    if (analysis) {
        var actionCount = (analysis.recommended_actions || []).length;
        var businessImpact = analysis.business_impact || 'Under assessment';
        
        debugLogger.debugLog('👨‍💼 CLEAN ARCH: Analysis recommendations - ' + actionCount + ' actions');
        
        // Update agent state
        agentStates.analyst.status = 'complete';
        agentStates.analyst.has_recommendations = true;
        
        // Show notification
        ui.showStatus('👨‍💼 Analysis complete with ' + actionCount + ' recommendations', 'success');
        
        // Update analyst agent display
        var analystOutput = document.getElementById('analystOutput');
        if (analystOutput) {
            var timestamp = new Date().toLocaleTimeString();
            var analysisOutput = '[' + timestamp + '] ✅ DETAILED ANALYSIS COMPLETE:\n' +
                '🎯 Threat Assessment: ' + (analysis.threat_assessment?.severity || 'Unknown') + '\n' +
                '📋 Recommendations: ' + actionCount + ' actions\n' +
                '💼 Business Impact: ' + businessImpact + '\n' +
                '🔒 Confidence: ' + (analysis.threat_assessment?.confidence || 'Unknown') + '\n' +
                '📝 Notes: ' + (analysis.investigation_notes || 'None provided') + '\n' +
                '⚡ Actions: ' + (analysis.recommended_actions || []).join(', ');
            
            analystOutput.textContent = analysisOutput;
            analystOutput.scrollTop = analystOutput.scrollHeight;
        }
        
        // Update UI
        ui.updateAgentStatus('analyst', 'complete');
        var analystCard = document.getElementById('analystCard');
        if (analystCard) {
            analystCard.classList.add('active');
            analystCard.style.borderLeft = '4px solid #56ab2f';
        }
        
        debugLogger.debugLog('✅ CLEAN ARCH: Analysis recommendations processed and displayed');
    } else {
        debugLogger.debugLog('❌ CLEAN ARCH: Invalid analysis recommendations data', 'ERROR');
    }
}

function handleAgentStatusUpdate(data) {
    // Handle agent status update messages
    var agent = data.agent;
    var status = data.status;
    var message = data.message;
    var previousStatus = data.previous_status;
    
    debugLogger.debugLog('📊 CLEAN ARCH: Agent status update - ' + agent + ': ' + previousStatus + ' → ' + status);
    
    // Update agent state
    if (agentStates[agent]) {
        agentStates[agent].status = status;
    }
    
    // Update UI
    ui.updateAgentStatus(agent, status);
    
    if (message) {
        ui.showStatus(agent.charAt(0).toUpperCase() + agent.slice(1) + ': ' + message, 'info');
    }
}

function handleAgentFunctionDetected(data) {
    // Handle agent function detection messages
    var agent = data.agent;
    var functionName = data.function_name;
    var description = data.description;
    
    debugLogger.debugLog('🔧 CLEAN ARCH: Function detected - ' + functionName + ' from ' + agent);
    
    // Show notification
    ui.showStatus('🔧 Function call: ' + functionName + ' from ' + agent, 'info');
    
    // Update agent status to show it's processing
    ui.updateAgentStatus(agent, 'active');
    
    // Add visual feedback
    var agentCard = document.getElementById(agent + 'Card');
    if (agentCard) {
        agentCard.style.borderLeft = '4px solid #f39c12';
        agentCard.style.boxShadow = '0 0 20px rgba(243, 156, 18, 0.4)';
    }
}

function handleAgentOutputStream(data) {
    // Handle real-time agent output streaming
    var agent = data.agent;
    var content = data.content;
    var isFinal = data.is_final;
    
    debugLogger.debugLog('💬 CLEAN ARCH: Agent output stream from ' + agent + ': ' + content.substring(0, 50) + '...');
    
    // Update agent output
    var outputElement = document.getElementById(agent + 'Output');
    if (outputElement) {
        var timestamp = new Date().toLocaleTimeString();
        var formattedContent = '[' + timestamp + '] ' + content;
        
        // Smart content management
        var existingContent = outputElement.textContent;
        
        if (existingContent.includes('Waiting for') || 
            existingContent.includes('waiting') ||
            existingContent.length < 50) {
            // Replace placeholder text
            outputElement.textContent = formattedContent;
        } else {
            // Append new content
            outputElement.textContent = existingContent + '\n\n' + formattedContent;
        }
        
        // Auto-scroll
        outputElement.scrollTop = outputElement.scrollHeight;
    }
    
    // Mark as active if not already
    if (agentStates[agent] && agentStates[agent].status === 'pending') {
        ui.updateAgentStatus(agent, 'active');
    }
}

function handleWorkflowProgress(data) {
    // Handle workflow progress updates
    var progressPercentage = data.progress_percentage;
    var currentStage = data.current_stage;
    var completedStages = data.completed_stages || [];
    var estimatedTimeRemaining = data.estimated_time_remaining;
    
    debugLogger.debugLog('📈 CLEAN ARCH: Workflow progress - ' + progressPercentage + '% - ' + currentStage);
    
    // Update global progress state
    workflowProgress.current_stage = currentStage;
    workflowProgress.progress_percentage = progressPercentage;
    workflowProgress.completed_stages = completedStages;
    workflowProgress.estimated_time_remaining = estimatedTimeRemaining;
    
    // Update UI progress
    ui.updateProgress(progressPercentage, currentStage);
    
    // Show stage transition notifications
    if (currentStage !== workflowProgress.current_stage) {
        ui.showStatus('📈 Stage: ' + currentStage, 'info');
    }
}

function handleApprovalRequest(data) {
    // Handle approval request messages
    var stage = data.stage;
    var prompt = data.prompt;
    var context = data.context || {};
    var timeoutSeconds = data.timeout_seconds || 300;
    
    debugLogger.debugLog('👤 CLEAN ARCH: Approval request for ' + stage + ' stage');
    
    // Create approval request data for the approval workflow
    var approvalData = {
        type: 'approval_request',
        content: prompt,
        source: stage + 'Agent',
        stage: stage,
        context: context,
        timeout_seconds: timeoutSeconds,
        session_id: currentSessionId
    };
    
    // Use the existing approval workflow handler
    approvalWorkflow.handleApprovalRequest(approvalData);
}

function handleApprovalTimeout(data) {
    // Handle approval timeout messages
    var stage = data.stage;
    var defaultAction = data.default_action;
    
    debugLogger.debugLog('⏰ CLEAN ARCH: Approval timeout for ' + stage + ' stage');
    
    ui.showStatus('⏰ Approval timeout for ' + stage + ' - ' + defaultAction, 'warning');
    
    // Use the existing approval workflow timeout handler
    approvalWorkflow.handleApprovalTimeout(data);
}

function handleAnalysisComplete(data) {
    // Handle analysis completion messages
    var success = data.success;
    var resultsSummary = data.results_summary || {};
    var duration = data.duration_seconds;
    
    debugLogger.debugLog('🎉 CLEAN ARCH: Analysis complete - Success: ' + success + ', Duration: ' + duration + 's');
    
    if (success) {
        ui.showStatus('🎉 Multi-agent analysis completed successfully!', 'success');
        ui.updateProgress(100, 'Analysis complete');
        
        // Show final results summary
        setTimeout(function() {
            showCleanArchitectureResultsSummary(resultsSummary);
        }, 1000);
    } else {
        ui.showStatus('⚠️ Analysis completed with issues', 'warning');
        ui.updateProgress(100, 'Completed with issues');
    }
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    approvalWorkflow.setAwaitingApproval(false);
    
    // Enable the analyze button again
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function handleWorkflowRejected(data) {
    // Handle workflow rejection messages
    var rejectedStage = data.rejected_stage;
    var reason = data.reason;
    
    debugLogger.debugLog('❌ CLEAN ARCH: Workflow rejected at ' + rejectedStage + ' stage');
    
    ui.showStatus('❌ Workflow rejected at ' + rejectedStage + ' stage: ' + (reason || 'User decision'), 'error');
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

function handleErrorMessage(data) {
    // Handle error messages
    var errorMessage = data.message;
    var errorCode = data.error_code;
    var details = data.details;
    
    debugLogger.debugLog('💥 CLEAN ARCH: Error received - ' + errorMessage, 'ERROR');
    
    var displayMessage = errorMessage;
    if (errorCode) {
        displayMessage = '[' + errorCode + '] ' + errorMessage;
    }
    
    ui.showStatus('❌ ' + displayMessage, 'error');
    
    if (details) {
        console.error('Error details:', details);
    }
};

function handleLogsRetrieved(data) {
    // Handle logs retrieved messages
    var logs = data.logs;
    var count = data.count;
    var message = data.message;
    
    debugLogger.debugLog('📥 CLEAN ARCH: Logs retrieved - ' + count + ' entries');
    
    progressManager.handleLogsRetrieved({
        logs: logs,
        message: message
    });
};

function handlePongMessage(data) {
    // Handle pong response messages
    debugLogger.debugLog('🏓 CLEAN ARCH: Received pong from server');
    ui.showStatus('🏓 Server responded to ping', 'info');
};

// ============================================================================
// RESULTS SUMMARY
// ============================================================================

function showCleanArchitectureResultsSummary(resultsSummary) {
    debugLogger.debugLog('📊 CLEAN ARCH: Showing results summary');
    
    var findings = [];
    
    // Check agent states and build findings
    if (agentStates.triage.has_findings) {
        findings.push({
            title: '🚨 Triage Results',
            content: 'Priority threat assessment completed with structured findings, threat classification, and source identification.'
        });
    }
    
    if (agentStates.context.has_research) {
        findings.push({
            title: '📚 Historical Context',
            content: 'Related historical incidents analyzed for pattern matching, threat correlation, and lessons learned integration.'
        });
    }
    
    if (agentStates.analyst.has_recommendations) {
        findings.push({
            title: '🎯 Deep Analysis Complete',
            content: 'Comprehensive analysis completed with actionable recommendations, business impact assessment, and implementation timeline.'
        });
    }
    
    // Add clean architecture specific findings
    findings.push({
        title: '🔧 Clean Architecture',
        content: 'Analysis completed using clean message architecture with ' + supportedMessageTypes.all_types.length + ' validated message types and type-safe communication.'
    });
    
    // Show the findings
    if (findings.length > 0) {
        ui.displayFinalResults({
            structured_findings: {
                priority_threat: {
                    priority: 'high',
                    threat_type: 'Clean Architecture Multi-stage Analysis',
                    brief_summary: 'Real-time analysis completed successfully with clean message architecture'
                }
            },
            chroma_context: {}
        });
    }
};

// ============================================================================
// MESSAGE SENDING WITH VALIDATION
// ============================================================================

function sendWebSocketMessage(message) {
    // Send WebSocket message with type validation
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        var messageString = JSON.stringify(message);
        websocket.send(messageString);
        wsStats.messages_sent++;
        
        debugLogger.debugLog('📤 CLEAN ARCH: WebSocket message sent - Type: ' + message.type);
        console.log('📤 CLEAN ARCH: Sent message:', message);
        return true;
    } else {
        debugLogger.debugLog('❌ CLEAN ARCH: WebSocket not connected, cannot send message - ReadyState: ' + (websocket ? websocket.readyState : 'null'), 'ERROR');
        ui.showStatus('❌ Not connected to server', 'error');
        return false;
    }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function showWebSocketStats() {
    // Show WebSocket statistics including clean architecture info
    var agentStatesStr = Object.keys(agentStates).map(function(agent) {
        var state = agentStates[agent];
        return agent + ': ' + state.status + (state.has_findings || state.has_research || state.has_recommendations ? ' (has_data)' : '');
    }).join(', ');
    
    var stats = 'Clean Architecture WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Type Validation Errors: ' + wsStats.type_validation_errors + '\n' +
        'Reconnects: ' + wsStats.reconnects + '\n' +
        'Connection State: ' + (websocket ? websocket.readyState : 'No connection') + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        'Clean Architecture: ' + (cleanArchitectureEnabled ? 'Enabled' : 'Disabled') + '\n' +
        'Type Validation: ' + (messageTypeValidationEnabled ? 'Enabled' : 'Disabled') + '\n' +
        'Supported Types: ' + supportedMessageTypes.all_types.length + '\n' +
        'Workflow Progress: ' + workflowProgress
        'Agent States: ' + agentStatesStr;

    debugLogger.debugLog(stats);
    logMessageTypeStats();
    ui.showStatus('📊 Clean Architecture WebSocket stats logged to console', 'info');
}

function testConnection() {
    // Test WebSocket connection
    debugLogger.debugLog('🔍 Testing clean architecture WebSocket connection');
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        if (sendWebSocketMessage({ type: 'ping', session_id: currentSessionId })) {
            ui.showStatus('🏓 Ping sent to clean architecture server', 'info');
        }
    } else {
        debugLogger.debugLog('❌ Cannot test connection - WebSocket not ready. State: ' + (websocket ? websocket.readyState : 'null'), 'WARNING');
        ui.showStatus('❌ Clean Architecture WebSocket not connected', 'warning');
    }
}

function getCurrentSessionId() {
    return currentSessionId;
}

function getWebSocket() {
    return websocket;
}

function getConnectionStats() {
    return {
        ...wsStats,
        clean_architecture_enabled: cleanArchitectureEnabled,
        type_validation_enabled: messageTypeValidationEnabled,
        supported_types_count: supportedMessageTypes.all_types.length,
        agent_states: agentStates,
        workflow_progress: workflowProgress
    };
}

function getSupportedMessageTypes() {
    return supportedMessageTypes;
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
    getSupportedMessageTypes,
    validateMessageType,
    getMessageCategory,
    logMessageTypeStats
};
