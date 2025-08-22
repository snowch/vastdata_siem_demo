// services/ai-agents/src/static/js/modules/approval-workflow.js
// Refactored approval workflow - cleaner separation of concerns

import * as debugLogger from '../debugLogger.js';
import * as ui from '../ui.js';
import * as websocket from '../websocket.js';

export class ApprovalWorkflow {
    constructor() {
        this.currentStage = null;
        this.awaitingApproval = false;
        this.approvalHistory = [];
        this.contextData = null;
        
        this.stageConfigs = this.initializeStageConfigs();
    }

    initializeStageConfigs() {
        return {
            'triage': {
                title: 'Threat Investigation Approval',
                prompt: 'Do you want to proceed with investigating this threat?',
                buttons: [
                    { text: '✅ Yes, investigate', value: 'approve', class: 'btn-approve' },
                    { text: '❌ No, skip threat', value: 'reject', class: 'btn-reject' },
                    { text: '📋 Show Details', value: 'show-details', class: 'btn-secondary' }
                ]
            },
            'context': {
                title: 'Historical Context Validation',
                prompt: 'Are these historical insights relevant?',
                buttons: [
                    { text: '✅ Relevant, proceed', value: 'approve', class: 'btn-approve' },
                    { text: '❌ Not relevant', value: 'reject', class: 'btn-reject' },
                    { text: '📋 Show Details', value: 'show-details', class: 'btn-secondary' },
                    { text: '✏️ Custom context', value: 'custom', class: 'btn-custom' }
                ],
                allowCustomInput: true,
                hasDetailedView: true
            },
            'analyst': {
                title: 'Action Authorization',
                prompt: 'Do you approve these recommendations?',
                buttons: [
                    { text: '✅ Approve all', value: 'approve', class: 'btn-approve' },
                    { text: '❌ Reject recommendations', value: 'reject', class: 'btn-reject' },
                    { text: '📋 Show Details', value: 'show-details', class: 'btn-secondary' },
                    { text: '✏️ Modify actions', value: 'custom', class: 'btn-custom' }
                ],
                allowCustomInput: true
            }
        };
    }

    // ============================================================================
    // PUBLIC API
    // ============================================================================

    handleApprovalRequest(data) {
        debugLogger.debugLog(`🔍 APPROVAL: Processing request - ${data.type}, Stage: ${data.stage}`);
        
        if (!this.isValidRequest(data)) {
            debugLogger.debugLog('❌ APPROVAL: Invalid request filtered out', 'WARNING');
            return;
        }

        const stage = this.determineStage(data);
        if (!stage || stage === 'unknown') {
            debugLogger.debugLog('❌ APPROVAL: Could not determine stage', 'WARNING');
            return;
        }

        this.showApprovalUI(stage, data);
    }

    hideAllApprovals() {
        debugLogger.debugLog('🗑️ APPROVAL: Hiding all approval UIs');
        
        Object.keys(this.stageConfigs).forEach(stage => {
            this.hideApprovalUI(stage);
        });
        
        this.resetState();
    }

    getCurrentStage() {
        return this.currentStage;
    }

    isAwaitingApproval() {
        return this.awaitingApproval;
    }

    // ============================================================================
    // VALIDATION AND STAGE DETECTION
    // ============================================================================

    isValidRequest(data) {
        // Filter out generic/invalid requests
        if (!data.stage || data.stage === 'unknown') {
            return false;
        }

        if (!this.stageConfigs[data.stage]) {
            return false;
        }

        // Filter out the specific problematic combination
        if (data.stage === 'unknown' && data.prompt === 'Enter your response: ') {
            return false;
        }

        return true;
    }

    determineStage(data) {
        // Priority order for stage detection
        if (data.stage && this.stageConfigs[data.stage]) {
            return data.stage;
        }

        // Fallback to content analysis
        const content = (data.content || data.prompt || '').toLowerCase();
        
        if (this.containsTriageIndicators(content)) {
            return 'triage';
        } else if (this.containsContextIndicators(content)) {
            return 'context';
        } else if (this.containsAnalystIndicators(content)) {
            return 'analyst';
        }

        return null;
    }

    containsTriageIndicators(content) {
        const indicators = [
            'priority threat', 'investigate this', 'brute force', 
            'attack detected', 'critical threat'
        ];
        return indicators.some(indicator => content.includes(indicator));
    }

    containsContextIndicators(content) {
        const indicators = [
            'historical insights', 'context validation', 'relevant for the current',
            'historical incidents', 'proceed with deep security analysis'
        ];
        return indicators.some(indicator => content.includes(indicator));
    }

    containsAnalystIndicators(content) {
        const indicators = [
            'recommend', 'authorize', 'recommended actions', 
            'approve these', 'security recommendations'
        ];
        return indicators.some(indicator => content.includes(indicator));
    }

    // ============================================================================
    // UI MANAGEMENT
    // ============================================================================

    showApprovalUI(stage, requestData) {
        debugLogger.debugLog(`🎯 APPROVAL: Showing UI for ${stage}`);
        
        // Store context data if available
        if (stage === 'context' && requestData.context?.research_data) {
            this.contextData = requestData.context.research_data;
        }

        // Clean up any existing approval UI
        this.hideApprovalUI(stage);

        // Set state
        this.awaitingApproval = true;
        this.currentStage = stage;

        // Create and show approval section
        const approvalSection = this.createApprovalSection(stage, requestData);
        this.attachToAgentCard(stage, approvalSection);

        // Update agent status and UI
        ui.updateAgentStatus(stage, 'awaiting-approval');
        ui.showStatus(`${this.stageConfigs[stage].title} required`, 'warning');

        // Scroll to agent card
        this.scrollToAgent(stage);
    }

    createApprovalSection(stage, requestData) {
        const config = this.stageConfigs[stage];
        const section = document.createElement('div');
        
        section.id = `${stage}ApprovalSection`;
        section.className = `approval-section stage-${stage}`;
        
        // Build custom prompt
        const customPrompt = this.buildCustomPrompt(stage, requestData, config);
        
        // Create HTML structure
        section.innerHTML = this.buildApprovalHTML(config, customPrompt, stage);
        
        // Attach event listeners
        this.attachApprovalListeners(section, stage, config);
        
        return section;
    }

    buildCustomPrompt(stage, requestData, config) {
        if (stage === 'context' && requestData?.context) {
            const incidentCount = this.extractIncidentCount(requestData);
            if (incidentCount > 0) {
                return `Found ${incidentCount} related historical incidents. Are these insights relevant?`;
            }
        }
        
        // Use request prompt if meaningful, otherwise use default
        if (requestData?.prompt && 
            requestData.prompt.trim() && 
            requestData.prompt !== 'Enter your response: ') {
            return requestData.prompt;
        }
        
        return config.prompt;
    }

    buildApprovalHTML(config, prompt, stage) {
        let html = `
            <div class="approval-prompt">
                <h4>${config.title}</h4>
                <p>${prompt}</p>
            </div>
            <div class="button-group">
        `;
        
        // Add buttons
        config.buttons.forEach((button, index) => {
            html += `
                <button class="btn ${button.class}" 
                        data-agent="${stage}" 
                        data-value="${button.value}" 
                        data-index="${index}"
                        tabindex="0">
                    ${button.text}
                </button>
            `;
        });
        
        html += '</div>';
        
        // Add custom input section if allowed
        if (config.allowCustomInput) {
            html += this.buildCustomInputHTML(stage);
        }
        
        return html;
    }

    buildCustomInputHTML(stage) {
        return `
            <div class="custom-input-section" style="display:none;">
                <label for="${stage}CustomInput">Custom Instructions:</label>
                <textarea id="${stage}CustomInput" 
                          placeholder="Enter your specific instructions..." 
                          rows="3"></textarea>
                <div class="custom-input-buttons">
                    <button class="btn btn-primary" data-agent="${stage}" data-action="submit-custom">
                        Submit Custom Response
                    </button>
                    <button class="btn btn-secondary" data-agent="${stage}" data-action="cancel-custom">
                        Cancel
                    </button>
                </div>
            </div>
        `;
    }

    attachToAgentCard(stage, approvalSection) {
        const agentCard = document.getElementById(`${stage}Card`);
        if (!agentCard) {
            debugLogger.debugLog(`❌ APPROVAL: Agent card not found: ${stage}`, 'ERROR');
            return;
        }
        
        const agentContent = agentCard.querySelector('.agent-content');
        if (!agentContent) {
            debugLogger.debugLog(`❌ APPROVAL: Agent content not found: ${stage}`, 'ERROR');
            return;
        }
        
        // Insert after agent content
        agentContent.parentNode.insertBefore(approvalSection, agentContent.nextSibling);
        agentCard.classList.add('approval-active');
        
        // Auto-focus first button
        setTimeout(() => {
            const firstButton = approvalSection.querySelector('.btn');
            if (firstButton) firstButton.focus();
        }, 100);
    }

    // ============================================================================
    // EVENT HANDLING
    // ============================================================================

    attachApprovalListeners(container, stage, config) {
        // Button click handlers
        container.querySelectorAll(`.btn[data-agent="${stage}"]`).forEach(button => {
            button.addEventListener('click', (e) => this.handleButtonClick(e, stage));
        });

        // Keyboard navigation
        container.addEventListener('keydown', (e) => this.handleKeyboardNavigation(e, stage));
    }

    handleButtonClick(event, stage) {
        const value = event.target.getAttribute('data-value');
        const action = event.target.getAttribute('data-action');
        
        if (action === 'submit-custom') {
            this.handleCustomSubmit(stage);
        } else if (action === 'cancel-custom') {
            this.hideCustomInput(stage);
        } else if (value === 'custom') {
            this.showCustomInput(stage);
        } else if (value === 'show-details' && stage === 'context') {
            this.showContextDetails();
        } else {
            this.sendApprovalResponse(stage, value);
        }
    }

    handleKeyboardNavigation(event, stage) {
        // Quick approval shortcuts
        if (event.key === '1') {
            event.preventDefault();
            this.sendApprovalResponse(stage, 'approve');
        } else if (event.key === '2') {
            event.preventDefault();
            this.sendApprovalResponse(stage, 'reject');
        } else if (event.key === '3') {
            event.preventDefault();
            const customBtn = event.target.closest('.approval-section').querySelector('.btn[data-value="custom"]');
            if (customBtn) customBtn.click();
        }
    }

    // ============================================================================
    // RESPONSE HANDLING
    // ============================================================================

    sendApprovalResponse(stage, response) {
        if (!this.awaitingApproval || this.currentStage !== stage) {
            debugLogger.debugLog(`⚠️ APPROVAL: Not awaiting approval for ${stage}`, 'WARNING');
            return;
        }

        debugLogger.debugLog(`📤 APPROVAL: Sending response for ${stage}: ${response}`);
        
        // Build response message
        const message = {
            type: 'TextMessage',
            content: response,
            source: 'user',
            target_agent: stage
        };
        
        if (websocket.sendWebSocketMessage(message)) {
            this.hideApprovalUI(stage);
            this.updateStatusAfterResponse(stage, response);
            this.resetState();
        } else {
            debugLogger.debugLog(`❌ APPROVAL: Failed to send response for ${stage}`, 'ERROR');
            ui.showStatus('Failed to send response - please try again', 'error');
        }
    }

    handleCustomSubmit(stage) {
        const textarea = document.getElementById(`${stage}CustomInput`);
        if (!textarea || !textarea.value.trim()) {
            ui.showStatus('Please enter custom instructions', 'warning');
            return;
        }
        
        const customText = textarea.value.trim();
        this.sendApprovalResponse(stage, `custom: ${customText}`);
    }

    updateStatusAfterResponse(stage, response) {
        let statusMessage;
        
        if (response === 'approve') {
            ui.updateAgentStatus(stage, 'complete');
            statusMessage = `${this.capitalize(stage)} approved - Continuing analysis`;
        } else if (response === 'reject') {
            ui.updateAgentStatus(stage, 'rejected');
            statusMessage = `${this.capitalize(stage)} rejected - Workflow modified`;
        } else {
            ui.updateAgentStatus(stage, 'complete');
            statusMessage = `${this.capitalize(stage)} - Custom instructions provided`;
        }
        
        ui.showStatus(statusMessage, response === 'reject' ? 'warning' : 'success');
    }

    // ============================================================================
    // UTILITY METHODS
    // ============================================================================

    hideApprovalUI(stage) {
        const approvalSection = document.getElementById(`${stage}ApprovalSection`);
        if (approvalSection) {
            approvalSection.remove();
        }
        
        const agentCard = document.getElementById(`${stage}Card`);
        if (agentCard) {
            agentCard.classList.remove('approval-active');
        }
    }

    showCustomInput(stage) {
        const customSection = document.querySelector(`#${stage}ApprovalSection .custom-input-section`);
        if (customSection) {
            customSection.style.display = 'block';
            const textarea = document.getElementById(`${stage}CustomInput`);
            if (textarea) textarea.focus();
        }
    }

    hideCustomInput(stage) {
        const customSection = document.querySelector(`#${stage}ApprovalSection .custom-input-section`);
        if (customSection) {
            customSection.style.display = 'none';
            const textarea = document.getElementById(`${stage}CustomInput`);
            if (textarea) textarea.value = '';
        }
    }

    scrollToAgent(stage) {
        const agentCard = document.getElementById(`${stage}Card`);
        if (agentCard) {
            agentCard.scrollIntoView({ behavior: 'smooth' });
        }
    }

    extractIncidentCount(requestData) {
        const content = requestData.content || requestData.prompt || '';
        const patterns = [
            /found (\d+) related/i,
            /(\d+) historical incidents/i,
            /analysis of (\d+) historical/i
        ];
        
        for (const pattern of patterns) {
            const match = content.match(pattern);
            if (match) return parseInt(match[1], 10);
        }
        
        return 0;
    }

    resetState() {
        this.awaitingApproval = false;
        this.currentStage = null;
    }

    capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // ============================================================================
    // CONTEXT DETAILS (if needed)
    // ============================================================================

    showContextDetails() {
        if (!this.contextData) {
            ui.showStatus('No detailed context data available', 'warning');
            return;
        }
        
        // Create and show context details modal
        // Implementation would be similar to the original but simplified
        debugLogger.debugLog('📋 APPROVAL: Context details requested');
        ui.showStatus('Context details feature - implementation needed', 'info');
    }
}

// ============================================================================
// BACKWARD COMPATIBILITY EXPORTS
// ============================================================================

// Create singleton instance
const approvalWorkflow = new ApprovalWorkflow();

// Export legacy API for backward compatibility
export function handleApprovalRequest(data) {
    return approvalWorkflow.handleApprovalRequest(data);
}

export function hideAllApprovalButtons() {
    return approvalWorkflow.hideAllApprovals();
}

export function getCurrentApprovalStage() {
    return approvalWorkflow.getCurrentStage();
}

export function getAwaitingApproval() {
    return approvalWorkflow.isAwaitingApproval();
}

export function setAwaitingApproval(value) {
    if (!value) {
        approvalWorkflow.resetState();
    }
}

// Legacy functions
export function showApprovalButtons() {
    // Legacy compatibility - now handled by handleApprovalRequest
}

export function hideApprovalButtons() {
    return approvalWorkflow.hideAllApprovals();
}

export function approveAnalysis() {
    const stage = approvalWorkflow.getCurrentStage();
    if (stage) {
        approvalWorkflow.sendApprovalResponse(stage, 'approve');
    }
}

export function rejectAnalysis() {
    const stage = approvalWorkflow.getCurrentStage();
    if (stage) {
        approvalWorkflow.sendApprovalResponse(stage, 'reject');
    }
}

export function handleApprovalTimeout() {
    // Handle timeout - simplified
    approvalWorkflow.hideAllApprovals();
    ui.showStatus('Approval timeout - Analysis continuing automatically', 'warning');
}