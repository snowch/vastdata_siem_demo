// Enhanced approvalWorkflow.js with multi-stage approval support

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
        prompt: 'Are these historical incidents relevant to the current analysis?',
        buttons: [
            { text: '✅ Relevant context, proceed to analysis', value: 'approve', class: 'btn-approve' },
            { text: '❌ Not relevant, skip context', value: 'reject', class: 'btn-reject' },
            { text: '✏️ Provide different context', value: 'custom', class: 'btn-custom' }
        ]
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
    // Try to determine which agent is requesting approval
    var content = data.content || '';
    var source = data.source || '';
    
    // Check source first
    if (source.includes('Triage') || source.includes('triage')) {
        return 'triage';
    } else if (source.includes('Context') || source.includes('context')) {
        return 'context';
    } else if (source.includes('Analyst') || source.includes('analyst')) {
        return 'analyst';
    }
    
    // Fallback to content analysis
    if (content.toLowerCase().includes('triage') || content.toLowerCase().includes('priority threat')) {
        return 'triage';
    } else if (content.toLowerCase().includes('historical') || content.toLowerCase().includes('context')) {
        return 'context';
    } else if (content.toLowerCase().includes('recommend') || content.toLowerCase().includes('action')) {
        return 'analyst';
    }
    
    // Default to triage if can't determine
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

    // Create approval buttons container
    var buttonsContainer = document.createElement('div');
    buttonsContainer.id = agentType + 'ApprovalButtons';
    buttonsContainer.className = 'approval-buttons';
    
    var buttonsHtml = '<div class="approval-prompt">' + 
        '<h4>' + stageConfig.title + '</h4>' +
        '<p>' + stageConfig.prompt + '</p>' +
        '</div>' +
        '<div class="button-group">';
    
    // Add configured buttons
    stageConfig.buttons.forEach(function(button, index) {
        buttonsHtml += '<button class="btn ' + button.class + '" ' +
            'data-agent="' + agentType + '" ' +
            'data-value="' + button.value + '" ' +
            'data-index="' + index + '">' +
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
    
    buttonsContainer.innerHTML = buttonsHtml;

    // Add to agent card content
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
    
    agentContent.appendChild(buttonsContainer);

    // Add event listeners
    attachApprovalEventListeners(agentType, buttonsContainer, stageConfig);

    // Add pulsing effect
    buttonsContainer.classList.add('pulse-animation');
    
    debugLogger.debugLog('Approval buttons created for agent: ' + agentType);
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
}

function showCustomInput(agentType) {
    var customSection = document.querySelector('#' + agentType + 'ApprovalButtons .custom-input-section');
    if (customSection) {
        customSection.style.display = 'block';
        var textarea = document.getElementById(agentType + 'CustomInput');
        if (textarea) {
            textarea.focus();
        }
    }
}

function hideCustomInput(agentType) {
    var customSection = document.querySelector('#' + agentType + 'ApprovalButtons .custom-input-section');
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
    var buttons = document.getElementById(agentType + 'ApprovalButtons');
    if (buttons) {
        debugLogger.debugLog('Hiding approval buttons for: ' + agentType);
        buttons.remove();
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
    hideAgentApprovalButtons
};