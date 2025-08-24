// services/ai-agents/src/static/js/modules/ui-manager.js - STRATEGIC FIX
// Fix: Preserve agent results when completing, don't revert to waiting messages

export class UIManager {
    constructor() {
        this.toastContainer = null;
        this.currentApproval = null;
        // STRATEGIC FIX: Track agent outputs to preserve them
        this.agentOutputs = {
            triage: null,
            context: null,
            analyst: null
        };
        this.agentStates = {
            triage: 'pending',
            context: 'pending', 
            analyst: 'pending'
        };
    }

    async initialize() {
        this.setupToastContainer();
        this.resetAllStates();
        console.log('✅ UI Manager initialized with strategic result preservation');
    }

    // ============================================================================
    // CORE AGENT FLOW - STRATEGIC FIX TO PRESERVE RESULTS
    // ============================================================================

    /**
     * Set agent to active state (shows spinner)
     */
    setAgentActive(agentType) {
        console.log(`🔄 Agent ${agentType} → active`);
        this.agentStates[agentType] = 'active';
        this.updateAgentStatus(agentType, 'active');
        this.showSpinner(agentType);
        this.hideApprovalForAgent(agentType);
        // Don't clear output - preserve any existing results
    }

    /**
     * Set agent to awaiting decision (shows results + approval UI)
     */
    setAgentAwaitingDecision(agentType, results, approvalCallback) {
        console.log(`🔄 Agent ${agentType} → awaiting-decision`);
        this.agentStates[agentType] = 'awaiting-decision';
        this.updateAgentStatus(agentType, 'awaiting-decision');
        this.hideSpinner(agentType);
        
        // STRATEGIC FIX: Store and update output - this is the key insight
        this.agentOutputs[agentType] = results;
        this.updateAgentOutput(agentType, results);
        
        this.showApprovalForAgent(agentType, approvalCallback);
    }

    /**
     * Set agent to complete (hides approval, PRESERVES results)
     */
    setAgentComplete(agentType) {
        console.log(`🔄 Agent ${agentType} → complete (preserving results)`);
        this.agentStates[agentType] = 'complete';
        this.updateAgentStatus(agentType, 'complete');
        this.hideApprovalForAgent(agentType);
        
        // STRATEGIC FIX: The core issue was here - preserve the output text!
        if (this.agentOutputs[agentType]) {
            // Ensure the results remain displayed after completion
            this.updateAgentOutput(agentType, this.agentOutputs[agentType]);
            console.log(`✅ Preserved ${agentType} results in output display`);
        } else {
            console.warn(`⚠️ No stored output for ${agentType} to preserve`);
        }
    }

    /**
     * Set agent to pending (initial state only)
     */
    setAgentPending(agentType, message = null) {
        console.log(`🔄 Agent ${agentType} → pending`);
        this.agentStates[agentType] = 'pending';
        this.updateAgentStatus(agentType, 'pending');
        this.hideSpinner(agentType);
        this.hideApprovalForAgent(agentType);
        
        // STRATEGIC FIX: Only set waiting message if explicitly provided or no results exist
        if (message) {
            this.agentOutputs[agentType] = message;
            this.updateAgentOutput(agentType, message);
        }
    }

    // ============================================================================
    // INTERNAL HELPERS - Enhanced with state tracking
    // ============================================================================

    updateAgentStatus(agentType, status) {
        const statusElement = document.getElementById(`${agentType}Status`);
        if (statusElement) {
            statusElement.className = `status-badge status-${status}`;
            statusElement.textContent = this.formatStatusText(status);
        }

        const card = document.getElementById(`${agentType}Card`);
        if (card) {
            card.classList.remove('active', 'approval-active');
            if (status === 'active') {
                card.classList.add('active');
            } else if (status === 'awaiting-decision') {
                card.classList.add('approval-active');
            }
        }
    }

    formatStatusText(status) {
        const statusMap = {
            'pending': 'Pending',
            'active': 'Processing...',
            'awaiting-decision': 'Awaiting Decision', 
            'complete': 'Complete',
            'error': 'Error'
        };
        return statusMap[status] || status;
    }

    updateAgentOutput(agentType, text) {
        const outputElement = document.getElementById(`${agentType}Output`);
        if (outputElement) {
            outputElement.textContent = text;
            console.log(`📝 Updated ${agentType} output (${text.length} chars)`);
        } else {
            console.error(`❌ Output element not found: ${agentType}Output`);
        }
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
    // APPROVAL WORKFLOW
    // ============================================================================

    showApprovalForAgent(agentType, responseCallback) {
        // Hide any existing approval
        this.hideCurrentApproval();
        
        // Create approval section
        const approvalSection = this.createApprovalSection(agentType, responseCallback);
        this.attachApprovalToAgent(agentType, approvalSection);
        
        this.currentApproval = { stage: agentType, element: approvalSection };
        this.showStatus(`${agentType} decision required`, 'warning');
    }

    createApprovalSection(stage, responseCallback) {
        const section = document.createElement('div');
        section.className = 'approval-section';
        section.id = `${stage}ApprovalSection`;
        
        section.innerHTML = `
            <div class="approval-prompt">
                <h4>${this.getStageTitle(stage)}</h4>
                <p>Review the ${stage} results and decide how to proceed.</p>
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
            this.currentApproval = null;
        }
    }

    hideApprovalForAgent(agentType) {
        if (this.currentApproval && this.currentApproval.stage === agentType) {
            this.hideCurrentApproval();
        }
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
    // ANALYSIS MODE - STRATEGIC FIX FOR STATE MANAGEMENT
    // ============================================================================

    setAnalysisMode(active) {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = active;
        }

        if (active) {
            // STRATEGIC FIX: Only reset agents that haven't started processing
            this.smartResetAgentStates();
        }
    }

    smartResetAgentStates() {
        console.log('🎯 Smart reset - preserving completed agent results');
        
        // Default messages for agents that haven't started
        const defaultTexts = {
            'triage': 'Waiting for analysis to begin...',
            'context': 'Waiting for triage completion...',
            'analyst': 'Waiting for context research...'
        };

        // Only reset agents that are still pending or haven't been processed
        Object.keys(this.agentStates).forEach(agentType => {
            const currentState = this.agentStates[agentType];
            
            if (currentState === 'complete' && this.agentOutputs[agentType]) {
                // Keep completed agents with their results
                console.log(`✅ Preserving completed ${agentType} results`);
                this.setAgentComplete(agentType); // This will preserve outputs
            } else {
                // Reset pending/unprocessed agents
                console.log(`🔄 Resetting ${agentType} to pending`);
                this.setAgentPending(agentType, defaultTexts[agentType]);
            }
        });
    }

    resetAgentStates() {
        // STRATEGIC FIX: This is now smarter - called from smartResetAgentStates
        console.log('🔄 Resetting agent states with smart preservation');
        this.smartResetAgentStates();
    }

    // ============================================================================
    // UTILITIES - Enhanced with preservation logic
    // ============================================================================

    clearAll() {
        const logInput = document.getElementById('logInput');
        if (logInput) logInput.value = '';

        this.updateLogCounter(0);
        
        // STRATEGIC FIX: Full clear - reset stored outputs and states
        this.agentOutputs = {
            triage: null,
            context: null,
            analyst: null
        };
        this.agentStates = {
            triage: 'pending',
            context: 'pending',
            analyst: 'pending'
        };
        
        this.resetAgentStates();
        this.hideCurrentApproval();
        this.updateProgress(0, 'Ready');
        
        console.log('🧹 Full clear completed - all states and outputs reset');
    }

    resetAllStates() {
        this.setConnectionStatus('disconnected');
        
        // Set initial waiting messages only
        const initialTexts = {
            'triage': 'Waiting for analysis to begin...',
            'context': 'Waiting for triage completion...',
            'analyst': 'Waiting for context research...'
        };
        
        Object.keys(initialTexts).forEach(agentType => {
            this.setAgentPending(agentType, initialTexts[agentType]);
        });
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

    // ============================================================================
    // DEBUG HELPERS - For monitoring state preservation
    // ============================================================================

    getAgentStates() {
        return {
            states: { ...this.agentStates },
            outputs: Object.keys(this.agentOutputs).reduce((acc, key) => {
                acc[key] = this.agentOutputs[key] ? 'has_content' : 'no_content';
                return acc;
            }, {}),
            currentApproval: this.currentApproval?.stage || 'none'
        };
    }

    logStateDebug() {
        console.log('🔍 UI State Debug:', this.getAgentStates());
    }
}