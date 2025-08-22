// services/ai-agents/src/static/js/modules/keyboard-manager.js
// Centralized keyboard shortcut management

import * as debugLogger from '../debugLogger.js';
import * as ui from '../ui.js';
import * as progressManager from '../progressManager.js';
import * as approvalWorkflow from '../approvalWorkflow.js';

export class KeyboardManager {
    constructor() {
        this.shortcuts = new Map();
        this.approvalShortcuts = new Map();
        this.setupShortcuts();
    }

    initialize() {
        debugLogger.debugLog('Setting up keyboard shortcuts...');
        
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        this.createHelpButton();
        
        // Log shortcuts to console
        setTimeout(() => this.logShortcuts(), 1000);
    }

    setupShortcuts() {
        // Global shortcuts
        this.shortcuts.set('ctrl+shift+d', () => {
            debugLogger.toggleDebugMode();
        });
        
        this.shortcuts.set('ctrl+shift+a', () => {
            if (!progressManager.getAnalysisInProgress()) {
                progressManager.startAnalysis();
            }
        });
        
        this.shortcuts.set('ctrl+shift+c', () => {
            ui.clearResults();
            approvalWorkflow.hideAllApprovalButtons();
        });

        // Approval shortcuts (when awaiting approval)
        this.approvalShortcuts.set('enter', 'approve');
        this.approvalShortcuts.set('y', 'approve');
        this.approvalShortcuts.set('escape', 'reject');
        this.approvalShortcuts.set('n', 'reject');
        
        // Stage-specific shortcuts
        this.approvalShortcuts.set('1', 'approve');
        this.approvalShortcuts.set('2', 'reject');
        this.approvalShortcuts.set('3', 'custom');
    }

    handleKeyDown(event) {
        // Build key combination string
        const key = this.buildKeyString(event);
        
        // Handle global shortcuts
        if (this.shortcuts.has(key)) {
            event.preventDefault();
            this.shortcuts.get(key)();
            return;
        }
        
        // Handle approval shortcuts
        if (approvalWorkflow.getAwaitingApproval()) {
            this.handleApprovalShortcut(event, key);
        }
    }

    buildKeyString(event) {
        const parts = [];
        
        if (event.ctrlKey) parts.push('ctrl');
        if (event.shiftKey) parts.push('shift');
        if (event.altKey) parts.push('alt');
        
        parts.push(event.key.toLowerCase());
        
        return parts.join('+');
    }

    handleApprovalShortcut(event, key) {
        const currentStage = approvalWorkflow.getCurrentApprovalStage();
        if (!currentStage) return;

        const action = this.approvalShortcuts.get(key);
        if (!action) return;

        event.preventDefault();
        this.executeApprovalAction(currentStage, action);
    }

    executeApprovalAction(stage, action) {
        debugLogger.debugLog(`Keyboard approval: ${stage} - ${action}`);
        
        // Find and activate the appropriate button
        const buttonSelector = `#${stage}ApprovalSection .btn[data-value="${action}"]`;
        const button = document.querySelector(buttonSelector);
        
        if (button) {
            this.addKeyboardFeedback(button);
            button.click();
            ui.showStatus(`${this.capitalize(stage)} ${action} via keyboard`, 'success');
        } else {
            // Fallback to direct function calls
            if (action === 'approve') {
                approvalWorkflow.approveAnalysis();
            } else if (action === 'reject') {
                approvalWorkflow.rejectAnalysis();
            }
        }
    }

    addKeyboardFeedback(button) {
        button.classList.add('keyboard-activated');
        setTimeout(() => button.classList.remove('keyboard-activated'), 200);
    }

    createHelpButton() {
        const helpButton = document.createElement('div');
        helpButton.id = 'keyboardHelpButton';
        helpButton.innerHTML = '⌨️';
        helpButton.className = 'keyboard-help-button';
        
        helpButton.addEventListener('click', () => this.showHelpModal());
        
        document.body.appendChild(helpButton);
        this.addHelpButtonStyles();
    }

    addHelpButtonStyles() {
        if (document.getElementById('keyboardHelpStyles')) return;
        
        const style = document.createElement('style');
        style.id = 'keyboardHelpStyles';
        style.textContent = `
            .keyboard-help-button {
                position: fixed;
                bottom: 20px;
                left: 20px;
                width: 40px;
                height: 40px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                font-size: 18px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                z-index: 1000;
                transition: all 0.3s ease;
                opacity: 0.8;
            }
            
            .keyboard-help-button:hover {
                opacity: 1;
                transform: scale(1.1);
            }
            
            .keyboard-activated {
                transform: scale(0.95) !important;
                background: linear-gradient(45deg, #56ab2f, #a8e6cf) !important;
                box-shadow: 0 0 20px rgba(86, 171, 47, 0.6) !important;
            }
        `;
        document.head.appendChild(style);
    }

    showHelpModal() {
        const modal = document.createElement('div');
        modal.className = 'keyboard-help-modal';
        
        modal.innerHTML = `
            <div class="modal-content">
                <h3>⌨️ Keyboard Shortcuts</h3>
                
                <div class="shortcut-section">
                    <h4>Global Controls</h4>
                    <div class="shortcut-list">
                        <div><kbd>Ctrl+Shift+D</kbd> Toggle debug mode</div>
                        <div><kbd>Ctrl+Shift+A</kbd> Start analysis</div>
                        <div><kbd>Ctrl+Shift+C</kbd> Clear results</div>
                    </div>
                </div>
                
                <div class="shortcut-section">
                    <h4>Approval Workflow</h4>
                    <div class="shortcut-list">
                        <div><kbd>Enter</kbd> or <kbd>Y</kbd> Approve</div>
                        <div><kbd>Escape</kbd> or <kbd>N</kbd> Reject</div>
                        <div><kbd>1</kbd> Approve (stage-specific)</div>
                        <div><kbd>2</kbd> Reject (stage-specific)</div>
                        <div><kbd>3</kbd> Custom (where available)</div>
                    </div>
                </div>
                
                <button class="close-modal">Close</button>
            </div>
        `;
        
        this.addModalStyles();
        document.body.appendChild(modal);
        
        // Close handlers
        modal.addEventListener('click', (e) => {
            if (e.target === modal || e.target.classList.contains('close-modal')) {
                document.body.removeChild(modal);
            }
        });
        
        document.addEventListener('keydown', function closeOnEscape(e) {
            if (e.key === 'Escape') {
                document.body.removeChild(modal);
                document.removeEventListener('keydown', closeOnEscape);
            }
        });
    }

    addModalStyles() {
        if (document.getElementById('modalStyles')) return;
        
        const style = document.createElement('style');
        style.id = 'modalStyles';
        style.textContent = `
            .keyboard-help-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            }
            
            .modal-content {
                background: white;
                padding: 30px;
                border-radius: 12px;
                max-width: 500px;
                max-height: 80vh;
                overflow-y: auto;
            }
            
            .shortcut-section {
                margin-bottom: 20px;
            }
            
            .shortcut-section h4 {
                color: #667eea;
                margin-bottom: 10px;
            }
            
            .shortcut-list div {
                margin: 5px 0;
                font-family: monospace;
            }
            
            kbd {
                background: #f0f0f0;
                padding: 2px 6px;
                border-radius: 3px;
                font-weight: bold;
            }
            
            .close-modal {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                cursor: pointer;
                width: 100%;
                margin-top: 20px;
            }
        `;
        document.head.appendChild(style);
    }

    logShortcuts() {
        console.log('🚀 SOC Dashboard Keyboard Shortcuts:');
        console.log('  Global Controls:');
        console.log('    • Ctrl+Shift+D → Toggle debug mode');
        console.log('    • Ctrl+Shift+A → Start analysis');
        console.log('    • Ctrl+Shift+C → Clear results');
        console.log('  ');
        console.log('  Approval Workflow:');
        console.log('    • Enter/Y → Approve');
        console.log('    • Escape/N → Reject');
        console.log('    • 1/2/3 → Stage-specific actions');
    }

    capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}