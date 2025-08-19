import * as debugLogger from './debugLogger.js?v=2';

// UI Update Helpers and DOM Manipulation

function showStatus(message, type) {
    var toastContainer = getOrCreateToastContainer();
    var toast = createToast(message, type);
    toastContainer.appendChild(toast);

    setTimeout(function() {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 5000);

    debugLogger.debugLog('Status: ' + message, type.toUpperCase());
    console.log('[' + type.toUpperCase() + '] ' + message);
}

function getOrCreateToastContainer() {
    var container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    return container;
}

function createToast(message, type) {
    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    return toast;
}

function updateAgentStatus(agent, status) {
    var element = document.getElementById(agent + 'Status');
    if (!element) return;
    
    element.className = 'status-badge status-' + status;

    var statusText = status.charAt(0).toUpperCase() + status.slice(1);
    if (status === 'awaiting-approval') {
        statusText = 'Awaiting Approval';
    } else if (status === 'rejected') {
        statusText = 'Rejected';
    }

    element.textContent = statusText;
    debugLogger.debugLog('Agent ' + agent + ' status updated to: ' + status);
}

function showAgentOutput(agent, text) {
    var element = document.getElementById(agent + 'Output');
    if (element) {
        element.textContent = text;
        debugLogger.debugLog('Agent ' + agent + ' output updated');
    }
}

function showAgentSpinner(agent, show) {
    var spinner = document.getElementById(agent + 'Spinner');
    var output = document.getElementById(agent + 'Output');

    if (spinner && output) {
        if (show) {
            spinner.style.display = 'flex';
            output.style.opacity = '0.3';
        } else {
            spinner.style.display = 'none';
            output.style.opacity = '1';
        }
    }
}

function updateProgress(percent, statusText) {
    var progressBar = document.getElementById('progressBar');
    var progressTextElement = document.getElementById('progressText');
    
    if (progressBar) {
        progressBar.style.width = percent + '%';
    }
    
    if (progressTextElement) {
        if (statusText) {
            progressTextElement.textContent = statusText;
        } else {
            progressTextElement.textContent = percent > 0 ? percent + '%' : 'Ready';
        }
    }
}

function resetAgentStates() {
    debugLogger.debugLog('Resetting all agent states');
    var agents = ['triage', 'context', 'analyst'];
    var outputTexts = {
        triage: 'Waiting for analysis to begin...',
        context: 'Waiting for triage completion and approval...',
        analyst: 'Waiting for context research...'
    };

    for (var i = 0; i < agents.length; i++) {
        var agent = agents[i];
        updateAgentStatus(agent, 'pending');
        showAgentSpinner(agent, false);
        var card = document.getElementById(agent + 'Card');
        if (card) {
            card.classList.remove('active');
        }
        showAgentOutput(agent, outputTexts[agent]);
    }
}

function hideFindings() {
    var panel = document.getElementById('findingsPanel');
    if (panel) {
        panel.style.display = 'none';
    }
}

function clearResults() {
    debugLogger.debugLog('Clearing all results and resetting dashboard');
    
    var logInput = document.getElementById('logInput');
    var logCounter = document.getElementById('logCounter');
    var analyzeBtn = document.getElementById('analyzeBtn');
    
    if (logInput) logInput.value = '';
    if (logCounter) logCounter.textContent = '0 events';
    
    resetAgentStates();
    hideFindings();
    
    // Hide approval buttons by importing approvalWorkflow dynamically to avoid circular dependency
    import('./approvalWorkflow.js').then(approvalWorkflow => {
        approvalWorkflow.hideApprovalButtons();
    });
    
    updateProgress(0, 'Ready');
    
    // Reset analysis state by importing progressManager dynamically
    import('./progressManager.js').then(progressManager => {
        progressManager.setAnalysisInProgress(false);
    });
    
    if (analyzeBtn) analyzeBtn.disabled = false;

    showStatus('Dashboard cleared and reset', 'info');
}

function displayFinalResults(results) {
    debugLogger.debugLog('Displaying final analysis results');
    var panel = document.getElementById('findingsPanel');
    var content = document.getElementById('findingsContent');
    
    if (!panel || !content) return;

    // Extract priority from structured findings
    var priority = 'medium';
    if (results.structured_findings && results.structured_findings.priority_threat) {
        var threatPriority = results.structured_findings.priority_threat.priority;
        if (threatPriority) {
            priority = threatPriority.toLowerCase();
        }
    }

    // Set priority indicator
    var priorityElement = document.getElementById('priorityIndicator');
    if (priorityElement) {
        priorityElement.textContent = priority.toUpperCase();
        priorityElement.className = 'priority-indicator priority-' + priority;
    }

    // Create findings cards from structured data
    var findings = [];

    if (results.structured_findings && results.structured_findings.priority_threat) {
        var threat = results.structured_findings.priority_threat;
        findings.push({
            title: '🚨 Priority Threat',
            content: (threat.threat_type || 'Unknown threat') + ' detected from ' +
                (threat.source_ip || 'unknown source') + '. ' +
                (threat.brief_summary || 'No summary available.')
        });
        debugLogger.debugLog('Priority threat identified: ' + threat.threat_type + ' from ' + threat.source_ip);
    }

    if (results.chroma_context && !results.chroma_context.error) {
        var contextCount = results.chroma_context.documents ? results.chroma_context.documents.length : 0;
        findings.push({
            title: '📚 Historical Context',
            content: 'Found ' + contextCount + ' related historical incidents to provide context for this analysis.'
        });
        debugLogger.debugLog('Historical context found: ' + contextCount + ' related incidents');
    }

    if (results.structured_findings && results.structured_findings.detailed_analysis) {
        var analysis = results.structured_findings.detailed_analysis;
        var actionCount = analysis.recommended_actions ? analysis.recommended_actions.length : 0;
        findings.push({
            title: '🎯 Analysis Complete',
            content: 'Deep analysis completed with ' + actionCount + ' recommended actions. Business impact: ' +
                (analysis.business_impact || 'Under assessment') + '.'
        });
        debugLogger.debugLog('Detailed analysis completed: ' + actionCount + ' recommendations');
    }

    // Fallback if no structured findings
    if (findings.length == 0) {
        findings.push({
            title: '✅ Analysis Complete',
            content: 'Multi-agent analysis completed successfully. Check individual agent outputs above for detailed findings and recommendations.'
        });
    }

    content.innerHTML = findings.map(function(finding) {
        return '<div class="finding-card">' +
            '<h4>' + finding.title + '</h4>' +
            '<p>' + finding.content + '</p>' +
            '</div>';
    }).join('');

    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth' });
    debugLogger.debugLog('Final results panel displayed');
}

export { 
    showStatus, 
    updateAgentStatus, 
    showAgentOutput, 
    showAgentSpinner, 
    updateProgress, 
    resetAgentStates,
    hideFindings, 
    clearResults, 
    displayFinalResults 
};