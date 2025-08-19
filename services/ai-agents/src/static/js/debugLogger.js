// Debug Mode Functions
var debugMode = false;
var debugMessages = [];

function toggleDebugMode() {
    debugMode = !debugMode;
    var toggle = document.getElementById('debugToggle');
    var panel = document.getElementById('debugPanel');
    
    if (debugMode) {
        toggle.textContent = '🔧 Debug ON';
        toggle.classList.add('debug-mode');
        panel.style.display = 'block';
        debugLog('Debug mode enabled');
        // Use dynamic import to avoid circular dependency
        import('./ui.js').then(ui => {
            ui.showStatus('Debug mode enabled - detailed WebSocket logging active', 'info');
        });
    } else {
        toggle.textContent = '🔧 Debug Mode';
        toggle.classList.remove('debug-mode');
        panel.style.display = 'none';
        import('./ui.js').then(ui => {
            ui.showStatus('Debug mode disabled', 'info');
        });
    }
}

function debugLog(message, level) {
    if (typeof level == 'undefined') level = 'INFO';
    if (!debugMode) return;
    
    var timestamp = new Date().toISOString();
    var logEntry = '[' + timestamp + '] [' + level + '] ' + message;
    debugMessages.push(logEntry);
    
    var debugLogElement = document.getElementById('debugLog');
    if (debugLogElement) {
        debugLogElement.textContent = debugMessages.slice(-100).join('\n');
        debugLogElement.scrollTop = debugLogElement.scrollHeight;
    }
    
    console.log(logEntry);
}

function clearDebugLog() {
    debugMessages = [];
    var debugLogElement = document.getElementById('debugLog');
    if (debugLogElement) {
        debugLogElement.textContent = 'Debug log cleared.';
    }
}

function exportDebugLog() {
    var blob = new Blob([debugMessages.join('\n')], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'soc-websocket-debug-' + new Date().toISOString().slice(0, 19) + '.log';
    a.click();
    URL.revokeObjectURL(url);
    debugLog('Debug log exported');
}

function getDebugMode() {
    return debugMode;
}

function getDebugMessages() {
    return debugMessages;
}

export { 
    debugLog, 
    toggleDebugMode, 
    clearDebugLog, 
    exportDebugLog, 
    getDebugMode, 
    getDebugMessages 
};