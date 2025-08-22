// services/ai-agents/src/static/js/modules/ui-helper.js
// UI helper utilities and initialization

import * as ui from '../ui.js';
import * as debugLogger from '../debugLogger.js';

export class UIHelper {
    constructor() {
        this.initialized = false;
    }

    initialize() {
        if (this.initialized) return;
        
        this.setupUIComponents();
        this.resetInitialState();
        
        this.initialized = true;
        debugLogger.debugLog('UI Helper initialized');
    }

    setupUIComponents() {
        // Ensure all required UI elements exist
        this.ensureToastContainer();
        this.setupLogCounter();
        this.validateRequiredElements();
    }

    ensureToastContainer() {
        if (!document.getElementById('toast-container')) {
            const container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
    }

    setupLogCounter() {
        const logCounter = document.getElementById('logCounter');
        if (logCounter && !logCounter.textContent) {
            logCounter.textContent = '0 events';
        }
    }

    validateRequiredElements() {
        const requiredElements = [
            'retrieveBtn',
            'analyzeBtn', 
            'clearBtn',
            'logInput',
            'progressBar',
            'progressText',
            'triageCard',
            'contextCard',
            'analystCard'
        ];

        const missing = requiredElements.filter(id => !document.getElementById(id));
        
        if (missing.length > 0) {
            debugLogger.debugLog(`Missing UI elements: ${missing.join(', ')}`, 'WARNING');
        }
    }

    resetInitialState() {
        // Reset agent states
        ui.resetAgentStates();
        
        // Reset progress
        ui.updateProgress(0, 'Ready');
        
        // Ensure analyze button is enabled
        const analyzeBtn = document.getElementById('analyzeBtn');
        if (analyzeBtn) {
            analyzeBtn.disabled = false;
        }
    }

    showWelcomeMessage() {
        ui.showStatus('Welcome to Refactored SOC Dashboard! 🚀', 'info');
        
        setTimeout(() => {
            ui.showStatus('Dashboard components loaded and ready', 'success');
        }, 1000);
    }

    // Utility methods for common UI operations
    
    showLoadingState(element, message = 'Loading...') {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (element) {
            element.disabled = true;
            const originalText = element.textContent;
            element.textContent = message;
            element.dataset.originalText = originalText;
        }
    }

    hideLoadingState(element) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        
        if (element) {
            element.disabled = false;
            if (element.dataset.originalText) {
                element.textContent = element.dataset.originalText;
                delete element.dataset.originalText;
            }
        }
    }

    highlightElement(elementId, duration = 2000) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.classList.add('highlight');
        
        setTimeout(() => {
            element.classList.remove('highlight');
        }, duration);
    }

    scrollToElement(elementId, behavior = 'smooth') {
        const element = document.getElementById(elementId);
        if (element) {
            element.scrollIntoView({ behavior });
        }
    }

    updateElementContent(elementId, content, type = 'text') {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        if (type === 'html') {
            element.innerHTML = content;
        } else {
            element.textContent = content;
        }
    }

    toggleElementVisibility(elementId, visible = null) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        if (visible === null) {
            // Toggle current state
            visible = element.style.display === 'none';
        }
        
        element.style.display = visible ? 'block' : 'none';
    }

    addTemporaryClass(elementId, className, duration = 3000) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.classList.add(className);
        
        setTimeout(() => {
            element.classList.remove(className);
        }, duration);
    }

    // Responsive utilities
    
    isMobile() {
        return window.innerWidth <= 768;
    }

    isTablet() {
        return window.innerWidth > 768 && window.innerWidth <= 1024;
    }

    isDesktop() {
        return window.innerWidth > 1024;
    }

    // Accessibility helpers
    
    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.style.position = 'absolute';
        announcement.style.left = '-10000px';
        announcement.style.width = '1px';
        announcement.style.height = '1px';
        announcement.style.overflow = 'hidden';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }

    focusElement(elementId) {
        const element = document.getElementById(elementId);
        if (element && typeof element.focus === 'function') {
            element.focus();
        }
    }
}