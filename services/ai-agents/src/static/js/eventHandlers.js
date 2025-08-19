// Event Handlers - Simplified version
// Most event handling has been moved to main.js
// This file is kept for legacy compatibility but most functions have been moved

import * as debugLogger from './debugLogger.js';

// This file is now mostly empty as event handling has been moved to main.js
// and individual modules handle their own functionality

// Legacy function kept for compatibility
function initialize() {
    debugLogger.debugLog('Event handlers module loaded (legacy compatibility)');
}

export { initialize };