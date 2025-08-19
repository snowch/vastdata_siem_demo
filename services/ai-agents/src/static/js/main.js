// Enhanced main.js with multi-stage approval support
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// Set up event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    debugLogger.debugLog('Page loaded, setting up enhanced multi-stage event listeners...');
    
    // Main control buttons
    document.getElementById('retrieveBtn').addEventListener('click', progressManager.retrieveLogs);
    document.getElementById('analyzeBtn').addEventListener('click', progressManager.startAnalysis);
    
    // Clear results button
    document.getElementById('clearBtn')?.addEventListener('click', function() {
        ui.clearResults();
        approvalWorkflow.hideAllApprovalButtons();
        debugLogger.debugLog('All results and approval buttons cleared');
    });
    
    // Debug toggle button
    document.getElementById('debugToggle').addEventListener('click', function() {
        debugLogger.toggleDebugMode();
    });
    
    // Debug control buttons using data-action attributes
    document.querySelectorAll('.debug-btn[data-action]').forEach(button => {
        button.addEventListener('click', function() {
            const action = this.getAttribute('data-action');
            
            switch(action) {
                case 'clearDebugLog':
                    debugLogger.clearDebugLog();
                    break;
                    
                case 'exportDebugLog':
                    debugLogger.exportDebugLog();
                    break;
                    
                case 'showWebSocketStats':
                    websocket.showWebSocketStats();
                    break;
                    
                case 'testConnection':
                    websocket.testConnection();
                    break;
            }
        });
    });
    
    // Initialize WebSocket connection
    websocket.initWebSocket();
    
    // Update log counter when text area changes
    document.getElementById('logInput').addEventListener('input', function() {
        progressManager.updateLogCounter(this.value);
    });
    
    // Enhanced keyboard shortcuts for multi-stage approval
    document.addEventListener('keydown', function(e) {
        // Debug mode toggle
        if (e.ctrlKey && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            debugLogger.toggleDebugMode();
        }
        
        // Clear results
        if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            e.preventDefault();
            ui.clearResults();
            approvalWorkflow.hideAllApprovalButtons();
        }
        
        // Start analysis
        if (e.ctrlKey && e.shiftKey && e.key === 'A') {
            e.preventDefault();
            if (!progressManager.getAnalysisInProgress()) {
                progressManager.startAnalysis();
            }
        }
        
        // Multi-stage approval shortcuts
        if (approvalWorkflow.getAwaitingApproval()) {
            const currentStage = approvalWorkflow.getCurrentApprovalStage();
            
            // Universal approve/reject
            if (e.key === 'Enter' || e.key === 'y' || e.key === 'Y') {
                e.preventDefault();
                handleKeyboardApproval(currentStage, 'approve');
            } else if (e.key === 'Escape' || e.key === 'n' || e.key === 'N') {
                e.preventDefault();
                handleKeyboardApproval(currentStage, 'reject');
            }
            
            // Stage-specific shortcuts
            switch(currentStage) {
                case 'triage':
                    if (e.key === '1') {
                        e.preventDefault();
                        handleKeyboardApproval('triage', 'approve');
                    } else if (e.key === '2') {
                        e.preventDefault();
                        handleKeyboardApproval('triage', 'reject');
                    }
                    break;
                    
                case 'context':
                    if (e.key === '1') {
                        e.preventDefault();
                        handleKeyboardApproval('context', 'approve');
                    } else if (e.key === '2') {
                        e.preventDefault();
                        handleKeyboardApproval('context', 'reject');
                    } else if (e.key === '3') {
                        e.preventDefault();
                        handleKeyboardApproval('context', 'custom');
                    }
                    break;
                    
                case 'analyst':
                    if (e.key === '1') {
                        e.preventDefault();
                        handleKeyboardApproval('analyst', 'approve');
                    } else if (e.key === '2') {
                        e.preventDefault();
                        handleKeyboardApproval('analyst', 'reject');
                    } else if (e.key === '3') {
                        e.preventDefault();
                        handleKeyboardApproval('analyst', 'custom');
                    }
                    break;
            }
        }
    });
    
    // Handle clicks outside approval buttons (for accessibility)
    document.addEventListener('click', function(e) {
        // If user clicks outside approval section while awaiting approval, show hint
        if (approvalWorkflow.getAwaitingApproval() && 
            !e.target.closest('.approval-section') && 
            !e.target.closest('.debug-btn')) {
            
            const currentStage = approvalWorkflow.getCurrentApprovalStage();
            if (currentStage) {
                ui.showStatus(`Please respond to the ${currentStage} approval request`, 'info');
            }
        }
    });
    
    // Initialize UI
    ui.resetAgentStates();
    
    // Enhanced welcome message
    ui.showStatus('Welcome to Enhanced SOC Dashboard with Multi-Stage Approval!', 'info');
    
    // Show enhanced keyboard shortcuts in console
    setTimeout(function() {
        console.log('🚀 Enhanced SOC Dashboard Shortcuts:');
        console.log('  Global Controls:');
        console.log('    • Ctrl+Shift+D → Toggle debug mode');
        console.log('    • Ctrl+Shift+A → Start analysis');
        console.log('    • Ctrl+Shift+C → Clear results');
        console.log('  ');
        console.log('  Multi-Stage Approval (when active):');
        console.log('    • Enter/Y → Approve current stage');
        console.log('    • Escape/N → Reject current stage');
        console.log('    • Tab → Navigate between buttons');
        console.log('  ');
        console.log('  Stage-Specific Shortcuts:');
        console.log('    Triage: 1=Approve, 2=Reject');
        console.log('    Context: 1=Relevant, 2=Not Relevant, 3=Custom');
        console.log('    Analyst: 1=Approve All, 2=Reject, 3=Modify');
        
        debugLogger.debugLog('Enhanced WebSocket dashboard with multi-stage approval initialized');
    }, 2000);
    
    // Add visual feedback for keyboard shortcuts
    createKeyboardShortcutHelp();
});

function handleKeyboardApproval(stage, action) {
    if (!stage) {
        debugLogger.debugLog('No current stage for keyboard approval', 'WARNING');
        return;
    }
    
    debugLogger.debugLog(`Keyboard approval: ${stage} - ${action}`);
    
    // Find the appropriate button and click it - UPDATED SELECTOR
    const buttonSelector = `#${stage}ApprovalSection .btn[data-value="${action}"]`;
    const button = document.querySelector(buttonSelector);
    
    if (button) {
        // Add visual feedback
        button.classList.add('keyboard-activated');
        setTimeout(() => button.classList.remove('keyboard-activated'), 200);
        
        // Trigger the click
        button.click();
        ui.showStatus(`${stage.charAt(0).toUpperCase() + stage.slice(1)} ${action} via keyboard`, 'success');
    } else {
        debugLogger.debugLog(`Button not found for keyboard approval: ${buttonSelector}`, 'WARNING');
        
        // Fallback to direct function calls
        if (action === 'approve') {
            approvalWorkflow.approveAnalysis();
        } else if (action === 'reject') {
            approvalWorkflow.rejectAnalysis();
        }
    }
}

function createKeyboardShortcutHelp() {
    // Create floating help tooltip
    const helpButton = document.createElement('div');
    helpButton.id = 'keyboardHelpButton';
    helpButton.innerHTML = '⌨️';
    helpButton.style.cssText = `
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
    `;
    
    helpButton.addEventListener('mouseenter', function() {
        this.style.opacity = '1';
        this.style.transform = 'scale(1.1)';
    });
    
    helpButton.addEventListener('mouseleave', function() {
        this.style.opacity = '0.8';
        this.style.transform = 'scale(1)';
    });
    
    helpButton.addEventListener('click', function() {
        showKeyboardShortcutModal();
    });
    
    document.body.appendChild(helpButton);
}

function showKeyboardShortcutModal() {
    // Create modal for keyboard shortcuts
    const modal = document.createElement('div');
    modal.id = 'keyboardShortcutModal';
    modal.style.cssText = `
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
    `;
    
    const modalContent = document.createElement('div');
    modalContent.style.cssText = `
        background: white;
        padding: 30px;
        border-radius: 12px;
        max-width: 500px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    `;
    
    modalContent.innerHTML = `
        <h3 style="margin-bottom: 20px; color: #2c3e50;">⌨️ Keyboard Shortcuts</h3>
        
        <div style="margin-bottom: 20px;">
            <h4 style="color: #667eea; margin-bottom: 10px;">Global Controls</h4>
            <div style="font-family: monospace; font-size: 14px; line-height: 1.6;">
                <div><strong>Ctrl+Shift+D</strong> → Toggle debug mode</div>
                <div><strong>Ctrl+Shift+A</strong> → Start analysis</div>
                <div><strong>Ctrl+Shift+C</strong> → Clear results</div>
            </div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <h4 style="color: #4ecdc4; margin-bottom: 10px;">Multi-Stage Approval</h4>
            <div style="font-family: monospace; font-size: 14px; line-height: 1.6;">
                <div><strong>Enter/Y</strong> → Approve current stage</div>
                <div><strong>Escape/N</strong> → Reject current stage</div>
                <div><strong>Tab</strong> → Navigate between buttons</div>
            </div>
        </div>
        
        <div style="margin-bottom: 20px;">
            <h4 style="color: #a8e6cf; margin-bottom: 10px;">Stage-Specific</h4>
            <div style="font-family: monospace; font-size: 14px; line-height: 1.6;">
                <div><strong>Triage:</strong> 1=Approve, 2=Reject</div>
                <div><strong>Context:</strong> 1=Relevant, 2=Not Relevant, 3=Custom</div>
                <div><strong>Analyst:</strong> 1=Approve All, 2=Reject, 3=Modify</div>
            </div>
        </div>
        
        <button id="closeShortcutModal" style="
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            width: 100%;
            margin-top: 20px;
        ">Close</button>
    `;
    
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // Close modal handlers
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
    
    document.getElementById('closeShortcutModal').addEventListener('click', function() {
        document.body.removeChild(modal);
    });
    
    // Close with Escape key
    const closeOnEscape = function(e) {
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', closeOnEscape);
        }
    };
    document.addEventListener('keydown', closeOnEscape);
}

// Add CSS for keyboard activation feedback
const style = document.createElement('style');
style.textContent = `
    .keyboard-activated {
        transform: scale(0.95) !important;
        background: linear-gradient(45deg, #56ab2f, #a8e6cf) !important;
        box-shadow: 0 0 20px rgba(86, 171, 47, 0.6) !important;
    }
    
    .btn:focus-visible {
        outline: 3px solid #667eea !important;
        outline-offset: 2px !important;
    }
    
    #keyboardHelpButton:hover {
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4) !important;
    }
`;
document.head.appendChild(style);