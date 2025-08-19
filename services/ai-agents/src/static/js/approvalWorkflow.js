// Updated approvalWorkflow.js to handle AutoGen-style messages

// Import other modules
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';

// Approval Workflow Logic
var awaitingApproval = false;

function handleApprovalRequest(data) {
    debugLogger.debugLog('Approval request received - Message: ' + data.content);
    console.log('Full approval request data:', data);
    
    // Set state before updating UI
    awaitingApproval = true;

    // Show approval buttons in triage card
    showApprovalButtons();

    // Update triage status
    ui.updateAgentStatus('triage', 'awaiting-approval');
    
    var outputText = 'Triage analysis complete. Awaiting your approval to continue...\n\n';
    if (data.content) {
        outputText += data.content;
    }
    
    ui.showAgentOutput('triage', outputText);

    // Show notification
    ui.showStatus('User approval required - Please review triage findings', 'warning');

    // Scroll to triage card
    var triageCard = document.getElementById('triageCard');
    if (triageCard) {
        triageCard.scrollIntoView({ behavior: 'smooth' });
    }
    
    debugLogger.debugLog('Approval workflow activated - awaiting user decision');
}

function handleApprovalTimeout(data) {
    debugLogger.debugLog('Approval timeout received - Message: ' + data.message);
    
    if (awaitingApproval) {
        awaitingApproval = false;
        hideApprovalButtons();
        ui.showStatus('Approval timeout - Analysis continuing automatically', 'warning');
        debugLogger.debugLog('Approval workflow timed out - continuing automatically');
    } else {
        debugLogger.debugLog('Approval timeout received but not awaiting approval', 'WARNING');
    }
}

function showApprovalButtons() {
    debugLogger.debugLog('Showing approval buttons');
    
    // Remove any existing approval buttons first
    hideApprovalButtons();

    // Create approval buttons container
    var buttonsContainer = document.createElement('div');
    buttonsContainer.id = 'approvalButtons';
    buttonsContainer.className = 'approval-buttons';
    buttonsContainer.innerHTML = 
        '<div class="approval-prompt">Do you want to continue with the analysis based on these findings?</div>' +
        '<div class="button-group">' +
        '<button class="btn btn-approve" id="approveBtn">✅ Approve & Continue</button>' +
        '<button class="btn btn-reject" id="rejectBtn">❌ Reject & Stop</button>' +
        '</div>';

    // Add to triage card content
    var triageCard = document.getElementById('triageCard');
    if (!triageCard) {
        debugLogger.debugLog('Triage card not found - cannot show approval buttons', 'ERROR');
        return;
    }
    
    var triageContent = triageCard.querySelector('.agent-content');
    if (!triageContent) {
        debugLogger.debugLog('Triage card content not found - cannot show approval buttons', 'ERROR');
        return;
    }
    
    triageContent.appendChild(buttonsContainer);

    // Add event listeners to the buttons
    var approveBtn = document.getElementById('approveBtn');
    var rejectBtn = document.getElementById('rejectBtn');
    
    if (approveBtn && rejectBtn) {
        approveBtn.addEventListener('click', approveAnalysis);
        rejectBtn.addEventListener('click', rejectAnalysis);
        debugLogger.debugLog('Approval buttons created and event listeners attached');
    } else {
        debugLogger.debugLog('Failed to find approval buttons after creation', 'ERROR');
    }

    // Add pulsing effect to draw attention
    buttonsContainer.classList.add('pulse-animation');
}

function hideApprovalButtons() {
    var buttons = document.getElementById('approvalButtons');
    if (buttons) {
        debugLogger.debugLog('Hiding approval buttons');
        
        // Remove event listeners first
        var approveBtn = document.getElementById('approveBtn');
        var rejectBtn = document.getElementById('rejectBtn');
        if (approveBtn) approveBtn.removeEventListener('click', approveAnalysis);
        if (rejectBtn) rejectBtn.removeEventListener('click', rejectAnalysis);
        
        // Remove the buttons container
        buttons.remove();
        debugLogger.debugLog('Approval buttons removed');
    }
}

function approveAnalysis() {
    debugLogger.debugLog('User clicked approve button');
    
    if (!awaitingApproval) {
        debugLogger.debugLog('Approve clicked but not awaiting approval', 'WARNING');
        return;
    }

    debugLogger.debugLog('Processing user approval');
    awaitingApproval = false;

    // Send response in AutoGen TextMessage format
    var approvalMessage = {
        type: 'TextMessage',
        content: 'approve',
        source: 'user'
    };
    
    debugLogger.debugLog('Sending approval message: ' + JSON.stringify(approvalMessage));
    
    if (websocket.sendWebSocketMessage(approvalMessage)) {
        hideApprovalButtons();
        ui.showStatus('Analysis approved - Continuing to context research', 'success');
        ui.updateAgentStatus('triage', 'complete');
        ui.showAgentOutput('triage', 'Analysis approved by user. Proceeding to context research...');
        debugLogger.debugLog('Approval sent successfully');
    } else {
        debugLogger.debugLog('Failed to send approval message', 'ERROR');
        ui.showStatus('Failed to send approval - please try again', 'error');
        awaitingApproval = true; // Reset state so user can try again
    }
}

function rejectAnalysis() {
    debugLogger.debugLog('User clicked reject button');
    
    if (!awaitingApproval) {
        debugLogger.debugLog('Reject clicked but not awaiting approval', 'WARNING');
        return;
    }

    debugLogger.debugLog('Processing user rejection');
    awaitingApproval = false;
    
    // Import progressManager here to avoid circular dependency
    import('./progressManager.js').then(progressManager => {
        progressManager.setAnalysisInProgress(false);
        debugLogger.debugLog('Set analysis in progress to false');
    }).catch(error => {
        debugLogger.debugLog('Failed to import progressManager: ' + error, 'ERROR');
    });

    // Send response in AutoGen TextMessage format
    var rejectionMessage = {
        type: 'TextMessage',
        content: 'reject',
        source: 'user'
    };
    
    debugLogger.debugLog('Sending rejection message: ' + JSON.stringify(rejectionMessage));

    if (websocket.sendWebSocketMessage(rejectionMessage)) {
        hideApprovalButtons();
        ui.showStatus('Analysis rejected - Workflow stopped', 'warning');
        ui.updateAgentStatus('triage', 'rejected');
        ui.showAgentOutput('triage', 'Analysis rejected by user. Workflow stopped.');

        // Re-enable analyze button
        var analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
        ui.updateProgress(0, 'Analysis Rejected');
        debugLogger.debugLog('Rejection processed successfully');
    } else {
        debugLogger.debugLog('Failed to send rejection message', 'ERROR');
        ui.showStatus('Failed to send rejection - please try again', 'error');
        awaitingApproval = true; // Reset state so user can try again
    }
}

function getAwaitingApproval() {
    return awaitingApproval;
}

function setAwaitingApproval(value) {
    debugLogger.debugLog('Setting awaiting approval to: ' + value + ' (was: ' + awaitingApproval + ')');
    awaitingApproval = value;
}

export { 
    handleApprovalRequest, 
    handleApprovalTimeout, 
    showApprovalButtons, 
    hideApprovalButtons, 
    approveAnalysis, 
    rejectAnalysis, 
    getAwaitingApproval, 
    setAwaitingApproval 
};