// services/ai-agents/src/static/js/modules/debug-manager.js - COMPLETE FIXED FILE
// Handles debug logging and debug mode

export class DebugManager {
    constructor() {
        this.debugMode = false;
        this.logs = [];
        this.maxLogs = 1000;
    }

    async initialize() {
        this.setupDebugPanel();
        console.log('✅ Debug Manager initialized');
    }

    // ============================================================================
    // DEBUG MODE CONTROL
    // ============================================================================

    toggle() {
        this.debugMode = !this.debugMode;
        this.updateDebugUI();
        
        if (this.debugMode) {
            this.log('Debug mode enabled');
            console.log('🔧 Debug mode ON');
        } else {
            console.log('🔧 Debug mode OFF');
        }
    }

    updateDebugUI() {
        const toggle = document.getElementById('debugToggle');
        const panel = document.getElementById('debugPanel');
        
        if (toggle) {
            toggle.textContent = this.debugMode ? '🔧 Debug ON' : '🔧 Debug Mode';
            toggle.classList.toggle('debug-mode', this.debugMode);
        }
        
        if (panel) {
            panel.style.display = this.debugMode ? 'block' : 'none';
        }
    }

    // ============================================================================
    // LOGGING
    // ============================================================================

    log(message, level = 'INFO') {
        if (!this.debugMode && level !== 'ERROR') return;
        
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            formatted: `[${timestamp}] [${level}] ${message}`
        };
        
        this.logs.push(logEntry);
        
        // Keep only recent logs
        if (this.logs.length > this.maxLogs) {
            this.logs = this.logs.slice(-this.maxLogs);
        }
        
        this.updateDebugDisplay();
        
        // Also log to console
        const consoleMethod = level === 'ERROR' ? 'error' : 
                             level === 'WARNING' ? 'warn' : 'log';
        console[consoleMethod](logEntry.formatted);
    }

    updateDebugDisplay() {
        const debugLogElement = document.getElementById('debugLog');
        if (!debugLogElement) return;
        
        const recentLogs = this.logs.slice(-100); // Show last 100 logs
        debugLogElement.textContent = recentLogs
            .map(log => log.formatted)
            .join('\n');
        
        // Auto-scroll to bottom
        debugLogElement.scrollTop = debugLogElement.scrollHeight;
    }

    // ============================================================================
    // LOG MANAGEMENT
    // ============================================================================

    clearLog() {
        this.logs = [];
        this.updateDebugDisplay();
        this.log('Debug log cleared');
    }

    exportLog() {
        const logText = this.logs
            .map(log => log.formatted)
            .join('\n');
        
        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `soc-debug-${new Date().toISOString().slice(0, 19)}.log`;
        a.click();
        
        URL.revokeObjectURL(url);
        this.log('Debug log exported');
    }

    // ============================================================================
    // SETUP
    // ============================================================================

    setupDebugPanel() {
        // Ensure debug panel exists
        const panel = document.getElementById('debugPanel');
        if (!panel) {
            console.warn('Debug panel not found in DOM');
            return;
        }

        // Set initial state
        panel.style.display = 'none';
        
        // Ensure debug log element exists
        const debugLog = document.getElementById('debugLog');
        if (debugLog && !debugLog.textContent.trim()) {
            debugLog.textContent = 'Debug mode disabled. Click "Debug Mode" to enable logging.';
        }
    }

    // ============================================================================
    // CONVENIENCE METHODS
    // ============================================================================

    info(message) {
        this.log(message, 'INFO');
    }

    warn(message) {
        this.log(message, 'WARNING');
    }

    error(message) {
        this.log(message, 'ERROR');
    }

    // ============================================================================
    // STATS AND UTILITIES
    // ============================================================================

    getStats() {
        return {
            debugMode: this.debugMode,
            totalLogs: this.logs.length,
            logLevels: this.logs.reduce((acc, log) => {
                acc[log.level] = (acc[log.level] || 0) + 1;
                return acc;
            }, {}),
            oldestLog: this.logs[0]?.timestamp,
            newestLog: this.logs[this.logs.length - 1]?.timestamp
        };
    }

    getLogs(level = null, count = 100) {
        let logs = this.logs;
        
        if (level) {
            logs = logs.filter(log => log.level === level);
        }
        
        return logs.slice(-count);
    }
}