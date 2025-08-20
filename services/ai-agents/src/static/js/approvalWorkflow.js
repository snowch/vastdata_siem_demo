// services/ai-agents/src/static/js/approvalWorkflow.js - DUPLICATE APPROVAL FIX
// Enhanced approval workflow with better duplicate prevention and unknown stage filtering

import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';

// Approval Workflow Logic with Enhanced Duplicate Prevention
var currentApprovalStage = null;
var awaitingApproval = false;
var lastApprovalTimestamp = null;
var processedApprovalIds = new Set(); // Track processed approval requests

// Define approval stages and their configurations
const APPROVAL_STAGES = {
    'triage': {
        title: 'Threat Investigation Approval',
        prompt: 'Do you want to proceed with investigating this threat?',
        buttons: [
            { text: '✅ Yes, investigate this threat', value: 'approve', class: 'btn-approve' },
            { text: '❌ No, skip this threat', value: 'reject', class: 'btn-reject' }
        ]
    },
    'context': {
        title: 'Historical Context Validation',
        prompt: 'Are these historical insights relevant for the current analysis?',
        buttons: [
            { text: '✅ Relevant context, proceed to analysis', value: 'approve', class: 'btn-approve' },
            { text: '❌ Not relevant, skip context', value: 'reject', class: 'btn-reject' },
            { text: '✏️ Provide different context', value: 'custom', class: 'btn-custom' }
        ],
        allowCustomInput: true
    },
    'analyst': {
        title: 'Action Authorization',
        prompt: 'Do you approve these recommended actions?',
        buttons: [
            { text: '✅ Approve all recommendations', value: 'approve', class: 'btn-approve' },
            { text: '❌ Reject recommendations', value: 'reject', class: 'btn-reject' },
            { text: '✏️ Modify recommendations', value: 'custom', class: 'btn-custom' }
        ],
        allowCustomInput: true
    }
};

function handleApprovalRequest(data) {
    debugLogger.debugLog('🔍 APPROVAL: Processing approval request - Type: ' + data.type + ', Stage: ' + (data.stage || 'undefined'));
    console.log('Full approval request data:', data);
    
    // ENHANCED: Filter out invalid or problematic approval requests
    if (!isValidApprovalRequest(data)) {
        debugLogger.debugLog('❌ APPROVAL: Invalid or filtered approval request', 'WARNING');
        return;
    }
    
    // ENHANCED: Check for duplicate requests
    var approvalId = generateApprovalId(data);
    if (processedApprovalIds.has(approvalId)) {
        debugLogger.debugLog('⚠️ APPROVAL: Duplicate approval request detected, skipping: ' + approvalId, 'WARNING');
        return;
    }
    
    // Determine which agent is requesting approval
    var requestingAgent = determineRequestingAgent(data);
    
    // ENHANCED: Additional validation for requesting agent
    if (!requestingAgent || requestingAgent === 'unknown') {
        debugLogger.debugLog('❌ APPROVAL: Could not determine requesting agent, skipping', 'WARNING');
        return;
    }
    
    debugLogger.debugLog('✅ APPROVAL: Valid approval request from agent: ' + requestingAgent);
    
    // ENHANCED: Check if we're already waiting for approval from this agent
    if (awaitingApproval && currentApprovalStage === requestingAgent) {
        debugLogger.debugLog('⚠️ APPROVAL: Already awaiting approval from ' + requestingAgent + ', skipping duplicate', 'WARNING');
        return;
    }
    
    // ENHANCED: If we're waiting for a different stage, complete the previous one first
    if (awaitingApproval && currentApprovalStage && currentApprovalStage !== requestingAgent) {
        debugLogger.debugLog('🔄 APPROVAL: Switching from ' + currentApprovalStage + ' to ' + requestingAgent + ' approval');
        hideAgentApprovalButtons(currentApprovalStage);
    }
    
    // Mark this request as processed
    processedApprovalIds.add(approvalId);
    lastApprovalTimestamp = Date.now();
    
    // Set state
    awaitingApproval = true;
    currentApprovalStage = requestingAgent;

    // Show approval buttons for the specific agent
    showAgentApprovalButtons(requestingAgent, data);

    // Update agent status
    ui.updateAgentStatus(requestingAgent, 'awaiting-approval');
    
    // Show notification
    var stageName = APPROVAL_STAGES[requestingAgent]?.title || 'Approval';
    ui.showStatus(stageName + ' required - Please review and respond', 'warning');

    // Scroll to the agent card
    var agentCard = document.getElementById(requestingAgent + 'Card');
    if (agentCard) {
        agentCard.scrollIntoView({ behavior: 'smooth' });
    }
    
    debugLogger.debugLog('✅ APPROVAL: Multi-stage approval workflow activated for: ' + requestingAgent);
}

// ENHANCED: Validation function for approval requests
function isValidApprovalRequest(data) {
    // Filter out requests with no stage or unknown stage
    if (!data.stage || data.stage === 'unknown') {
        debugLogger.debugLog('🚫 APPROVAL: Filtering out request with unknown/missing stage', 'INFO');
        return false;
    }
    
    // Must be a recognized stage
    if (!APPROVAL_STAGES[data.stage]) {
        debugLogger.debugLog('🚫 APPROVAL: Filtering out request with unrecognized stage: ' + data.stage, 'INFO');
        return false;
    }
    
    // FIXED: Only filter out the specific problematic combination
    // Allow empty prompts for legitimate stages, but filter out the specific generic prompt
    if (data.stage === 'unknown' && data.prompt === 'Enter your response: ') {
        debugLogger.debugLog('🚫 APPROVAL: Filtering out generic unknown stage request', 'INFO');
        return false;
    }
    
    // Must have reasonable timing (prevent rapid-fire duplicates)
    if (lastApprovalTimestamp && (Date.now() - lastApprovalTimestamp) < 500) {
        debugLogger.debugLog('🚫 APPROVAL: Filtering out request due to rapid timing', 'INFO');
        return false;
    }
    
    // ENHANCED: For triage stage, be more permissive with prompts
    if (data.stage === 'triage') {
        debugLogger.debugLog('✅ APPROVAL: Allowing triage stage request (permissive validation)', 'INFO');
        return true;
    }
    
    // For other stages, ensure they have meaningful content
    if (data.stage === 'context' || data.stage === 'analyst') {
        if (!data.prompt || data.prompt.trim() === '' || data.prompt === 'Enter your response: ') {
            debugLogger.debugLog('🚫 APPROVAL: Filtering out ' + data.stage + ' request with insufficient prompt', 'INFO');
            return false;
        }
    }
    
    return true;
}

// ENHANCED: Generate unique ID for approval requests to detect duplicates
function generateApprovalId(data) {
    var id = (data.stage || 'unknown') + '_' + 
             (data.prompt ? data.prompt.substring(0, 50) : 'empty') + '_' + 
             (data.session_id || 'nosession');
    return id;
}

function determineRequestingAgent(data) {
    // ENHANCED: Better detection for requesting agent with priority order
    var content = data.content || data.prompt || '';
    var source = data.source || '';
    var stage = data.stage || '';
    
    debugLogger.debugLog('🔍 APPROVAL: Determining agent from stage: "' + stage + '", source: "' + source + '" and content snippet: "' + content.substring(0, 100) + '..."');
    
    // PRIORITY 1: Check the stage field from the message (most reliable)
    if (stage && APPROVAL_STAGES[stage]) {
        debugLogger.debugLog('✅ APPROVAL: Detected agent from stage field: ' + stage);
        return stage;
    }
    
    // PRIORITY 2: Check source field
    if (source.includes('Triage') || source.includes('triage')) {
        debugLogger.debugLog('✅ APPROVAL: Detected triage agent from source');
        return 'triage';
    } else if (source.includes('Context') || source.includes('context')) {
        debugLogger.debugLog('✅ APPROVAL: Detected context agent from source');
        return 'context';
    } else if (source.includes('Analyst') || source.includes('analyst') || source.includes('Senior')) {
        debugLogger.debugLog('✅ APPROVAL: Detected analyst agent from source');
        return 'analyst';
    }
    
    // PRIORITY 3: Enhanced content analysis with more specific patterns
    var contentLower = content.toLowerCase();
    
    // Context agent specific indicators (most specific first)
    var contextIndicators = [
        'context validation required',
        '🔍 context validation required',
        'historical insights relevant',
        'should we proceed with deep security analysis',
        'proceed with deep analysis using this context',
        'are these insights relevant for the current threat analysis',
        'found 30 related historical incidents', // From your console output
        'found' + '.*' + 'historical incidents',
        'context research',
        'auto_triggered'
    ];
    
    for (var i = 0; i < contextIndicators.length; i++) {
        if (contentLower.includes(contextIndicators[i])) {
            debugLogger.debugLog('✅ APPROVAL: Detected context agent from content indicator: ' + contextIndicators[i]);
            return 'context';
        }
    }
    
    // Triage agent indicators
    var triageIndicators = [
        'priority threat',
        'investigate this',
        'brute force',
        'attack detected',
        'proceed with investigating',
        'high priority',
        'critical threat',
        'sql injection and brute force attacks' // From your console output
    ];
    
    for (var i = 0; i < triageIndicators.length; i++) {
        if (contentLower.includes(triageIndicators[i])) {
            debugLogger.debugLog('✅ APPROVAL: Detected triage agent from content indicator: ' + triageIndicators[i]);
            return 'triage';
        }
    }
    
    // Analyst agent indicators
    var analystIndicators = [
        'recommend',
        'action',
        'authorize',
        'recommendations',
        'implement',
        'block ip',
        'reset passwords',
        'remediation',
        'containment'
    ];
    
    for (var i = 0; i < analystIndicators.length; i++) {
        if (contentLower.includes(analystIndicators[i])) {
            debugLogger.debugLog('✅ APPROVAL: Detected analyst agent from content indicator: ' + analystIndicators[i]);
            return 'analyst';
        }
    }
    
    debugLogger.debugLog('❌ APPROVAL: Could not determine agent type - will be filtered out');
    return null; // Changed from 'triage' to null to prevent defaulting
}

function showAgentApprovalButtons(agentType, requestData) {
    debugLogger.debugLog('🎯 APPROVAL: Showing approval buttons for agent: ' + agentType);
    
    // Remove any existing approval buttons for this agent
    hideAgentApprovalButtons(agentType);

    var stageConfig = APPROVAL_STAGES[agentType];
    if (!stageConfig) {
        debugLogger.debugLog('❌ APPROVAL: No approval stage configuration found for: ' + agentType, 'ERROR');
        return;
    }

    // Create approval section container
    var approvalSection = document.createElement('div');
    approvalSection.id = agentType + 'ApprovalSection';
    approvalSection.className = 'approval-section stage-' + agentType;
    
    // ENHANCED: Better prompts based on agent type and context
    var customPrompt = stageConfig.prompt;
    if (agentType === 'context' && requestData) {
        // Extract key information from context for better prompt
        var context = requestData.context || {};
        var content = requestData.content || requestData.prompt || '';
        
        if (context.incidents_found || content.includes('incidents')) {
            var incidentCount = context.incidents_found || extractIncidentCount(content);
            if (incidentCount > 0) {
                customPrompt = 'Found ' + incidentCount + ' related historical incidents. Are these insights relevant for the current threat analysis?';
            }
        }
        
        // Use the prompt from the request if available and meaningful
        if (requestData.prompt && requestData.prompt.trim() && requestData.prompt !== 'Enter your response: ') {
            customPrompt = requestData.prompt;
        }
    }
    
    var buttonsHtml = '<div class="approval-prompt">' + 
        '<h4>' + stageConfig.title + '</h4>' +
        '<p>' + customPrompt + '</p>' +
        '</div>' +
        '<div class="button-group">';
    
    // Add configured buttons
    stageConfig.buttons.forEach(function(button, index) {
        buttonsHtml += '<button class="btn ' + button.class + '" ' +
            'data-agent="' + agentType + '" ' +
            'data-value="' + button.value + '" ' +
            'data-index="' + index + '" ' +
            'tabindex="0">' +
            button.text + '</button>';
    });
    
    buttonsHtml += '</div>';
    
    // Add custom input field if allowed
    if (stageConfig.allowCustomInput) {
        buttonsHtml += '<div class="custom-input-section" style="display:none;">' +
            '<label for="' + agentType + 'CustomInput">Custom Instructions:</label>' +
            '<textarea id="' + agentType + 'CustomInput" placeholder="Enter your specific instructions or modifications..." rows="3"></textarea>' +
            '<div class="custom-input-buttons">' +
            '<button class="btn btn-primary" data-agent="' + agentType + '" data-action="submit-custom">Submit Custom Response</button>' +
            '<button class="btn btn-secondary" data-agent="' + agentType + '" data-action="cancel-custom">Cancel</button>' +
            '</div>' +
            '</div>';
    }
    
    approvalSection.innerHTML = buttonsHtml;

    // Add to agent card - AFTER the agent-content, not inside it
    var agentCard = document.getElementById(agentType + 'Card');
    if (!agentCard) {
        debugLogger.debugLog('❌ APPROVAL: Agent card not found: ' + agentType, 'ERROR');
        return;
    }
    
    var agentContent = agentCard.querySelector('.agent-content');
    if (!agentContent) {
        debugLogger.debugLog('❌ APPROVAL: Agent card content not found: ' + agentType, 'ERROR');
        return;
    }
    
    // Insert approval section AFTER the agent-content
    agentContent.parentNode.insertBefore(approvalSection, agentContent.nextSibling);

    // Add event listeners
    attachApprovalEventListeners(agentType, approvalSection, stageConfig);

    // Add visual feedback
    agentCard.classList.add('approval-active');
    
    // Auto-focus on first button for better accessibility
    setTimeout(function() {
        var firstButton = approvalSection.querySelector('.btn');
        if (firstButton) {
            firstButton.focus();
        }
    }, 100);
    
    debugLogger.debugLog('✅ APPROVAL: Approval section created for agent: ' + agentType);
}

function extractIncidentCount(content) {
    // Enhanced extraction for numbers from content
    var patterns = [
        /found (\d+) related/i,
        /(\d+) historical incidents/i,
        /analysis of (\d+) historical/i,
        /found (\d+) related historical incidents/i // Specific to your console output
    ];
    
    for (var i = 0; i < patterns.length; i++) {
        var matches = content.match(patterns[i]);
        if (matches) {
            return parseInt(matches[1], 10);
        }
    }
    
    return 0;
}

function attachApprovalEventListeners(agentType, container, stageConfig) {
    // Handle button clicks
    container.querySelectorAll('.btn[data-agent="' + agentType + '"]').forEach(function(button) {
        button.addEventListener('click', function() {
            var value = this.getAttribute('data-value');
            var action = this.getAttribute('data-action');
            
            if (action === 'submit-custom') {
                handleCustomResponse(agentType);
            } else if (action === 'cancel-custom') {
                hideCustomInput(agentType);
            } else if (value === 'custom') {
                showCustomInput(agentType);
            } else {
                handleStandardApproval(agentType, value);
            }
        });
    });
    
    // Handle keyboard navigation within approval section
    container.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            // Let default tab behavior work
            return;
        }
        
        if (e.key === 'Enter' && e.target.classList.contains('btn')) {
            e.preventDefault();
            e.target.click();
        }
        
        // Quick approval shortcuts
        if (e.key === '1' || (e.key === 'Enter' && !e.target.classList.contains('btn'))) {
            e.preventDefault();
            var firstButton = container.querySelector('.btn[data-value="approve"]');
            if (firstButton) firstButton.click();
        } else if (e.key === '2' || (e.key === 'Escape' && !e.target.classList.contains('btn'))) {
            e.preventDefault();
            var secondButton = container.querySelector('.btn[data-value="reject"]');
            if (secondButton) secondButton.click();
        } else if (e.key === '3') {
            e.preventDefault();
            var thirdButton = container.querySelector('.btn[data-value="custom"]');
            if (thirdButton) thirdButton.click();
        }
    });
}

function showCustomInput(agentType) {
    var customSection = document.querySelector('#' + agentType + 'ApprovalSection .custom-input-section');
    if (customSection) {
        customSection.style.display = 'block';
        var textarea = document.getElementById(agentType + 'CustomInput');
        if (textarea) {
            textarea.focus();
        }
    }
}

function hideCustomInput(agentType) {
    var customSection = document.querySelector('#' + agentType + 'ApprovalSection .custom-input-section');
    if (customSection) {
        customSection.style.display = 'none';
        var textarea = document.getElementById(agentType + 'CustomInput');
        if (textarea) {
            textarea.value = '';
        }
    }
}

function handleCustomResponse(agentType) {
    var textarea = document.getElementById(agentType + 'CustomInput');
    if (!textarea || !textarea.value.trim()) {
        ui.showStatus('Please enter custom instructions before submitting', 'warning');
        return;
    }
    
    var customText = textarea.value.trim();
    debugLogger.debugLog('✏️ APPROVAL: Custom response for ' + agentType + ': ' + customText);
    
    sendApprovalResponse(agentType, 'custom: ' + customText);
}

function handleStandardApproval(agentType, value) {
    debugLogger.debugLog('✅ APPROVAL: Standard approval for ' + agentType + ': ' + value);
    sendApprovalResponse(agentType, value);
}

function sendApprovalResponse(agentType, response) {
    if (!awaitingApproval || currentApprovalStage !== agentType) {
        debugLogger.debugLog('⚠️ APPROVAL: Not awaiting approval for this agent: ' + agentType, 'WARNING');
        return;
    }

    debugLogger.debugLog('📤 APPROVAL: Sending approval response for ' + agentType + ': ' + response);
    
    // ENHANCED: Clear the processed request ID to allow new requests from this agent
    processedApprovalIds.clear();
    
    // Reset state
    awaitingApproval = false;
    currentApprovalStage = null;

    // Send response in AutoGen TextMessage format
    var approvalMessage = {
        type: 'TextMessage',
        content: response,
        source: 'user',
        target_agent: agentType
    };
    
    debugLogger.debugLog('📨 APPROVAL: Sending approval message: ' + JSON.stringify(approvalMessage));
    
    if (websocket.sendWebSocketMessage(approvalMessage)) {
        hideAgentApprovalButtons(agentType);
        
        var statusMessage = 'Response sent for ' + agentType;
        if (response === 'approve') {
            ui.updateAgentStatus(agentType, 'complete');
            statusMessage = agentType.charAt(0).toUpperCase() + agentType.slice(1) + ' approved - Continuing analysis';
        } else if (response === 'reject') {
            ui.updateAgentStatus(agentType, 'rejected');
            statusMessage = agentType.charAt(0).toUpperCase() + agentType.slice(1) + ' rejected - Modifying workflow';
        } else {
            ui.updateAgentStatus(agentType, 'complete');
            statusMessage = agentType.charAt(0).toUpperCase() + agentType.slice(1) + ' - Custom instructions provided';
        }
        
        ui.showStatus(statusMessage, response === 'reject' ? 'warning' : 'success');
        debugLogger.debugLog('✅ APPROVAL: Approval response sent successfully for: ' + agentType);
    } else {
        debugLogger.debugLog('❌ APPROVAL: Failed to send approval response for: ' + agentType, 'ERROR');
        ui.showStatus('Failed to send response - please try again', 'error');
        // Reset state so user can try again
        awaitingApproval = true;
        currentApprovalStage = agentType;
    }
}

function hideAgentApprovalButtons(agentType) {
    var approvalSection = document.getElementById(agentType + 'ApprovalSection');
    if (approvalSection) {
        debugLogger.debugLog('🗑️ APPROVAL: Hiding approval section for: ' + agentType);
        approvalSection.remove();
    }
    
    // Also remove the approval-active class from the agent card
    var agentCard = document.getElementById(agentType + 'Card');
    if (agentCard) {
        agentCard.classList.remove('approval-active');
    }
}

function hideAllApprovalButtons() {
    debugLogger.debugLog('🗑️ APPROVAL: Hiding all approval buttons');
    Object.keys(APPROVAL_STAGES).forEach(function(agentType) {
        hideAgentApprovalButtons(agentType);
    });
    
    // ENHANCED: Clear processed requests when hiding all
    processedApprovalIds.clear();
    awaitingApproval = false;
    currentApprovalStage = null;
}

function getAwaitingApproval() {
    return awaitingApproval;
}

function setAwaitingApproval(value) {
    debugLogger.debugLog('🔄 APPROVAL: Setting awaiting approval to: ' + value + ' (was: ' + awaitingApproval + ')');
    awaitingApproval = value;
    if (!value) {
        currentApprovalStage = null;
        // Clear processed requests when not awaiting approval
        processedApprovalIds.clear();
    }
}

function getCurrentApprovalStage() {
    return currentApprovalStage;
}

// Legacy functions for backward compatibility
function showApprovalButtons() {
    showAgentApprovalButtons('triage', { content: 'Triage analysis complete. Do you want to proceed?' });
}

function hideApprovalButtons() {
    hideAllApprovalButtons();
}

function approveAnalysis() {
    if (currentApprovalStage) {
        handleStandardApproval(currentApprovalStage, 'approve');
    }
}

function rejectAnalysis() {
    if (currentApprovalStage) {
        handleStandardApproval(currentApprovalStage, 'reject');
    }
}

// Handle approval timeout
function handleApprovalTimeout(data) {
    debugLogger.debugLog('⏰ APPROVAL: Approval timeout received for stage: ' + currentApprovalStage);
    
    if (awaitingApproval && currentApprovalStage) {
        awaitingApproval = false;
        var stage = currentApprovalStage;
        currentApprovalStage = null;
        hideAgentApprovalButtons(stage);
        ui.showStatus('Approval timeout for ' + stage + ' - Analysis continuing automatically', 'warning');
        debugLogger.debugLog('⏰ APPROVAL: Approval workflow timed out for: ' + stage);
        
        // Clear processed requests on timeout
        processedApprovalIds.clear();
    }
}

// ENHANCED: Export additional functions for debugging
function debugApprovalState() {
    return {
        awaitingApproval: awaitingApproval,
        currentStage: currentApprovalStage,
        availableStages: Object.keys(APPROVAL_STAGES),
        processedApprovalIds: Array.from(processedApprovalIds),
        lastApprovalTimestamp: lastApprovalTimestamp
    };
}

function clearApprovalHistory() {
    debugLogger.debugLog('🗑️ APPROVAL: Clearing approval history and state');
    processedApprovalIds.clear();
    awaitingApproval = false;
    currentApprovalStage = null;
    lastApprovalTimestamp = null;
    hideAllApprovalButtons();
}

export { 
    handleApprovalRequest, 
    handleApprovalTimeout, 
    showApprovalButtons, 
    hideApprovalButtons, 
    hideAllApprovalButtons,
    approveAnalysis, 
    rejectAnalysis, 
    getAwaitingApproval, 
    setAwaitingApproval,
    getCurrentApprovalStage,
    showAgentApprovalButtons,
    hideAgentApprovalButtons,
    debugApprovalState,
    clearApprovalHistory
};