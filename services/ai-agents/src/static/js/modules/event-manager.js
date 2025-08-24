// UPDATED: services/ai-agents/src/static/js/modules/event-manager.js - ADD AUTO-APPROVE SUPPORT
// Enhanced with auto-approve toggle event handling

export class EventManager {
    constructor() {
        this.dashboard = null;
        this.listeners = [];
    }

    async initialize(dashboard) {
        this.dashboard = dashboard;
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        console.log('✅ Event Manager initialized with auto-approve support');
    }

    // ============================================================================
    // EVENT SETUP - Enhanced with auto-approve
    // ============================================================================

    setupEventListeners() {
        // Main control buttons
        this.addListener('retrieveBtn', 'click', () => {
            this.dashboard.retrieveLogs();
        });

        this.addListener('analyzeBtn', 'click', () => {
            this.dashboard.startAnalysis();
        });

        this.addListener('exportBtn', 'click', () => {
            this.dashboard.exportResults();
        });

        this.addListener('clearBtn', 'click', () => {
            this.dashboard.clearResults();
        });

        // Debug toggle
        this.addListener('debugToggle', 'click', () => {
            this.dashboard.debugManager.toggle();
        });

        // NEW: Auto-approve toggle
        this.addListener('autoApproveToggle', 'click', () => {
            this.dashboard.toggleAutoApprove();
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
            // Global shortcuts (Ctrl+Shift combinations)
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
                    case 'R':
                        e.preventDefault();
                        this.dashboard.retrieveLogs();
                        break;
                    case 'E':
                        e.preventDefault();
                        this.dashboard.exportResults();
                        break;
                    // NEW: Auto-approve toggle shortcut
                    case 'M':
                        e.preventDefault();
                        this.dashboard.toggleAutoApprove();
                        this.showKeyboardFeedback('autoApproveToggle');
                        break;
                }
            }

            // Approval shortcuts (when approval UI is visible)
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

            // NEW: Quick auto-approve toggle when no approval UI visible
            if (!this.dashboard.uiManager.currentApproval) {
                switch (e.key) {
                    case 'F1':
                        e.preventDefault();
                        this.dashboard.toggleAutoApprove();
                        this.showKeyboardFeedback('autoApproveToggle');
                        break;
                }
            }
        });
    }

    // ============================================================================
    // HELPER METHODS - Enhanced with auto-approve support
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

    showKeyboardFeedback(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.transform = 'scale(0.95)';
            element.style.opacity = '0.8';
            setTimeout(() => {
                element.style.transform = '';
                element.style.opacity = '';
            }, 150);
        }
    }

    showWebSocketStats() {
        const stats = this.dashboard.websocketManager.getStats();
        const message = `WebSocket Stats:
Connected: ${stats.connected}
Messages Sent: ${stats.messagesSent}
Messages Received: ${stats.messagesReceived}
Ready State: ${stats.readyState}
Reconnect Attempts: ${stats.reconnectAttempts}`;
        
        console.log(message);
        this.dashboard.debugManager.info('WebSocket stats displayed in console');
        this.dashboard.uiManager.showStatus('Stats logged to console', 'info');
    }

    // ============================================================================
    // NEW: Auto-approve specific helpers
    // ============================================================================

    getAutoApproveShortcutHelp() {
        return `Auto-Approve Keyboard Shortcuts:
• Ctrl+Shift+M - Toggle auto-approve mode
• F1 - Quick toggle auto-approve (when no approval dialog)

When auto-approve is ON:
• All workflow stages approve automatically after 2-second delay
• Visual countdown indicators show approval progress
• Workflow can run unattended to completion

When auto-approve is OFF:
• Manual approval required at each stage
• Standard approval buttons (1=Approve, 2=Reject, 3=Custom)
• Workflow pauses until user decision`;
    }

    showAutoApproveHelp() {
        const helpText = this.getAutoApproveShortcutHelp();
        console.log(helpText);
        this.dashboard.uiManager.showStatus('Auto-approve help logged to console', 'info');
    }

    // ============================================================================
    // ENHANCED DEBUG SUPPORT
    // ============================================================================

    getEventStats() {
        return {
            totalListeners: this.listeners.length,
            autoApproveEnabled: this.dashboard.autoApproveMode,
            currentApprovalVisible: !!this.dashboard.uiManager.currentApproval,
            analysisInProgress: this.dashboard.analysisInProgress
        };
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