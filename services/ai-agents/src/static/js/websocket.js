// services/ai-agents/src/static/js/websocket.js - DOMAIN-FOCUSED VERSION
// WebSocket client focused on security domain messages, filtering out technical noise

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// ============================================================================
// DOMAIN-FOCUSED GLOBALS
// ============================================================================

var websocket = null;
var wsStats = { connected: false, messages_sent: 0, messages_received: 0, reconnects: 0 };
var reconnectAttempts = 0;
var maxReconnectAttempts = 5;
var currentSessionId = null;

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

// Domain state tracking (security-focused)
var securityFindings = {
    triage: { threat_detected: false, priority: null, threat_type: null, source_ip: null },
    context: { historical_incidents: 0, patterns_found: false },
    analyst: { recommendations_count: 0, business_impact: null }
};

// ============================================================================
// WEBSOCKET INITIALIZATION
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
        ui.showStatus('🔌 Connected to SOC Security Analysis', 'success');
    };

    websocket.onmessage = function(event) {
        wsStats.messages_received++;
        
        try {
            var data = JSON.parse(event.data);
            
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
// DOMAIN MESSAGE FILTERING
// ============================================================================

function isDomainRelevantMessage(messageType) {
    // Return true only for messages that matter to the security domain
    return DOMAIN_MESSAGE_TYPES[messageType] === true;
}

function handleDomainMessage(data) {
    // Handle only domain-relevant messages
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
// SECURITY DOMAIN MESSAGE HANDLERS
// ============================================================================

function handleSecurityTriage(data) {
    // Handle threat assessment results
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
            brief_summary: findings.brief_summary
        };
        
        // Update UI with clean security information
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
    // Handle historical security incident analysis
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
            search_queries: research.search_queries || []
        };
        
        // Update UI with clean security information
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
    // Handle final security recommendations
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
            investigation_notes: analysis.investigation_notes
        };
        
        // Update UI with clean security information
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
// CLEAN DOMAIN-FOCUSED UI UPDATES
// ============================================================================

function updateTriageDisplay(triageData) {
    // Show clean threat assessment information
    var triageOutput = document.getElementById('triageOutput');
    if (triageOutput) {
        var securitySummary = '🚨 THREAT ASSESSMENT COMPLETE\n\n' +
            '⚠️  Priority: ' + triageData.priority.toUpperCase() + '\n' +
            '🎯 Threat Type: ' + triageData.threat_type + '\n' +
            '📍 Source IP: ' + triageData.source_ip + '\n' +
            '🎯 Targets: ' + (triageData.target_hosts.length > 0 ? triageData.target_hosts.join(', ') : 'Multiple') + '\n' +
            '📊 Confidence: ' + (triageData.confidence * 100).toFixed(1) + '%\n' +
            '🔍 Pattern: ' + (triageData.attack_pattern || 'Unknown') + '\n\n' +
            '📋 Summary: ' + (triageData.brief_summary || 'Threat detected and classified for investigation');
        
        triageOutput.textContent = securitySummary;
    }
    
    // Add visual security indicator
    var triageCard = document.getElementById('triageCard');
    if (triageCard) {
        triageCard.classList.add('active');
        // triageCard.style.borderLeft = getPriorityColor(triageData.priority);
    }
}

function updateContextDisplay(contextData) {
    // Show clean historical security context
    var contextOutput = document.getElementById('contextOutput');
    if (contextOutput) {
        var contextSummary = '📚 HISTORICAL CONTEXT ANALYSIS\n\n' +
            '📊 Related Incidents: ' + contextData.historical_incidents + '\n' +
            '🔍 Pattern Analysis: ' + (contextData.patterns_found ? 'Patterns identified' : 'No clear patterns') + '\n' +
            '📝 Search Scope: ' + (contextData.search_queries.length > 0 ? contextData.search_queries.join(', ') : 'General threat patterns') + '\n\n' +
            '📋 Analysis: ' + contextData.pattern_analysis;
        
        contextOutput.textContent = contextSummary;
    }
    
    // Add visual context indicator
    var contextCard = document.getElementById('contextCard');
    if (contextCard) {
        contextCard.classList.add('active');
        // contextCard.style.borderLeft = '4px solid #4ecdc4';
    }
}

function updateAnalystDisplay(analystData) {
    // Show clean security recommendations
    var analystOutput = document.getElementById('analystOutput');
    if (analystOutput) {
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
    }
    
    // Add visual completion indicator
    var analystCard = document.getElementById('analystCard');
    if (analystCard) {
        analystCard.classList.add('active');
        // analystCard.style.borderLeft = '4px solid #a8e6cf';
    }
}

function getPriorityColor(priority) {
    // Get color based on security priority
    switch (priority.toLowerCase()) {
        case 'critical': return '4px solid #ff416c';
        case 'high': return '4px solid #ffa726';
        case 'medium': return '4px solid #42a5f5';
        case 'low': return '4px solid #95a5a6';
        default: return '4px solid #667eea';
    }
}

// ============================================================================
// OTHER DOMAIN MESSAGE HANDLERS (kept from original)
// ============================================================================

function handleApprovalRequest(data) {
    // Use existing approval workflow
    approvalWorkflow.handleApprovalRequest(data);
}

function handleApprovalTimeout(data) {
    // Use existing approval workflow
    approvalWorkflow.handleApprovalTimeout(data);
}

function handleWorkflowProgress(data) {
    // Handle high-level workflow progress only
    var progressPercentage = data.progress_percentage;
    var currentStage = data.current_stage;
    
    debugLogger.debugLog('📈 DOMAIN: Workflow progress - ' + progressPercentage + '% - ' + currentStage);
    
    // Update UI progress with domain-friendly stage names
    var domainStage = convertToDomainStage(currentStage);
    ui.updateProgress(progressPercentage, domainStage);
}

function convertToDomainStage(technicalStage) {
    // Convert technical stage names to domain-friendly ones
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
    // Handle workflow completion
    var success = data.success;
    var resultsSummary = data.results_summary || {};
    
    debugLogger.debugLog('🎉 SECURITY: Analysis complete - Success: ' + success);
    
    if (success) {
        ui.showStatus('🎉 Security analysis completed successfully!', 'success');
        ui.updateProgress(100, 'Security Analysis Complete');
        
        // Show domain-focused results summary
        setTimeout(function() {
            showSecurityResultsSummary();
        }, 1000);
    } else {
        ui.showStatus('⚠️ Security analysis completed with issues', 'warning');
        ui.updateProgress(100, 'Completed with issues');
    }
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    
    // Enable the analyze button again
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function handleWorkflowRejected(data) {
    // Handle workflow rejection
    var rejectedStage = data.rejected_stage;
    
    debugLogger.debugLog('❌ SECURITY: Analysis rejected at ' + rejectedStage + ' stage');
    
    ui.showStatus('❌ Security analysis rejected at ' + rejectedStage + ' stage', 'error');
    ui.updateProgress(100, 'Analysis Rejected');
    
    // Reset analysis state
    progressManager.setAnalysisInProgress(false);
    
    // Enable the analyze button again
    var analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
        analyzeBtn.disabled = false;
    }
}

function showSecurityResultsSummary() {
    // Show clean security-focused results summary
    debugLogger.debugLog('📊 SECURITY: Showing domain-focused results summary');
    
    var findings = [];
    
    // Build findings from security state
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
    
    // Show the clean security findings
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
// ESSENTIAL SYSTEM HANDLERS (simplified)
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
    // Send WebSocket message
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
    // Show simplified security-focused stats
    var stats = 'Security Domain WebSocket Statistics:\n' +
        'Connected: ' + wsStats.connected + '\n' +
        'Messages Sent: ' + wsStats.messages_sent + '\n' +
        'Messages Received: ' + wsStats.messages_received + '\n' +
        'Session ID: ' + (currentSessionId || 'None') + '\n' +
        'Threats Detected: ' + (securityFindings.triage.threat_detected ? 'Yes' : 'No') + '\n' +
        'Historical Incidents: ' + securityFindings.context.historical_incidents + '\n' +
        'Recommendations: ' + securityFindings.analyst.recommendations_count;

    debugLogger.debugLog(stats);
    ui.showStatus('📊 Security analysis stats logged to console', 'info');
}

function testConnection() {
    // Test WebSocket connection
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
    getSecurityFindings
};