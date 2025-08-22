// services/ai-agents/src/static/js/main.js - REFACTORED VERSION
// Simplified main controller - delegates to specialized modules

import { EventManager } from './modules/event-manager.js';
import { KeyboardManager } from './modules/keyboard-manager.js';
import { UIHelper } from './modules/ui-helper.js';
import * as debugLogger from './debugLogger.js';
import * as websocket from './websocket.js';

class Dashboard {
    constructor() {
        this.eventManager = new EventManager();
        this.keyboardManager = new KeyboardManager();
        this.uiHelper = new UIHelper();
        this.initialized = false;
    }

    async initialize() {
        if (this.initialized) return;
        
        debugLogger.debugLog('Initializing SOC Dashboard...');
        
        // Initialize components
        await this.eventManager.initialize();
        this.keyboardManager.initialize();
        this.uiHelper.initialize();
        
        // Initialize WebSocket
        websocket.initWebSocket();
        
        // Show welcome message
        this.uiHelper.showWelcomeMessage();
        
        this.initialized = true;
        debugLogger.debugLog('SOC Dashboard initialized successfully');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
    const dashboard = new Dashboard();
    await dashboard.initialize();
});