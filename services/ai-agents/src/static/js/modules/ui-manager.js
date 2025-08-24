// FIXED: src/static/js/modules/ui-manager.js - ADD storeAgentOutput METHOD
// Fix: Added method to properly store agent outputs before completion

export class UIManager {
    constructor() {
        this.toastContainer = null;
        this.currentApproval = null;
        // Track agent outputs to preserve them
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
        
        // Auto-approval state tracking
        this.autoApprovalIndicators = new Map();
    }

    async initialize() {
        this.setupToastContainer();
        this.resetAllStates();
        console.log('✅ UI Manager initialized with auto-approve support');
    }

    // ============================================================================
    // 🔧 NEW: EXPLICIT OUTPUT STORAGE METHOD
    // ============================================================================

    /**
     * Store agent output explicitly (for auto-approve workflow)
     */
    storeAgentOutput(agentType, output) {
        this.agentOutputs[agentType] = output;
        this.updateAgentOutput(agentType, output);
        console.log(`💾 Stored ${agentType} output (${output.length} chars) for preservation`);
    }

    // ============================================================================
    // AUTO-APPROVE UI SUPPORT
    // ============================================================================

    /**
     * Show visual indicator that auto-approval is in progress
     */
    showAutoApprovalIndicator(stage, delayMs) {
        // Create countdown indicator
        const indicator = this.createAutoApprovalIndicator(stage, delayMs);
        this.attachAutoApprovalIndicator(stage, indicator);
        this.autoApprovalIndicators.set(stage, indicator);
        
        // Start countdown
        this.startAutoApprovalCountdown(stage, delayMs);
    }

    createAutoApprovalIndicator(stage, delayMs) {
        const indicator = document.createElement('div');
        indicator.className = 'auto-approval-indicator';
        indicator.id = `${stage}AutoApprovalIndicator`;
        
        const seconds = Math.ceil(delayMs / 1000);
        indicator.innerHTML = `
            <div class="auto-approval-content">
                <div class="auto-approval-icon">🤖</div>
                <div class="auto-approval-text">
                    <strong>Auto-Approval Active</strong>
                    <br>Approving in <span class="countdown">${seconds}</span> seconds...
                </div>
                <div class="auto-approval-progress">
                    <div class="progress-bar-auto" style="animation-duration: ${delayMs}ms;"></div>
                </div>
            </div>
        `;
        
        return indicator;
    }

    attachAutoApprovalIndicator(stage, indicator) {
        const agentCard = document.getElementById(`${stage}Card`);
        if (!agentCard) return;

        const agentContent = agentCard.querySelector('.agent-content');
        if (agentContent) {
            agentContent.parentNode.insertBefore(indicator, agentContent.nextSibling);
        }
    }

    startAutoApprovalCountdown(stage, delayMs) {
        const indicator = this.autoApprovalIndicators.get(stage);
        if (!indicator) return;

        const countdownElement = indicator.querySelector('.countdown');
        const totalSeconds = Math.ceil(delayMs / 1000);
        
        let remainingSeconds = totalSeconds;
        
        const countdownInterval = setInterval(() => {
            remainingSeconds--;
            if (countdownElement) {
                countdownElement.textContent = remainingSeconds;
            }
            
            if (remainingSeconds <= 0) {
                clearInterval(countdownInterval);
                this.hideAutoApprovalIndicator(stage);
            }
        }, 1000);
    }

    hideAutoApprovalIndicator(stage) {
        const indicator = this.autoApprovalIndicators.get(stage);
        if (indicator) {
            indicator.remove();
            this.autoApprovalIndicators.delete(stage);
        }
    }

    // ============================================================================
    // CORE AGENT FLOW - Enhanced with auto-approve awareness
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
        this.hideAutoApprovalIndicator(agentType);
    }

    /**
     * Set agent to awaiting decision (shows results + approval UI)
     */
    setAgentAwaitingDecision(agentType, results, approvalCallback) {
        console.log(`🔄 Agent ${agentType} → awaiting-decision`);
        this.agentStates[agentType] = 'awaiting-decision';
        this.updateAgentStatus(agentType, 'awaiting-decision');
        this.hideSpinner(agentType);
        
        // Store and update output
        this.agentOutputs[agentType] = results;
        this.updateAgentOutput(agentType, results);
        
        this.showApprovalForAgent(agentType, approvalCallback);
    }

    /**
     * 🔧 FIXED: Set agent to complete (hides approval, PRESERVES results)
     */
    setAgentComplete(agentType) {
        console.log(`🔄 Agent ${agentType} → complete (preserving results)`);
        this.agentStates[agentType] = 'complete';
        this.updateAgentStatus(agentType, 'complete');
        
        // 🔧 FIX: Hide spinner when completing
        this.hideSpinner(agentType);
        this.hideApprovalForAgent(agentType);
        this.hideAutoApprovalIndicator(agentType);
        
        // 🔧 CRITICAL FIX: The preserved output should already be stored
        if (this.agentOutputs[agentType]) {
            // Results were already stored, just ensure they're displayed
            this.updateAgentOutput(agentType, this.agentOutputs[agentType]);
            console.log(`✅ Preserved ${agentType} results: ${this.agentOutputs[agentType].length} chars`);
        } else {
            console.warn(`⚠️ No stored output for ${agentType} to preserve!`);
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
        this.hideAutoApprovalIndicator(agentType);
        
        if (message) {
            this.agentOutputs[agentType] = message;
            this.updateAgentOutput(agentType, message);
        }
    }

    /**
     * Update agent output text
     */
    updateAgentOutput(agentType, text) {
        const outputElement = document.getElementById(`${agentType}Output`);
        if (outputElement) {
            outputElement.textContent = text;
            console.log(`📝 Updated ${agentType} output display (${text.length} chars)`);
        } else {
            console.error(`❌ Output element not found: ${agentType}Output`);
        }
    }

    // ============================================================================
    // INTERNAL HELPERS
    // ============================================================================

    updateAgentStatus(agentType, status) {
        const statusElement = document.getElementById(`${agentType}Status`);
        if (statusElement) {
            statusElement.className = `status-badge status-${status}`;
            statusElement.textContent = this.formatStatusText(status);
        }

        const card = document.getElementById(`${agentType}Card`);
        if (card) {
            card.classList.remove('active', 'approval-active', 'auto-approval-active');
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

    showSpinner(agentType) {
        const spinner = document.getElementById(`${agentType}Spinner`);
        if (spinner) {
            spinner.style.display = 'flex';
            spinner.classList.add('show'); // Backup CSS class
            console.log(`🔄 Showing spinner for ${agentType}`);
        }
    }

    hideSpinner(agentType) {
        const spinner = document.getElementById(`${agentType}Spinner`);
        if (spinner) {
            spinner.style.display = 'none';
            spinner.classList.remove('show'); // Remove backup CSS class
            console.log(`✅ Hidden spinner for ${agentType}`);
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
        this.showStatus('🚀 SOC Dashboard Ready - Auto-approve available!', 'success');
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
    // ANALYSIS MODE
    // ============================================================================

    setAnalysisMode(active) {
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = active;
        }

        if (active) {
            this.smartResetAgentStates();
        }
    }

    smartResetAgentStates() {
        console.log('🎯 Smart reset - preserving completed agent results');
        
        const defaultTexts = {
            'triage': 'Waiting for analysis to begin...',
            'context': 'Waiting for triage completion...',
            'analyst': 'Waiting for context research...'
        };

        Object.keys(this.agentStates).forEach(agentType => {
            const currentState = this.agentStates[agentType];
            
            if (currentState === 'complete' && this.agentOutputs[agentType]) {
                console.log(`✅ Preserving completed ${agentType} results`);
                this.setAgentComplete(agentType);
            } else {
                console.log(`🔄 Resetting ${agentType} to pending`);
                this.setAgentPending(agentType, defaultTexts[agentType]);
            }
        });
    }

    resetAgentStates() {
        console.log('🔄 Resetting agent states with smart preservation');
        this.smartResetAgentStates();
    }

    // ============================================================================
    // UTILITIES
    // ============================================================================

    clearAll() {
        const logInput = document.getElementById('logInput');
        if (logInput) logInput.value = '';

        this.updateLogCounter(0);
        
        // Full clear - reset stored outputs and states
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
        
        // Clear all auto-approval indicators
        for (const [stage, indicator] of this.autoApprovalIndicators) {
            indicator.remove();
        }
        this.autoApprovalIndicators.clear();
        
        this.resetAgentStates();
        this.hideCurrentApproval();
        this.updateProgress(0, 'Ready');
        
        console.log('🧹 Full clear completed - all states and outputs reset');
    }

    resetAllStates() {
        this.setConnectionStatus('disconnected');
        
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
    // DEBUG HELPERS
    // ============================================================================

    getAgentStates() {
        return {
            states: { ...this.agentStates },
            outputs: Object.keys(this.agentOutputs).reduce((acc, key) => {
                acc[key] = this.agentOutputs[key] ? 
                    `has_content (${this.agentOutputs[key].length} chars)` : 'no_content';
                return acc;
            }, {}),
            currentApproval: this.currentApproval?.stage || 'none',
            autoApprovalIndicators: Array.from(this.autoApprovalIndicators.keys())
        };
    }

    logStateDebug() {
        console.log('🔍 UI State Debug:', this.getAgentStates());
    }
}

// Add CSS for auto-approval indicator (inline styles for this feature)
const autoApprovalCSS = `
.auto-approval-indicator {
    background: linear-gradient(45deg, #27ae60, #2ecc71);
    border-radius: var(--radius-lg);
    padding: var(--spacing-lg);
    margin-top: var(--spacing-md);
    color: white;
    animation: pulse 2s infinite;
    border: 1px solid rgba(46, 204, 113, 0.3);
    box-shadow: 0 4px 15px rgba(46, 204, 113, 0.2);
}

.auto-approval-content {
    display: flex;
    align-items: center;
    gap: var(--spacing-lg);
    text-align: left;
}

.auto-approval-icon {
    font-size: 2em;
    opacity: 0.9;
}

.auto-approval-text {
    flex: 1;
    font-size: 0.9em;
    line-height: 1.4;
}

.auto-approval-text strong {
    font-size: 1.1em;
}

.countdown {
    font-weight: bold;
    font-size: 1.2em;
    color: #fff;
    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
}

.auto-approval-progress {
    width: 100%;
    height: 4px;
    background: rgba(255, 255, 255, 0.3);
    border-radius: 2px;
    overflow: hidden;
    margin-top: var(--spacing-sm);
}

.progress-bar-auto {
    height: 100%;
    width: 0%;
    background: white;
    border-radius: 2px;
    animation: auto-progress linear;
}

@keyframes auto-progress {
    from { width: 0%; }
    to { width: 100%; }
}
`;

// Add styles to document head
if (typeof document !== 'undefined') {
    const styleElement = document.createElement('style');
    styleElement.textContent = autoApprovalCSS;
    document.head.appendChild(styleElement);
}