// services/ai-agents/src/static/js/modules/event-manager.js - CLEAN REFACTORED
// Handles DOM events and user interactions

export class EventManager {
    constructor() {
        this.dashboard = null;
        this.listeners = [];
    }

    async initialize(dashboard) {
        this.dashboard = dashboard;
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        console.log('✅ Event Manager initialized');
    }

    // ============================================================================
    // EVENT SETUP
    // ============================================================================

    setupEventListeners() {
        // Main control buttons
        this.addListener('retrieveBtn', 'click', () => {
            this.dashboard.retrieveLogs();
        });

        this.addListener('analyzeBtn', 'click', () => {
            this.dashboard.startAnalysis();
        });

        this.addListener('clearBtn', 'click', () => {
            this.dashboard.clearResults();
        });

        // Debug toggle
        this.addListener('debugToggle', 'click', () => {
            this.dashboard.debugManager.toggle();
        });

        // Log input changes
        this.addListener('logInput', 'input', (e) => {
            const lines = e.target.value.split('\n').filter(line => line.trim());
            this.dashboard.uiManager.updateLogCounter(lines.length);
        });

        // Debug controls
        this.setupDebugControls();
    }

    setupDebugControls() {
        const debugActions = {
            'clearDebugLog': () => this.dashboard.debugManager.clearLog(),
            'exportDebugLog': () => this.dashboard.debugManager.exportLog(),
            'showWebSocketStats': () => this.showWebSocketStats(),
            'testConnection': () => this.dashboard.websocketManager.test()
        };

        document.querySelectorAll('.debug-btn[data-action]').forEach(button => {
            const action = button.getAttribute('data-action');
            if (debugActions[action]) {
                this.addListener(button, 'click', debugActions[action]);
            }
        });
    }

    setupKeyboardShortcuts() {
        this.addListener(document, 'keydown', (e) => {
            // Global shortcuts
            if (e.ctrlKey && e.shiftKey) {
                switch (e.key) {
                    case 'D':
                        e.preventDefault();
                        this.dashboard.debugManager.toggle();
                        break;
                    case 'A':
                        e.preventDefault();
                        if (!this.dashboard.analysisInProgress) {
                            this.dashboard.startAnalysis();
                        }
                        break;
                    case 'C':
                        e.preventDefault();
                        this.dashboard.clearResults();
                        break;
                }
            }

            // Approval shortcuts (when approval is active)
            if (this.dashboard.uiManager.currentApproval) {
                switch (e.key) {
                    case '1':
                    case 'Enter':
                        e.preventDefault();
                        this.clickApprovalButton('approve');
                        break;
                    case '2':
                    case 'Escape':
                        e.preventDefault();
                        this.clickApprovalButton('reject');
                        break;
                    case '3':
                        e.preventDefault();
                        this.clickApprovalButton('custom');
                        break;
                }
            }
        });
    }

    // ============================================================================
    // HELPER METHODS
    // ============================================================================

    addListener(elementOrId, event, handler) {
        const element = typeof elementOrId === 'string' 
            ? document.getElementById(elementOrId) 
            : elementOrId;
            
        if (!element) {
            console.warn(`Element not found: ${elementOrId}`);
            return;
        }

        element.addEventListener(event, handler);
        this.listeners.push({ element, event, handler });
    }

    clickApprovalButton(action) {
        if (!this.dashboard.uiManager.currentApproval) return;
        
        const section = this.dashboard.uiManager.currentApproval.element;
        const button = section.querySelector(`[data-action="${action}"]`);
        if (button) {
            button.click();
            // Add visual feedback
            button.style.transform = 'scale(0.95)';
            setTimeout(() => button.style.transform = '', 100);
        }
    }

    showWebSocketStats() {
        const stats = this.dashboard.websocketManager.getStats();
        const message = `WebSocket Stats:
Connected: ${stats.connected}
Messages Sent: ${stats.messagesSent}
Messages Received: ${stats.messagesReceived}
Ready State: ${stats.readyState}`;
        
        console.log(message);
        this.dashboard.uiManager.showStatus('Stats logged to console', 'info');
    }

    // ============================================================================
    // CLEANUP
    // ============================================================================

    cleanup() {
        this.listeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.listeners = [];
    }
}