# services/ai-agents/src/core/services/state_manager.py
"""
Workflow State Manager - Centralized state tracking
"""

from datetime import datetime
from typing import Optional, Dict, Any
from core.models.analysis import PriorityFindings, ContextResearchResult, SOCAnalysisResult
import logging

agent_logger = logging.getLogger("agent_diagnostics")

class WorkflowStateManager:
    """Manages workflow state using structured data"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.workflow_start_time = datetime.now()
        
        # Structured findings storage
        self.triage_findings: Optional[PriorityFindings] = None
        self.context_research: Optional[ContextResearchResult] = None
        self.analyst_results: Optional[Dict[str, Any]] = None
        self.structured_result: Optional[SOCAnalysisResult] = None
        
        # Workflow tracking
        self.approvals: Dict[str, Dict[str, Any]] = {}
        self.workflow_complete = False
        self.workflow_rejected = False
        
        # Stage completion tracking
        self.completed_stages = []
        
    def store_triage_findings(self, findings: PriorityFindings):
        """Store structured triage findings"""
        self.triage_findings = findings
        self._mark_stage_complete("triage")
        agent_logger.info(f"✅ Stored triage findings: {findings.threat_type} from {findings.source_ip}")
    
    def store_context_research(self, research: ContextResearchResult):
        """Store structured context research"""
        self.context_research = research
        self._mark_stage_complete("context")
        agent_logger.info(f"✅ Stored context research: {research.total_documents_found} documents")
    
    def store_analyst_results(self, results: Dict[str, Any]):
        """Store structured analyst results"""
        self.analyst_results = results
        self._mark_stage_complete("analyst")
        agent_logger.info("✅ Stored analyst results")
    
    def store_structured_result(self, result: SOCAnalysisResult):
        """Store final structured result"""
        self.structured_result = result
        
        # Check for completion flags
        if result.workflow_complete or result.analysis_status == "complete":
            self.workflow_complete = True
            agent_logger.info("✅ Workflow marked as complete via structured flags")
    
    def record_approval(self, stage: str, approved: bool, response: str = None):
        """Record approval decision"""
        self.approvals[stage] = {
            "approved": approved,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
        
        if not approved:
            self.workflow_rejected = True
            agent_logger.info(f"❌ Workflow rejected at {stage} stage")
        else:
            agent_logger.info(f"✅ {stage} stage approved")
    
    def is_workflow_complete(self) -> bool:
        """Check if workflow is complete"""
        return self.workflow_complete
    
    def was_rejected(self) -> bool:
        """Check if workflow was rejected"""
        return self.workflow_rejected
    
    def get_workflow_duration(self) -> float:
        """Get workflow duration in seconds"""
        return (datetime.now() - self.workflow_start_time).total_seconds()
    
    def get_progress_percentage(self) -> int:
        """Calculate progress percentage based on completed stages"""
        stage_weights = {
            "triage": 30,
            "context": 60,
            "analyst": 90
        }
        
        if self.workflow_complete:
            return 100
        
        progress = 0
        for stage in self.completed_stages:
            progress = max(progress, stage_weights.get(stage, 0))
        
        return progress
    
    def get_current_stage(self) -> str:
        """Get current workflow stage"""
        if self.workflow_complete:
            return "complete"
        elif "analyst" in self.completed_stages:
            return "finalizing"
        elif "context" in self.completed_stages:
            return "analyst_active"
        elif "triage" in self.completed_stages:
            return "context_active"
        else:
            return "triage_active"
    
    def get_context_for_approval(self, stage: str) -> Dict[str, Any]:
        """Get structured context for approval requests"""
        if stage == "triage" and self.triage_findings:
            return {
                "threat_type": self.triage_findings.threat_type,
                "source_ip": self.triage_findings.source_ip,
                "priority": self.triage_findings.priority,
                "confidence_score": self.triage_findings.confidence_score,
                "brief_summary": self.triage_findings.brief_summary
            }
        elif stage == "context" and self.context_research:
            return {
                "total_documents_found": self.context_research.total_documents_found,
                "pattern_analysis": self.context_research.pattern_analysis,
                "confidence_assessment": self.context_research.confidence_assessment
            }
        elif stage == "analyst" and self.analyst_results:
            return {
                "recommendations_count": len(self.analyst_results.get('recommended_actions', [])),
                "business_impact": self.analyst_results.get('business_impact', ''),
                "threat_assessment": self.analyst_results.get('threat_assessment', {})
            }
        
        return {}
    
    def get_completion_summary(self) -> Dict[str, Any]:
        """Get workflow completion summary"""
        return {
            "session_id": self.session_id,
            "duration_seconds": self.get_workflow_duration(),
            "completed_stages": self.completed_stages.copy(),
            "has_triage": self.triage_findings is not None,
            "has_context": self.context_research is not None,
            "has_analysis": self.analyst_results is not None,
            "has_structured_result": self.structured_result is not None,
            "workflow_complete": self.workflow_complete,
            "workflow_rejected": self.workflow_rejected,
            "approvals": self.approvals.copy()
        }
    
    def _mark_stage_complete(self, stage: str):
        """Mark a stage as complete"""
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)
            agent_logger.info(f"✅ Stage completed: {stage}")