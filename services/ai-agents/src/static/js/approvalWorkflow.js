// services/ai-agents/src/static/js/approvalWorkflow.js - COMPLETE UPDATED VERSION
// Enhanced approval workflow with improved context detection and multi-stage support

import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';

// Approval Workflow Logic with Multi-Stage Support
var currentApprovalStage = null;
var awaitingApproval = false;

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
    debugLogger.debugLog('Multi-stage approval request received - Message: ' + data.content);
    console.log('Full approval request data:', data);
    
    // Determine which agent is requesting approval based on the message content or source
    var requestingAgent = determineRequestingAgent(data);
    
    debugLogger.debugLog('Approval requested by agent: ' + requestingAgent);
    
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
    
    debugLogger.debugLog('Multi-stage approval workflow activated for: ' + requestingAgent);
}

function determineRequestingAgent(data) {
    // ENHANCED: Better detection for context agent approval requests
    var content = data.content || '';
    var source = data.source || '';
    var stage = data.stage || '';
    
    debugLogger.debugLog('Determining requesting agent from stage: "' + stage + '", source: "' + source + '" and content snippet: "' + content.substring(0, 100) + '..."');
    
    // First check the stage field from the message (most reliable)
    if (stage && APPROVAL_STAGES[stage]) {
        debugLogger.debugLog('Detected agent from stage field: ' + stage);
        return stage;
    }
    
    // Check source next
    if (source.includes('Triage') || source.includes('triage')) {
        debugLogger.debugLog('Detected triage agent from source');
        return 'triage';
    } else if (source.includes('Context') || source.includes('context')) {
        debugLogger.debugLog('Detected context agent from source');
        return 'context';
    } else if (source.includes('Analyst') || source.includes('analyst') || source.includes('Senior')) {
        debugLogger.debugLog('Detected analyst agent from source');
        return 'analyst';
    }
    
    // ENHANCED: Better content analysis for context agent
    var contentLower = content.toLowerCase();
    
    // Context agent specific indicators (more specific patterns)
    if (contentLower.includes('context validation required') || 
        contentLower.includes('🔍 context validation required') ||
        contentLower.includes('historical insights relevant') ||
        contentLower.includes('should we proceed with deep security analysis') ||
        contentLower.includes('context research') ||
        contentLower.includes('found') && contentLower.includes('historical incidents') ||
        (contentLower.includes('historical') && contentLower.includes('incidents')) ||
        (contentLower.includes('pattern') && contentLower.includes('analysis')) ||
        contentLower.includes('proceed with deep analysis') ||
        contentLower.includes('auto_triggered')) {
        debugLogger.debugLog('Detected context agent from content indicators');
        return 'context';
    }
    
    // Triage agent indicators
    if (contentLower.includes('priority threat') || 
        contentLower.includes('investigate this') || 
        contentLower.includes('brute force') || 
        contentLower.includes('attack detected') ||
        contentLower.includes('proceed with investigating') || 
        contentLower.includes('high priority') || 
        contentLower.includes('critical threat')) {
        debugLogger.debugLog('Detected triage agent from content indicators');
        return 'triage';
    }
    
    // Analyst agent indicators
    if (contentLower.includes('recommend') || 
        contentLower.includes('action') || 
        contentLower.includes('authorize') || 
        contentLower.includes('recommendations') || 
        contentLower.includes('implement') ||
        contentLower.includes('block ip') || 
        contentLower.includes('reset passwords') || 
        contentLower.includes('remediation') || 
        contentLower.includes('containment')) {
        debugLogger.debugLog('Detected analyst agent from content indicators');
        return 'analyst';
    }
    
    debugLogger.debugLog('Could not determine agent type, defaulting to triage');
    return 'triage';
}

function showAgentApprovalButtons(agentType, requestData) {
    debugLogger.debugLog('Showing approval buttons for agent: ' + agentType);
    
    // Remove any existing approval buttons for this agent
    hideAgentApprovalButtons(agentType);

    var stageConfig = APPROVAL_STAGES[agentType];
    if (!stageConfig) {
        debugLogger.debugLog('No approval stage configuration found for: ' + agentType, 'ERROR');
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
        
        // Use the prompt from the request if available
        if (requestData.prompt && requestData.prompt.trim()) {
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
        debugLogger.debugLog('Agent card not found: ' + agentType, 'ERROR');
        return;
    }
    
    var agentContent = agentCard.querySelector('.agent-content');
    if (!agentContent) {
        debugLogger.debugLog('Agent card content not found: ' + agentType, 'ERROR');
        return;
    }
    
    // Insert approval section AFTER the agent-content
    agentContent.parentNode.insertBefore(approvalSection, agentContent.nextSibling);

    // Add event listeners
    attachApprovalEventListeners(agentType, approvalSection, stageConfig);

    // Add visual feedback
    agentCard.classList.add('approval-active');
    
    // ENHANCED: Auto-focus on first button for better accessibility
    setTimeout(function() {
        var firstButton = approvalSection.querySelector('.btn');
        if (firstButton) {
            firstButton.focus();
        }
    }, 100);
    
    debugLogger.debugLog('Approval section created for agent: ' + agentType);
}

function extractIncidentCount(content) {
    // Try to extract number from content like "Found 24 related historical incidents"
    var matches = content.match(/found (\d+) related/i) || 
                  content.match(/(\d+) historical incidents/i) ||
                  content.match(/analysis of (\d+) historical/i);
    return matches ? parseInt(matches[1], 10) : 0;
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
    debugLogger.debugLog('Custom response for ' + agentType + ': ' + customText);
    
    sendApprovalResponse(agentType, 'custom: ' + customText);
}

function handleStandardApproval(agentType, value) {
    debugLogger.debugLog('Standard approval for ' + agentType + ': ' + value);
    sendApprovalResponse(agentType, value);
}

function sendApprovalResponse(agentType, response) {
    if (!awaitingApproval || currentApprovalStage !== agentType) {
        debugLogger.debugLog('Not awaiting approval for this agent: ' + agentType, 'WARNING');
        return;
    }

    debugLogger.debugLog('Sending approval response for ' + agentType + ': ' + response);
    
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
    
    debugLogger.debugLog('Sending approval message: ' + JSON.stringify(approvalMessage));
    
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
        debugLogger.debugLog('Approval response sent successfully for: ' + agentType);
    } else {
        debugLogger.debugLog('Failed to send approval response for: ' + agentType, 'ERROR');
        ui.showStatus('Failed to send response - please try again', 'error');
        // Reset state so user can try again
        awaitingApproval = true;
        currentApprovalStage = agentType;
    }
}

function hideAgentApprovalButtons(agentType) {
    var approvalSection = document.getElementById(agentType + 'ApprovalSection');
    if (approvalSection) {
        debugLogger.debugLog('Hiding approval section for: ' + agentType);
        approvalSection.remove();
    }
    
    // Also remove the approval-active class from the agent card
    var agentCard = document.getElementById(agentType + 'Card');
    if (agentCard) {
        agentCard.classList.remove('approval-active');
    }
}

function hideAllApprovalButtons() {
    Object.keys(APPROVAL_STAGES).forEach(function(agentType) {
        hideAgentApprovalButtons(agentType);
    });
}

function getAwaitingApproval() {
    return awaitingApproval;
}

function setAwaitingApproval(value) {
    debugLogger.debugLog('Setting awaiting approval to: ' + value + ' (was: ' + awaitingApproval + ')');
    awaitingApproval = value;
    if (!value) {
        currentApprovalStage = null;
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
    debugLogger.debugLog('Approval timeout received for stage: ' + currentApprovalStage);
    
    if (awaitingApproval && currentApprovalStage) {
        awaitingApproval = false;
        var stage = currentApprovalStage;
        currentApprovalStage = null;
        hideAgentApprovalButtons(stage);
        ui.showStatus('Approval timeout for ' + stage + ' - Analysis continuing automatically', 'warning');
        debugLogger.debugLog('Approval workflow timed out for: ' + stage);
    }
}

// ENHANCED: Export additional functions for debugging
function debugApprovalState() {
    return {
        awaitingApproval: awaitingApproval,
        currentStage: currentApprovalStage,
        availableStages: Object.keys(APPROVAL_STAGES)
    };
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
    debugApprovalState
};