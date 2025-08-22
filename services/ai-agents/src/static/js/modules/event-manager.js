// services/ai-agents/src/static/js/modules/event-manager.js
// Centralized event management

import * as debugLogger from '../debugLogger.js';
import * as ui from '../ui.js';
import * as progressManager from '../progressManager.js';
import * as approvalWorkflow from '../approvalWorkflow.js';

export class EventManager {
    constructor() {
        this.eventListeners = new Map();
    }

    async initialize() {
        debugLogger.debugLog('Setting up event listeners...');
        
        // Main control buttons
        this.addListener('retrieveBtn', 'click', progressManager.retrieveLogs);
        this.addListener('analyzeBtn', 'click', progressManager.startAnalysis);
        this.addListener('clearBtn', 'click', this.handleClearResults);
        
        // Debug controls
        this.addListener('debugToggle', 'click', debugLogger.toggleDebugMode);
        this.setupDebugControls();
        
        // Input monitoring
        this.addListener('logInput', 'input', this.handleLogInputChange);
        
        // Global click handler for approval hints
        this.addListener(document, 'click', this.handleGlobalClick);
        
        debugLogger.debugLog('Event listeners configured');
    }

    addListener(elementOrId, event, handler) {
        const element = typeof elementOrId === 'string' 
            ? document.getElementById(elementOrId) 
            : elementOrId;
            
        if (!element) {
            debugLogger.debugLog(`Element not found: ${elementOrId}`, 'WARNING');
            return;
        }

        element.addEventListener(event, handler);
        
        // Store for cleanup if needed
        const key = `${element.id || 'document'}_${event}`;
        this.eventListeners.set(key, { element, event, handler });
    }

    setupDebugControls() {
        const debugActions = {
            'clearDebugLog': debugLogger.clearDebugLog,
            'exportDebugLog': debugLogger.exportDebugLog,
            'showWebSocketStats': () => import('../websocket.js').then(ws => ws.showWebSocketStats()),
            'testConnection': () => import('../websocket.js').then(ws => ws.testConnection())
        };

        document.querySelectorAll('.debug-btn[data-action]').forEach(button => {
            const action = button.getAttribute('data-action');
            if (debugActions[action]) {
                this.addListener(button, 'click', debugActions[action]);
            }
        });
    }

    handleClearResults = () => {
        ui.clearResults();
        approvalWorkflow.hideAllApprovalButtons();
        debugLogger.debugLog('Results cleared via event manager');
    }

    handleLogInputChange = (event) => {
        progressManager.updateLogCounter(event.target.value);
    }

    handleGlobalClick = (event) => {
        // Show approval hint if user clicks outside approval area
        if (approvalWorkflow.getAwaitingApproval() && 
            !event.target.closest('.approval-section') && 
            !event.target.closest('.debug-btn')) {
            
            const currentStage = approvalWorkflow.getCurrentApprovalStage();
            if (currentStage) {
                ui.showStatus(`Please respond to the ${currentStage} approval request`, 'info');
            }
        }
    }

    cleanup() {
        // Remove all event listeners if needed
        this.eventListeners.forEach(({ element, event, handler }) => {
            element.removeEventListener(event, handler);
        });
        this.eventListeners.clear();
    }
}