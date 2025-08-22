// services/ai-agents/src/static/js/modules/ui-manager.js - CLEAN FLOW IMPLEMENTATION
// Handles all UI operations with proper status flow

export class UIManager {
    constructor() {
        this.toastContainer = null;
        this.currentApproval = null;
    }

    async initialize() {
        this.setupToastContainer();
        this.resetAllStates();
        console.log('✅ UI Manager initialized');
    }

    // ============================================================================
    // STATUS AND NOTIFICATIONS
    // ============================================================================

    showStatus(message, type = 'info') {
        const toast = this.createToast(message, type);
        this.toastContainer.appendChild(toast);

        setTimeout(() => toast.remove(), 5000);
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    showWelcome() {
        this.showStatus('🚀 SOC Dashboard Ready', 'success');
    }

    showError(message) {
        this.showStatus(`❌ ${message}`, 'error');
    }

    // ============================================================================
    // CONNECTION STATUS
    // ============================================================================

    setConnectionStatus(status) {
        const indicator = document.getElementById('connectionIndicator');
        const statusText = document.getElementById('connectionStatus');
        
        if (!indicator || !statusText) return;

        indicator.className = 'status-indicator';
        
        switch (status) {
            case 'connected':
                indicator.classList.add('connected');
                statusText.textContent = 'Connected';
                break;
            case 'connecting':
                indicator.classList.add('connecting');
                statusText.textContent = 'Connecting...';
                break;
            case 'disconnected':
                statusText.textContent = 'Disconnected';
                break;
        }
    }

    // ============================================================================
    // PROGRESS TRACKING
    // ============================================================================

    updateProgress(percent, text) {
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        
        if (progressBar) progressBar.style.width = `${percent}%`;
        if (progressText) progressText.textContent = text || `${percent}%`;
    }

    updateLogCounter(count) {
        const counter = document.getElementById('logCounter');
        if (counter) counter.textContent = `${count} events`;
    }

    // ============================================================================
    // AGENT MANAGEMENT - CLEAN FLOW IMPLEMENTATION
    // ============================================================================

    updateAgent(agentType, status, outputText = null) {
        console.log(`🔄 Agent ${agentType} → ${status}`);
        
        // Update status badge
        const statusElement = document.getElementById(`${agentType}Status`);
        if (statusElement) {
            statusElement.className = `status-badge status-${status}`;
            statusElement.textContent = this.formatStatusText(status);
        }

        // Update output if provided
        if (outputText) {
            const outputElement = document.getElementById(`${agentType}Output`);
            if (outputElement) {
                outputElement.textContent = outputText;
            }
        }

        // Update card visual state
        const card = document.getElementById(`${agentType}Card`);
        if (card) {
            card.classList.remove('active', 'approval-active');
            
            if (status === 'awaiting-approval') {
                card.classList.add('approval-active');
            } else if (status === 'complete') {
                card.classList.add('active');
            }
        }

        // CLEAN SPINNER LOGIC:
        // active = show spinner
        // awaiting-approval = hide spinner  
        // complete = hide spinner
        // pending = hide spinner
        if (status === 'active') {
            this.showSpinner(agentType);
            this.hideApprovalForAgent(agentType); // Clear any existing approval
        } else {
            this.hideSpinner(agentType);
        }
    }

    formatStatusText(status) {
        const statusMap = {
            'pending': 'Pending',
            'active': 'Processing...',
            'awaiting-approval': 'Awaiting Decision',
            'complete': 'Complete',
            'error': 'Error'
        };
        return statusMap[status] || status;
    }

    showSpinner(agentType) {
        const spinner = document.getElementById(`${agentType}Spinner`);
        if (spinner) {
            spinner.style.display = 'flex';
        }
    }

    hideSpinner(agentType) {
        const spinner = document.getElementById(`${agentType}Spinner`);
        if (spinner) {
            spinner.style.display = 'none';
        }
    }

    // ============================================================================
    // APPROVAL WORKFLOW - SIMPLIFIED
    // ============================================================================

    showApprovalForAgent(agentType, prompt, responseCallback) {
        // Hide any existing approval
        this.hideCurrentApproval();
        
        // Create approval section
        const approvalSection = this.createApprovalSection(agentType, prompt, responseCallback);
        this.attachApprovalToAgent(agentType, approvalSection);
        
        // Set agent status to awaiting-approval (this will hide spinner automatically)
        this.updateAgent(agentType, 'awaiting-approval');
        
        this.currentApproval = { stage: agentType, element: approvalSection };
        this.showStatus(`${agentType} decision required`, 'warning');
    }

    createApprovalSection(stage, prompt, responseCallback) {
        const section = document.createElement('div');
        section.className = 'approval-section';
        section.id = `${stage}ApprovalSection`;
        
        section.innerHTML = `
            <div class="approval-prompt">
                <h4>${this.getStageTitle(stage)}</h4>
                <p>${prompt}</p>
            </div>
            <div class="button-group">
                <button class="btn btn-approve" data-action="approve">✅ Approve</button>
                <button class="btn btn-reject" data-action="reject">❌ Reject</button>
                <button class="btn btn-custom" data-action="custom">✏️ Custom</button>
            </div>
            <div class="custom-input-section" style="display:none;">
                <textarea placeholder="Enter custom instructions..."></textarea>
                <button class="btn btn-primary" data-action="submit-custom">Submit</button>
                <button class="btn btn-secondary" data-action="cancel-custom">Cancel</button>
            </div>
        `;

        this.attachApprovalHandlers(section, responseCallback);
        return section;
    }

    getStageTitle(stage) {
        const titles = {
            'triage': 'Threat Investigation Approval',
            'context': 'Context Validation',
            'analyst': 'Action Authorization'
        };
        return titles[stage] || 'Approval Required';
    }

    attachApprovalHandlers(section, responseCallback) {
        section.addEventListener('click', (e) => {
            const action = e.target.getAttribute('data-action');
            if (!action) return;

            switch (action) {
                case 'approve':
                    responseCallback('approve');
                    this.showStatus('Approved - proceeding...', 'success');
                    break;
                case 'reject':
                    responseCallback('reject');
                    this.showStatus('Rejected - stopping workflow', 'error');
                    break;
                case 'custom':
                    section.querySelector('.custom-input-section').style.display = 'block';
                    break;
                case 'submit-custom':
                    const customText = section.querySelector('textarea').value.trim();
                    if (customText) {
                        responseCallback(`custom: ${customText}`);
                        this.showStatus('Custom response sent', 'info');
                    } else {
                        this.showStatus('Please enter custom instructions', 'warning');
                    }
                    break;
                case 'cancel-custom':
                    section.querySelector('.custom-input-section').style.display = 'none';
                    break;
            }
        });
    }

    attachApprovalToAgent(stage, section) {
        const agentCard = document.getElementById(`${stage}Card`);
        if (!agentCard) return;

        const agentContent = agentCard.querySelector('.agent-content');
        if (agentContent) {
            agentContent.parentNode.insertBefore(section, agentContent.nextSibling);
        }
    }

    hideCurrentApproval() {
        if (this.currentApproval) {
            this.currentApproval.element.remove();
            
            const agentCard = document.getElementById(`${this.currentApproval.stage}Card`);
            if (agentCard) {
                agentCard.classList.remove('approval-active');
            }
            
            this.currentApproval = null;
        }
    }

    hideApprovalForAgent(agentType) {
        if (this.currentApproval && this.currentApproval.stage === agentType) {
            this.hideCurrentApproval();
        }
    }

    // ============================================================================
    // ANALYSIS MODE
    // ============================================================================

    setAnalysisMode(active) {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = active;
        }

        if (active) {
            this.resetAgentStates();
        }
    }

    resetAgentStates() {
        const agents = ['triage', 'context', 'analyst'];
        const defaultTexts = {
            'triage': 'Waiting for analysis to begin...',
            'context': 'Waiting for triage completion...',
            'analyst': 'Waiting for context research...'
        };

        agents.forEach(agent => {
            this.updateAgent(agent, 'pending', defaultTexts[agent]);
        });
    }

    // ============================================================================
    // UTILITIES
    // ============================================================================

    clearAll() {
        const logInput = document.getElementById('logInput');
        if (logInput) logInput.value = '';

        this.updateLogCounter(0);
        this.resetAgentStates();
        this.hideCurrentApproval();
        this.updateProgress(0, 'Ready');
    }

    resetAllStates() {
        this.setConnectionStatus('disconnected');
        this.clearAll();
    }

    setupToastContainer() {
        this.toastContainer = document.getElementById('toast-container');
        if (!this.toastContainer) {
            this.toastContainer = document.createElement('div');
            this.toastContainer.id = 'toast-container';
            document.body.appendChild(this.toastContainer);
        }
    }

    createToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        toast.addEventListener('click', () => toast.remove());
        
        return toast;
    }
}