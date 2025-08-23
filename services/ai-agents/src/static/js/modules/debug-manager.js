// services/ai-agents/src/static/js/modules/debug-manager.js - ENHANCED WITH CONTEXT DEBUGGING
export class DebugManager {
    constructor() {
        this.debugMode = false;
        this.logs = [];
        this.maxLogs = 1000;
    }

    async initialize() {
        this.setupDebugPanel();
        console.log('✅ Debug Manager initialized with enhanced context debugging');
    }

    // ============================================================================
    // DEBUG MODE CONTROL
    // ============================================================================

    toggle() {
        this.debugMode = !this.debugMode;
        this.updateDebugUI();
        
        if (this.debugMode) {
            this.log('Debug mode enabled - Context data debugging active');
            console.log('🔧 Debug mode ON - Enhanced context logging enabled');
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
    // ENHANCED LOGGING WITH CONTEXT SUPPORT
    // ============================================================================

    log(message, level = 'INFO', context = null) {
        if (!this.debugMode && level !== 'ERROR') return;
        
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            context,
            formatted: context ? 
                `[${timestamp}] [${level}] ${message}\nContext: ${JSON.stringify(context, null, 2)}` :
                `[${timestamp}] [${level}] ${message}`
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
        if (context) {
            console[consoleMethod](logEntry.formatted.split('\nContext:')[0]);
            console[consoleMethod]('Context:', context);
        } else {
            console[consoleMethod](logEntry.formatted);
        }
    }

    // Special method for context data debugging
    logContextData(contextData, stage = 'unknown') {
        this.log(`Context data received for ${stage} stage`, 'INFO', {
            stage,
            available_fields: Object.keys(contextData),
            field_details: this.analyzeContextFields(contextData)
        });
    }

    analyzeContextFields(data) {
        const analysis = {};
        for (const [key, value] of Object.entries(data)) {
            analysis[key] = {
                type: Array.isArray(value) ? 'array' : typeof value,
                length: Array.isArray(value) ? value.length : 
                       typeof value === 'string' ? value.length : 
                       typeof value === 'object' && value !== null ? Object.keys(value).length : null,
                hasContent: Boolean(value && (
                    (Array.isArray(value) && value.length > 0) ||
                    (typeof value === 'string' && value.trim().length > 0) ||
                    (typeof value === 'object' && value !== null && Object.keys(value).length > 0) ||
                    (typeof value !== 'object' && value !== null && value !== undefined)
                )),
                sample: Array.isArray(value) && value.length > 0 ? value[0] :
                       typeof value === 'string' ? value.substring(0, 50) + (value.length > 50 ? '...' : '') :
                       value
            };
        }
        return analysis;
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
            debugLog.textContent = 'Enhanced debug mode disabled. Click "Debug Mode" to enable context data logging.';
        }
    }

    // ============================================================================
    // CONVENIENCE METHODS
    // ============================================================================

    info(message, context = null) {
        this.log(message, 'INFO', context);
    }

    warn(message, context = null) {
        this.log(message, 'WARNING', context);
    }

    error(message, context = null) {
        this.log(message, 'ERROR', context);
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
            newestLog: this.logs[this.logs.length - 1]?.timestamp,
            contextLogs: this.logs.filter(log => log.context).length
        };
    }

    getLogs(level = null, count = 100) {
        let logs = this.logs;
        
        if (level) {
            logs = logs.filter(log => log.level === level);
        }
        
        return logs.slice(-count);
    }

    // Get context-specific logs
    getContextLogs(count = 50) {
        return this.logs
            .filter(log => log.context)
            .slice(-count);
    }
}