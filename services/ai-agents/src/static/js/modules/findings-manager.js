// services/ai-agents/src/static/js/modules/findings-manager.js
// Dedicated module for managing the findings/results panel

export class FindingsManager {
    constructor() {
        this.panel = null;
        this.content = null;
        this.currentResults = {
            triage: null,
            context: null,
            analyst: null
        };
    }

    async initialize() {
        this.panel = document.getElementById('findingsPanel');
        this.content = document.getElementById('findingsContent');
        
        if (!this.panel || !this.content) {
            console.warn('⚠️ Findings panel elements not found in DOM');
            return false;
        }

        console.log('✅ Findings Manager initialized');
        return true;
    }

    // ============================================================================
    // RESULTS STORAGE
    // ============================================================================

    storeTriageResults(data) {
        this.currentResults.triage = data;
        console.log('💾 Stored triage results');
    }

    storeContextResults(data) {
        this.currentResults.context = data;
        console.log('💾 Stored context results');
    }

    storeAnalystResults(data) {
        this.currentResults.analyst = data;
        console.log('💾 Stored analyst results');
    }

    clearResults() {
        this.currentResults = {
            triage: null,
            context: null,
            analyst: null
        };
        console.log('🧹 Cleared stored results');
    }

    // ============================================================================
    // PANEL DISPLAY
    // ============================================================================

    /**
     * Show and populate the findings panel with consolidated results
     */
    showPanel() {
        if (!this.panel || !this.content) {
            console.error('❌ Findings panel not initialized');
            return false;
        }

        try {
            // Clear previous content
            this.content.innerHTML = '';

            // Create consolidated findings display
            const findingsHTML = this.createFindingsHTML();
            this.content.innerHTML = findingsHTML;

            // Show the panel with smooth animation
            this.panel.style.display = 'block';
            
            // Scroll to panel after a brief delay to ensure it's rendered
            setTimeout(() => {
                this.panel.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'start' 
                });
            }, 100);

            console.log('✅ Findings panel displayed with consolidated results');
            return true;

        } catch (error) {
            console.error('❌ Error displaying findings panel:', error);
            return false;
        }
    }

    /**
     * Hide the findings panel
     */
    hidePanel() {
        if (this.panel) {
            this.panel.style.display = 'none';
            console.log('📤 Findings panel hidden');
        }
    }

    // ============================================================================
    // HTML GENERATION
    // ============================================================================

    /**
     * Create comprehensive HTML for the findings panel
     */
    createFindingsHTML() {
        const { triage, context, analyst } = this.currentResults;
        
        return `
            <div class="findings-summary">
                ${this.createThreatSection(triage)}
                ${this.createContextSection(context)}
                ${this.createRecommendationsSection(analyst)}
                ${this.createSummarySection()}
            </div>
        `;
    }

    createThreatSection(triage) {
        return `
            <div class="finding-section threat-section">
                <h4>🚨 Threat Assessment</h4>
                <div class="finding-content">
                    <div class="finding-grid">
                        <div class="finding-item">
                            <span class="finding-label">Priority:</span>
                            <span class="finding-value priority-${triage?.priority?.toLowerCase() || 'unknown'}">
                                ${triage?.priority?.toUpperCase() || 'UNKNOWN'}
                            </span>
                        </div>
                        <div class="finding-item">
                            <span class="finding-label">Threat Type:</span>
                            <span class="finding-value">${triage?.threat_type || 'Unknown'}</span>
                        </div>
                        <div class="finding-item">
                            <span class="finding-label">Source IP:</span>
                            <span class="finding-value source-ip">${triage?.source_ip || 'Unknown'}</span>
                        </div>
                        <div class="finding-item">
                            <span class="finding-label">Confidence:</span>
                            <span class="finding-value confidence">
                                ${((triage?.confidence_score || 0) * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>
                    ${triage?.brief_summary ? `
                        <div class="finding-summary">
                            <strong>Summary:</strong> ${triage.brief_summary}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    createContextSection(context) {
        return `
            <div class="finding-section context-section">
                <h4>📚 Historical Context</h4>
                <div class="finding-content">
                    <div class="finding-grid">
                        <div class="finding-item">
                            <span class="finding-label">Documents Analyzed:</span>
                            <span class="finding-value">${context?.total_documents_found || 0}</span>
                        </div>
                        <div class="finding-item">
                            <span class="finding-label">Confidence Level:</span>
                            <span class="finding-value confidence-${context?.confidence_assessment?.toLowerCase() || 'medium'}">
                                ${context?.confidence_assessment || 'Medium'}
                            </span>
                        </div>
                    </div>
                    ${context?.pattern_analysis ? `
                        <div class="finding-summary">
                            <strong>Pattern Analysis:</strong> ${context.pattern_analysis}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    createRecommendationsSection(analyst) {
        const actions = analyst?.recommended_actions || [];
        
        return `
            <div class="finding-section recommendations-section">
                <h4>🎯 Security Recommendations</h4>
                <div class="finding-content">
                    ${analyst?.business_impact ? `
                        <div class="business-impact">
                            <strong>Business Impact:</strong> ${analyst.business_impact}
                        </div>
                    ` : ''}
                    
                    <div class="recommendations-container">
                        <strong>Recommended Actions (${actions.length}):</strong>
                        ${actions.length > 0 ? `
                            <div class="recommendations-list">
                                ${actions.map((action, i) => `
                                    <div class="recommendation-item">
                                        <span class="recommendation-number">${i + 1}</span>
                                        <span class="recommendation-text">${action}</span>
                                    </div>
                                `).join('')}
                            </div>
                        ` : `
                            <div class="no-recommendations">
                                No specific recommendations available
                            </div>
                        `}
                    </div>
                </div>
            </div>
        `;
    }

    createSummarySection() {
        const now = new Date();
        const hasAllResults = this.currentResults.triage && 
                            this.currentResults.context && 
                            this.currentResults.analyst;
        
        return `
            <div class="finding-section summary-section">
                <h4>📋 Analysis Summary</h4>
                <div class="finding-content">
                    <div class="analysis-metadata">
                        <div class="metadata-item">
                            <span class="metadata-label">Completed:</span>
                            <span class="metadata-value">${now.toLocaleString()}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Analysis Status:</span>
                            <span class="metadata-value status-${hasAllResults ? 'complete' : 'partial'}">
                                ${hasAllResults ? 'Complete' : 'Partial'}
                            </span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Stages Completed:</span>
                            <span class="metadata-value">
                                ${this.getCompletedStagesText()}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // ============================================================================
    // UTILITIES
    // ============================================================================

    getCompletedStagesText() {
        const stages = [];
        if (this.currentResults.triage) stages.push('Triage');
        if (this.currentResults.context) stages.push('Context');
        if (this.currentResults.analyst) stages.push('Analysis');
        
        return stages.length > 0 ? stages.join(' → ') : 'None';
    }

    hasResults() {
        return this.currentResults.triage || 
               this.currentResults.context || 
               this.currentResults.analyst;
    }

    isComplete() {
        return this.currentResults.triage && 
               this.currentResults.context && 
               this.currentResults.analyst;
    }

    // ============================================================================
    // EXPORT FUNCTIONALITY
    // ============================================================================

    exportResults(format = 'json') {
        const exportData = {
            timestamp: new Date().toISOString(),
            results: this.currentResults,
            summary: {
                completedStages: this.getCompletedStagesText(),
                isComplete: this.isComplete(),
                hasResults: this.hasResults()
            }
        };

        let content, filename, mimeType;

        switch (format) {
            case 'json':
                content = JSON.stringify(exportData, null, 2);
                filename = `soc-analysis-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
                mimeType = 'application/json';
                break;
            case 'text':
                content = this.formatAsText(exportData);
                filename = `soc-analysis-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
                mimeType = 'text/plain';
                break;
            default:
                console.error('Unsupported export format:', format);
                return false;
        }

        this.downloadFile(content, filename, mimeType);
        return true;
    }

    formatAsText(data) {
        const { triage, context, analyst } = data.results;
        
        return `SOC SECURITY ANALYSIS REPORT
Generated: ${data.timestamp}
Status: ${data.summary.isComplete ? 'Complete' : 'Partial'}

=== THREAT ASSESSMENT ===
Priority: ${triage?.priority?.toUpperCase() || 'Unknown'}
Threat Type: ${triage?.threat_type || 'Unknown'}
Source IP: ${triage?.source_ip || 'Unknown'}
Confidence: ${((triage?.confidence_score || 0) * 100).toFixed(1)}%
Summary: ${triage?.brief_summary || 'None'}

=== HISTORICAL CONTEXT ===
Documents Analyzed: ${context?.total_documents_found || 0}
Pattern Analysis: ${context?.pattern_analysis || 'None'}
Confidence: ${context?.confidence_assessment || 'Medium'}

=== RECOMMENDATIONS ===
Business Impact: ${analyst?.business_impact || 'None specified'}
Recommended Actions:
${(analyst?.recommended_actions || []).map((action, i) => `${i + 1}. ${action}`).join('\n') || 'None'}

=== ANALYSIS METADATA ===
Completed Stages: ${data.summary.completedStages}
Full Analysis: ${data.summary.isComplete ? 'Yes' : 'No'}
`;
    }

    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        
        URL.revokeObjectURL(url);
        console.log(`📥 Exported findings as ${filename}`);
    }
}