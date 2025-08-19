// main.js - Event listener approach (recommended)
import * as debugLogger from './debugLogger.js';
import * as ui from './ui.js';
import * as websocket from './websocket.js';
import * as approvalWorkflow from './approvalWorkflow.js';
import * as progressManager from './progressManager.js';

// Set up event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    debugLogger.debugLog('Page loaded, setting up event listeners...');
    
    // Main control buttons
    document.getElementById('retrieveBtn').addEventListener('click', progressManager.retrieveLogs);
    document.getElementById('analyzeBtn').addEventListener('click', progressManager.startAnalysis);
    
    // Clear results button
    document.getElementById('clearBtn')?.addEventListener('click', function() {
        ui.clearResults();
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
    
    // Set up keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            debugLogger.toggleDebugMode();
        }
        
        if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            e.preventDefault();
            ui.clearResults();
        }
        
        if (e.ctrlKey && e.shiftKey && e.key === 'A') {
            e.preventDefault();
            if (!progressManager.getAnalysisInProgress()) {
                progressManager.startAnalysis();
            }
        }
        
        // Approval shortcuts when waiting
        if (approvalWorkflow.getAwaitingApproval()) {
            if (e.key === 'Enter' || e.key === 'y' || e.key === 'Y') {
                e.preventDefault();
                approvalWorkflow.approveAnalysis();
            } else if (e.key === 'Escape' || e.key === 'n' || e.key === 'N') {
                e.preventDefault();
                approvalWorkflow.rejectAnalysis();
            }
        }
    });
    
    // Initialize UI
    ui.resetAgentStates();
    
    // Welcome message
    ui.showStatus('Welcome to SOC Agent Dashboard with Approval Workflow!', 'info');
    
    // Show keyboard shortcuts in console
    setTimeout(function() {
        console.log('💡 SOC Dashboard Shortcuts:');
        console.log('  • Ctrl+Shift+D → Toggle debug mode');
        console.log('  • Ctrl+Shift+A → Start analysis');
        console.log('  • Ctrl+Shift+C → Clear results');
        console.log('  • When approval requested:');
        console.log('    - Enter/Y → Approve');
        console.log('    - Escape/N → Reject');
        debugLogger.debugLog('WebSocket dashboard with approval workflow initialized');
    }, 2000);
});