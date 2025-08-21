// services/ai-agents/src/static/js/websocket.js - AGENT DISPLAY FIX
// Fixed version with enhanced debugging and proper agent isolation

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// ============================================================================
// ENHANCED DEBUGGING AND AGENT STATE TRACKING
// ============================================================================

var websocket = null;
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;
var currentSessionId = null;

// ENHANCED: Track which agents have been activated to prevent confusion
var agentActivationState = {
    triage: { activated: false, completed: false, lastUpdate: null },
    context: { activated: false, completed: false, lastUpdate: null },
    analyst: { activated: false, completed: false, lastUpdate: null }
};

// Domain-focused message types that the UI cares about
const DOMAIN_MESSAGE_TYPES = {
    // Security domain results
    'triage_findings': true,
    'context_research': true, 
    'analysis_recommendations': true,
    
    // User interaction
    'approval_request': true,
    'approval_timeout': true,
    
    // High-level workflow
    'workflow_progress': true,
    'analysis_complete': true,
    'workflow_rejected': true,
    
    // System control (essential only)
    'connection_established': true,
    'message_types_advertisement': true,
    'error': true,
    'logs_retrieved': true,
    'pong': true
};

// ENHANCED: Domain state tracking with better isolation
var securityFindings = {
    triage: { 
        threat_detected: false, 
        priority: null, 
        threat_type: null, 
        source_ip: null,
        processed: false,
        timestamp: null
    },
    context: { 
        historical_incidents: 0, 
        patterns_found: false,
        processed: false,
        timestamp: null
    },
    analyst: { 
        recommendations_count: 0, 
        business_impact: null,
        processed: false,
        timestamp: null
    }
};

// ============================================================================
// WEBSOCKET INITIALIZATION (unchanged)
// ============================================================================

function initWebSocket() {
    console.log('🚀 DOMAIN-FOCUSED: Initializing Security Domain WebSocket');
    var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var wsUrl = protocol + '//' + window.location.host + '/ws/analysis';

    debugLogger.debugLog('🔌 DOMAIN: Connecting to WebSocket: ' + wsUrl);
    progressManager.updateConnectionStatus('connecting');

    websocket = new WebSocket(wsUrl);

    websocket.onopen = function(event) {
        debugLogger.debugLog('✅ DOMAIN: WebSocket connection established');
        progressManager.updateConnectionStatus('connected');
        wsStats.connected = true;
        reconnectAttempts = 0;

        // Reset agent state on new connection
        resetAgentStates();
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        
        try {
            var data = JSON.parse(event.data);
            
            // ENHANCED: Add message reception logging
            debugLogger.debugLog('📨 RAW MESSAGE: Type=' + data.type + ', Agent=' + (data.agent || 'unknown') + ', Session=' + (data.session_id || 'none'));
            
            // Filter messages - only process domain-relevant ones
            if (isDomainRelevantMessage(data.type)) {
                debugLogger.debugLog('📨 DOMAIN: Processing security domain message - Type: ' + data.type);
                handleDomainMessage(data);
            } else {
                // Log technical messages but don't process them in UI
                debugLogger.debugLog('🔧 TECHNICAL: Filtered out technical message - Type: ' + data.type);
            }
            
        } catch (e) {
            console.error('❌ Error parsing WebSocket message:', e);
            debugLogger.debugLog('❌ WebSocket message parse error: ' + e, 'ERROR');
        }
    };

    websocket.onclose = function(event) {
        debugLogger.debugLog('🔌 DOMAIN: WebSocket connection closed: ' + event.code + ' - ' + event.reason);
        progressManager.updateConnectionStatus('disconnected');
        wsStats.connected = false;

        if (!event.wasClean && reconnectAttempts < maxReconnectAttempts) {
            reconnectAttempts++;
            ui.showStatus('🔄 Connection lost. Reconnecting... (' + reconnectAttempts + '/' + maxReconnectAttempts + ')', 'warning');
            setTimeout(function() {
                initWebSocket();
            }, 2000 * reconnectAttempts);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
            ui.showStatus('❌ Connection failed. Please refresh the page.', 'error');
        }
    };

    websocket.onerror = function(error) {
        debugLogger.debugLog('❌ DOMAIN: WebSocket error: ' + error, 'ERROR');
        progressManager.updateConnectionStatus('error');
        ui.showStatus('❌ Security Analysis WebSocket connection error', 'error');
    };
}

// ============================================================================
// ENHANCED AGENT STATE MANAGEMENT
// ============================================================================

function resetAgentStates() {
    debugLogger.debugLog('🔄 DOMAIN: Resetting all agent states');
    
    // Reset activation tracking
    Object.keys(agentActivationState).forEach(function(agent) {
        agentActivationState[agent] = { 
            activated: false, 
            completed: false, 
            lastUpdate: null 
        };
    });
    
    // Reset security findings
    securityFindings.triage.processed = false;
    securityFindings.context.processed = false;
    securityFindings.analyst.processed = false;
    
    debugLogger.debugLog('✅ DOMAIN: Agent states reset successfully');
}

function validateAgentState(agentType, operation) {
    var state = agentActivationState[agentType];
    if (!state) {
        debugLogger.debugLog('❌ AGENT STATE: Unknown agent type: ' + agentType, 'ERROR');
        return false;
    }
    
    debugLogger.debugLog('🔍 AGENT STATE: ' + agentType + ' - Activated: ' + state.activated + ', Completed: ' + state.completed + ', Operation: ' + operation);
    
    // Prevent duplicate processing
    if (operation === 'complete' && state.completed) {
        debugLogger.debugLog('⚠️ AGENT STATE: ' + agentType + ' already completed, skipping duplicate', 'WARNING');
        return false;
    }
    
    return true;
}

function updateAgentState(agentType, operation) {
    if (!validateAgentState(agentType, operation)) {
        return false;
    }
    
    var state = agentActivationState[agentType];
    state.lastUpdate = new Date().toISOString();
    
    if (operation === 'activate') {
        state.activated = true;
        state.completed = false;
        debugLogger.debugLog('✅ AGENT STATE: ' + agentType + ' activated');
    } else if (operation === 'complete') {
        state.activated = true;
        state.completed = true;
        debugLogger.debugLog('✅ AGENT STATE: ' + agentType + ' completed');
    }
    
    return true;
}

// ============================================================================
// DOMAIN MESSAGE FILTERING (unchanged)
// ============================================================================

function isDomainRelevantMessage(messageType) {
    return DOMAIN_MESSAGE_TYPES[messageType] === true;
}

function handleDomainMessage(data) {
    var messageType = data.type;
    
    debugLogger.debugLog('🎯 DOMAIN: Handling security domain message: ' + messageType);
    
    switch (messageType) {
        // === SECURITY DOMAIN RESULTS ===
        case 'triage_findings':
            handleSecurityTriage(data);
            break;
            
        case 'context_research':
            handleSecurityContext(data);
            break;
            
        case 'analysis_recommendations':
            handleSecurityRecommendations(data);
            break;
            
        // === USER INTERACTION ===
        case 'approval_request':
            handleApprovalRequest(data);
            break;
            
        case 'approval_timeout':
            handleApprovalTimeout(data);
            break;
            
        // === HIGH-LEVEL WORKFLOW ===
        case 'workflow_progress':
            handleWorkflowProgress(data);
            break;
            
        case 'analysis_complete':
            handleAnalysisComplete(data);
            break;
            
        case 'workflow_rejected':
            handleWorkflowRejected(data);
            break;
            
        // === ESSENTIAL SYSTEM CONTROL ===
        case 'connection_established':
            handleConnectionEstablished(data);
            break;
            
        case 'message_types_advertisement':
            handleMessageTypesAdvertisement(data);
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
            debugLogger.debugLog('⚠️ DOMAIN: Unknown domain message type: ' + messageType, 'WARNING');
            break;
    }
}

// ============================================================================
// ENHANCED SECURITY DOMAIN MESSAGE HANDLERS
// ============================================================================

function handleSecurityTriage(data) {
    debugLogger.debugLog('🚨 DOMAIN: Processing TRIAGE findings message');
    
    // Validate this is actually a triage message
    if (data.agent && data.agent !== 'triage') {
        debugLogger.debugLog('❌ TRIAGE: Message marked for wrong agent: ' + data.agent, 'ERROR');
        return;
    }
    
    // Prevent duplicate processing
    if (securityFindings.triage.processed) {
        debugLogger.debugLog('⚠️ TRIAGE: Already processed, skipping duplicate', 'WARNING');
        return;
    }
    
    if (!updateAgentState('triage', 'complete')) {
        return;
    }
    
    var findings = data.data;
    
    if (findings && findings.threat_type && findings.source_ip) {
        var priority = findings.priority || 'medium';
        var threatType = findings.threat_type;
        var sourceIp = findings.source_ip;
        var confidence = findings.confidence_score || 0;
        
        debugLogger.debugLog('🚨 SECURITY: Threat detected - ' + threatType + ' from ' + sourceIp + ' (Priority: ' + priority + ')');
        
        // Update security state
        securityFindings.triage = {
            threat_detected: true,
            priority: priority,
            threat_type: threatType,
            source_ip: sourceIp,
            confidence: confidence,
            attack_pattern: findings.attack_pattern,
            target_hosts: findings.target_hosts || [],
            brief_summary: findings.brief_summary,
            processed: true,
            timestamp: new Date().toISOString()
        };
        
        // ENHANCED: Explicit UI targeting with validation
        debugLogger.debugLog('🎯 TRIAGE: Updating UI elements for TRIAGE agent');
        ui.updateAgentStatus('triage', 'complete');
        updateTriageDisplay(securityFindings.triage);
        
        // Show security-focused notification
        ui.showStatus('🚨 ' + priority.toUpperCase() + ' Priority Threat: ' + threatType + ' from ' + sourceIp, 'warning');
        
        debugLogger.debugLog('✅ SECURITY: Threat assessment complete and displayed');
    } else {
        debugLogger.debugLog('❌ SECURITY: Invalid triage findings data', 'ERROR');
    }
}

function handleSecurityContext(data) {
    debugLogger.debugLog('📚 DOMAIN: Processing CONTEXT research message');
    
    // Validate this is actually a context message
    if (data.agent && data.agent !== 'context') {
        debugLogger.debugLog('❌ CONTEXT: Message marked for wrong agent: ' + data.agent, 'ERROR');
        return;
    }
    
    // Prevent duplicate processing
    if (securityFindings.context.processed) {
        debugLogger.debugLog('⚠️ CONTEXT: Already processed, skipping duplicate', 'WARNING');
        return;
    }
    
    if (!updateAgentState('context', 'complete')) {
        return;
    }
    
    var research = data.data;
    
    if (research) {
        var documentCount = research.total_documents_found || 0;
        var patternAnalysis = research.pattern_analysis || 'No patterns identified';
        
        debugLogger.debugLog('📚 SECURITY: Historical context - ' + documentCount + ' related incidents');
        
        // Update security state
        securityFindings.context = {
            historical_incidents: documentCount,
            patterns_found: documentCount > 0,
            pattern_analysis: patternAnalysis,
            search_queries: research.search_queries || [],
            processed: true,
            timestamp: new Date().toISOString()
        };
        
        // ENHANCED: Explicit UI targeting with validation
        debugLogger.debugLog('🎯 CONTEXT: Updating UI elements for CONTEXT agent');
        ui.updateAgentStatus('context', 'complete');
        updateContextDisplay(securityFindings.context);
        
        // Show security-focused notification
        ui.showStatus('📚 Found ' + documentCount + ' related security incidents', 'info');
        
        debugLogger.debugLog('✅ SECURITY: Historical context analysis complete');
    } else {
        debugLogger.debugLog('❌ SECURITY: Invalid context research data', 'ERROR');
    }
}

function handleSecurityRecommendations(data) {
    debugLogger.debugLog('🎯 DOMAIN: Processing ANALYST recommendations message');
    
    // Validate this is actually an analyst message
    if (data.agent && data.agent !== 'analyst') {
        debugLogger.debugLog('❌ ANALYST: Message marked for wrong agent: ' + data.agent, 'ERROR');
        return;
    }
    
    // Prevent duplicate processing
    if (securityFindings.analyst.processed) {
        debugLogger.debugLog('⚠️ ANALYST: Already processed, skipping duplicate', 'WARNING');
        return;
    }
    
    if (!updateAgentState('analyst', 'complete')) {
        return;
    }
    
    var analysis = data.data;
    
    if (analysis) {
        var recommendations = analysis.recommended_actions || [];
        var businessImpact = analysis.business_impact || 'Under assessment';
        var threatAssessment = analysis.threat_assessment || {};
        
        debugLogger.debugLog('🎯 SECURITY: Analysis complete - ' + recommendations.length + ' recommendations');
        
        // Update security state
        securityFindings.analyst = {
            recommendations_count: recommendations.length,
            business_impact: businessImpact,
            recommended_actions: recommendations,
            threat_severity: threatAssessment.severity,
            investigation_notes: analysis.investigation_notes,
            processed: true,
            timestamp: new Date().toISOString()
        };
        
        // ENHANCED: Explicit UI targeting with validation
        debugLogger.debugLog('🎯 ANALYST: Updating UI elements for ANALYST agent');
        ui.updateAgentStatus('analyst', 'complete');
        updateAnalystDisplay(securityFindings.analyst);
        
        // Show security-focused notification
        ui.showStatus('🎯 Security analysis complete: ' + recommendations.length + ' recommendations', 'success');
        
        debugLogger.debugLog('✅ SECURITY: Security recommendations complete');
    } else {
        debugLogger.debugLog('❌ SECURITY: Invalid analysis recommendations data', 'ERROR');
    }
}

// ============================================================================
// ENHANCED UI UPDATE FUNCTIONS WITH VALIDATION
// ============================================================================

function updateTriageDisplay(triageData) {
    debugLogger.debugLog('🎯 UI: Updating TRIAGE display elements');
    
    // ENHANCED: Validate element exists before updating
    var triageOutput = document.getElementById('triageOutput');
    if (!triageOutput) {
        debugLogger.debugLog('❌ UI: triageOutput element not found!', 'ERROR');
        return;
    }
    
    var securitySummary = '🚨 THREAT ASSESSMENT COMPLETE\n\n' +
        '⚠️  Priority: ' + triageData.priority.toUpperCase() + '\n' +
        '🎯 Threat Type: ' + triageData.threat_type + '\n' +
        '📍 Source IP: ' + triageData.source_ip + '\n' +
        '🎯 Targets: ' + (triageData.target_hosts.length > 0 ? triageData.target_hosts.join(', ') : 'Multiple') + '\n' +
        '📊 Confidence: ' + (triageData.confidence * 100).toFixed(1) + '%\n' +
        '🔍 Pattern: ' + (triageData.attack_pattern || 'Unknown') + '\n\n' +
        '📋 Summary: ' + (triageData.brief_summary || 'Threat detected and classified for investigation');
    
    triageOutput.textContent = securitySummary;
    debugLogger.debugLog('✅ UI: TRIAGE content updated successfully');
    
    // Add visual security indicator
    var triageCard = document.getElementById('triageCard');
    if (triageCard) {
        triageCard.classList.add('active');
        debugLogger.debugLog('✅ UI: TRIAGE card marked as active');
    } else {
        debugLogger.debugLog('❌ UI: triageCard element not found!', 'ERROR');
    }
}

function updateContextDisplay(contextData) {
    debugLogger.debugLog('🎯 UI: Updating CONTEXT display elements');
    
    // ENHANCED: Validate element exists before updating
    var contextOutput = document.getElementById('contextOutput');
    if (!contextOutput) {
        debugLogger.debugLog('❌ UI: contextOutput element not found!', 'ERROR');
        return;
    }
    
    var contextSummary = '📚 HISTORICAL CONTEXT ANALYSIS\n\n' +
        '📊 Related Incidents: ' + contextData.historical_incidents + '\n' +
        '🔍 Pattern Analysis: ' + (contextData.patterns_found ? 'Patterns identified' : 'No clear patterns') + '\n' +
        '📝 Search Scope: ' + (contextData.search_queries.length > 0 ? contextData.search_queries.join(', ') : 'General threat patterns') + '\n\n' +
        '📋 Analysis: ' + contextData.pattern_analysis;
    
    // NEW: Add detailed document and distance information if available
    if (contextData.all_documents && contextData.all_distances) {
        contextSummary += '\n\n' + '=' * 50 + '\n';
        contextSummary += '📄 DETAILED HISTORICAL DOCUMENTS & RELEVANCE SCORES\n';
        contextSummary += '=' * 50 + '\n\n';
        
        var documentCount = Math.min(contextData.all_documents.length, contextData.all_distances.length);
        
        if (documentCount > 0) {
            contextSummary += 'Found ' + documentCount + ' historical documents (lower score = more relevant):\n\n';
            
            // Create pairs of documents and distances, sort by relevance (lowest distance first)
            var documentPairs = [];
            for (var i = 0; i < documentCount; i++) {
                documentPairs.push({
                    document: contextData.all_documents[i],
                    distance: contextData.all_distances[i],
                    index: i + 1
                });
            }
            
            // Sort by distance (most relevant first)
            documentPairs.sort(function(a, b) {
                return a.distance - b.distance;
            });
            
            // Display documents with their relevance scores
            for (var i = 0; i < documentPairs.length; i++) {
                var pair = documentPairs[i];
                var relevancePercent = ((1 - pair.distance) * 100).toFixed(1);
                
                contextSummary += 'Document #' + pair.index + ' (Relevance: ' + relevancePercent + '%):\n';
                contextSummary += 'Distance Score: ' + pair.distance.toFixed(4) + '\n';
                
                // Truncate long documents for display
                var docText = pair.document;
                if (docText.length > 200) {
                    docText = docText.substring(0, 200) + '... [truncated]';
                }
                contextSummary += 'Content: ' + docText + '\n';
                contextSummary += '-' * 80 + '\n';
            }
            
            // Add summary statistics
            var avgDistance = contextData.all_distances.reduce(function(sum, dist) { return sum + dist; }, 0) / contextData.all_distances.length;
            var minDistance = Math.min.apply(Math, contextData.all_distances);
            var maxDistance = Math.max.apply(Math, contextData.all_distances);
            
            contextSummary += '\n📊 RELEVANCE STATISTICS:\n';
            contextSummary += 'Average Distance: ' + avgDistance.toFixed(4) + '\n';
            contextSummary += 'Best Match (Min Distance): ' + minDistance.toFixed(4) + '\n';
            contextSummary += 'Worst Match (Max Distance): ' + maxDistance.toFixed(4) + '\n';
            contextSummary += 'Total Documents Analyzed: ' + documentCount + '\n';
        } else {
            contextSummary += 'No historical documents found with distance scores.\n';
        }
    }
    
    contextOutput.textContent = contextSummary;
    debugLogger.debugLog('✅ UI: CONTEXT content updated successfully with all documents and distances');
    
    // Add visual context indicator
    var contextCard = document.getElementById('contextCard');
    if (contextCard) {
        contextCard.classList.add('active');
        debugLogger.debugLog('✅ UI: CONTEXT card marked as active');
    } else {
        debugLogger.debugLog('❌ UI: contextCard element not found!', 'ERROR');
    }
}

function updateAnalystDisplay(analystData) {
    debugLogger.debugLog('🎯 UI: Updating ANALYST display elements');
    
    // ENHANCED: Validate element exists before updating
    var analystOutput = document.getElementById('analystOutput');
    if (!analystOutput) {
        debugLogger.debugLog('❌ UI: analystOutput element not found!', 'ERROR');
        return;
    }
    
    var recommendationsSummary = '🎯 SECURITY ANALYSIS COMPLETE\n\n' +
        '📊 Recommendations: ' + analystData.recommendations_count + ' actions identified\n' +
        '⚠️  Threat Level: ' + (analystData.threat_severity || 'Under assessment') + '\n' +
        '💼 Business Impact: ' + analystData.business_impact + '\n\n' +
        '📋 Recommended Actions:\n' +
        (analystData.recommended_actions.length > 0 ? 
            analystData.recommended_actions.map(function(action, index) {
                return '   ' + (index + 1) + '. ' + action;
            }).join('\n') : 
            '   No specific actions identified') + '\n\n' +
        '📝 Notes: ' + (analystData.investigation_notes || 'Analysis complete - review recommendations');
    
    analystOutput.textContent = recommendationsSummary;
    debugLogger.debugLog('✅ UI: ANALYST content updated successfully');
    
    // Add visual completion indicator
    var analystCard = document.getElementById('analystCard');
    if (analystCard) {
        analystCard.classList.add('active');
        debugLogger.debugLog('✅ UI: ANALYST card marked as active');
    } else {
        debugLogger.debugLog('❌ UI: analystCard element not found!', 'ERROR');
    }
}

// ============================================================================
// OTHER DOMAIN MESSAGE HANDLERS (rest of the functions remain the same)
// ============================================================================

function handleApprovalRequest(data) {
    approvalWorkflow.handleApprovalRequest(data);
}

function handleApprovalTimeout(data) {
    approvalWorkflow.handleApprovalTimeout(data);
}

function handleWorkflowProgress(data) {
    var progressPercentage = data.progress_percentage;
    var currentStage = data.current_stage;
    
    debugLogger.debugLog('📈 DOMAIN: Workflow progress - ' + progressPercentage + '% - ' + currentStage);
    
    var domainStage = convertToDomainStage(currentStage);
    ui.updateProgress(progressPercentage, domainStage);
}

function convertToDomainStage(technicalStage) {
    var stageMapping = {
        'initializing': 'Initializing Security Analysis',
        'triage_active': 'Assessing Threats',
        'triage_complete': 'Threat Assessment Complete',
        'context_active': 'Analyzing Historical Context',
        'context_complete': 'Historical Analysis Complete',
        'analyst_active': 'Generating Recommendations',
        'analyst_complete': 'Security Analysis Complete',
        'finalizing': 'Finalizing Results'
    };
    
    return stageMapping[technicalStage] || technicalStage;
}

function handleAnalysisComplete(data) {
    var success = data.success;
    
    debugLogger.debugLog('🎉 SECURITY: Analysis complete - Success: ' + success);
    
    if (success) {
        ui.showStatus('🎉 Security analysis completed successfully!', 'success');
        ui.updateProgress(100, 'Security Analysis Complete');
        
        setTimeout(function() {
            showSecurityResultsSummary();
        }, 1000);
    } else {
        ui.showStatus('⚠️ Security analysis completed with issues', 'warning');
        ui.updateProgress(100, 'Completed with issues');
    }
    
    progressManager.setAnalysisInProgress(false);
    
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function handleWorkflowRejected(data) {
    var rejectedStage = data.rejected_stage;
    
    debugLogger.debugLog('❌ SECURITY: Analysis rejected at ' + rejectedStage + ' stage');
    
    ui.showStatus('❌ Security analysis rejected at ' + rejectedStage + ' stage', 'error');
    ui.updateProgress(100, 'Analysis Rejected');
    
    progressManager.setAnalysisInProgress(false);
    
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function showSecurityResultsSummary() {
    debugLogger.debugLog('📊 SECURITY: Showing domain-focused results summary');
    
    var findings = [];
    
    if (securityFindings.triage.threat_detected) {
        findings.push({
            title: '🚨 Security Threat Identified',
            content: securityFindings.triage.priority.toUpperCase() + ' priority ' + 
                    securityFindings.triage.threat_type + ' detected from ' + 
                    securityFindings.triage.source_ip + '. ' +
                    (securityFindings.triage.brief_summary || 'Threat classified and ready for response.')
        });
    }
    
    if (securityFindings.context.historical_incidents > 0) {
        findings.push({
            title: '📚 Historical Context',
            content: 'Found ' + securityFindings.context.historical_incidents + 
                    ' related security incidents. ' + 
                    (securityFindings.context.patterns_found ? 'Attack patterns identified for correlation.' : 'No clear attack patterns identified.')
        });
    }
    
    if (securityFindings.analyst.recommendations_count > 0) {
        findings.push({
            title: '🎯 Security Recommendations',
            content: securityFindings.analyst.recommendations_count + ' actionable security recommendations generated. ' +
                    'Business impact: ' + securityFindings.analyst.business_impact + '.'
        });
    }
    
    if (findings.length > 0) {
        ui.displayFinalResults({
            structured_findings: {
                priority_threat: {
                    priority: securityFindings.triage.priority || 'medium',
                    threat_type: securityFindings.triage.threat_type || 'Security Analysis Complete',
                    brief_summary: 'Domain-focused security analysis completed successfully'
                }
            },
            chroma_context: {}
        });
    }
}

// ============================================================================
// ESSENTIAL SYSTEM HANDLERS
// ============================================================================

function handleConnectionEstablished(data) {
    currentSessionId = data.session_id;
    debugLogger.debugLog('✅ SECURITY: Connected with session ID: ' + currentSessionId);
    ui.showStatus('🔌 Connected to Security Analysis System', 'success');
}

function handleMessageTypesAdvertisement(data) {
    debugLogger.debugLog('📢 SECURITY: Message types advertised');
    ui.showStatus('📢 Security analysis capabilities loaded', 'info');
}

function handleErrorMessage(data) {
    var errorMessage = data.message;
    debugLogger.debugLog('💥 SECURITY: Error - ' + errorMessage, 'ERROR');
    ui.showStatus('❌ ' + errorMessage, 'error');
}

function handleLogsRetrieved(data) {
    debugLogger.debugLog('📥 SECURITY: Security logs retrieved');
    progressManager.handleLogsRetrieved(data);
}

function handlePongMessage(data) {
    debugLogger.debugLog('🏓 SECURITY: Server responded to ping');
    ui.showStatus('🏓 Security system responding', 'info');
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function sendWebSocketMessage(message) {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        var messageString = JSON.stringify(message);
        websocket.send(messageString);
        wsStats.messages_sent++;
        
        debugLogger.debugLog('📤 SECURITY: Message sent - Type: ' + message.type);
        return true;
    } else {
        debugLogger.debugLog('❌ SECURITY: WebSocket not connected', 'ERROR');
        ui.showStatus('❌ Not connected to security system', 'error');
        return false;
    }
}

function showWebSocketStats() {
    var stats = 'ENHANCED Security Domain WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        '\nAgent States:\n' +
        'Triage: Activated=' + agentActivationState.triage.activated + ', Completed=' + agentActivationState.triage.completed + '\n' +
        'Context: Activated=' + agentActivationState.context.activated + ', Completed=' + agentActivationState.context.completed + '\n' +
        'Analyst: Activated=' + agentActivationState.analyst.activated + ', Completed=' + agentActivationState.analyst.completed + '\n' +
        '\nSecurity Findings:\n' +
        'Threats Detected: ' + (securityFindings.triage.threat_detected ? 'Yes' : 'No') + '\n' +
        'Historical Incidents: ' + securityFindings.context.historical_incidents + '\n' +
        'Recommendations: ' + securityFindings.analyst.recommendations_count;

    debugLogger.debugLog(stats);
    ui.showStatus('📊 Enhanced security analysis stats logged to console', 'info');
}

function testConnection() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        if (sendWebSocketMessage({ type: 'ping', session_id: currentSessionId })) {
            ui.showStatus('🏓 Testing security system connection', 'info');
        }
    } else {
        ui.showStatus('❌ Security system not connected', 'warning');
    }
}

function getWebSocket() {
    return websocket;
}

function getCurrentSessionId() {
    return currentSessionId;
}

function getSecurityFindings() {
    return securityFindings;
}

// ENHANCED: Debug functions to help troubleshoot agent display issues
function getAgentActivationState() {
    return agentActivationState;
}

function debugAgentState() {
    console.log('🔍 AGENT DEBUG STATE:');
    console.log('Activation State:', agentActivationState);
    console.log('Security Findings:', securityFindings);
    console.log('DOM Elements:');
    console.log('  triageOutput exists:', !!document.getElementById('triageOutput'));
    console.log('  contextOutput exists:', !!document.getElementById('contextOutput'));
    console.log('  analystOutput exists:', !!document.getElementById('analystOutput'));
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
    getSecurityFindings,
    getAgentActivationState,
    debugAgentState,
    resetAgentStates
};