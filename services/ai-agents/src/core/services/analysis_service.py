from datetime import datetime

def parse_agent_conversation(conversation):
    """Parse the conversation string to extract individual agent outputs."""
    lines = conversation.split('\n')
    agent_outputs = {'triage': [], 'context': [], 'analyst': []}
    current_agent = None
    current_message = []

    agent_mapping = {
        'TriageSpecialist': 'triage',
        'ContextAgent': 'context',
        'SeniorAnalyst': 'analyst'
    }

    for line in lines:
        # Check if line contains agent identifier
        agent_found = None
        for agent_name, agent_key in agent_mapping.items():
            if f'[{agent_name}]' in line:
                agent_found = agent_key
                break

        if agent_found:
            # Save previous agent's message if exists
            if current_agent and current_message:
                message_text = '\n'.join(current_message).strip()
                if message_text:
                    agent_outputs[current_agent].append(message_text)

            # Start new agent message
            current_agent = agent_found
            current_message = [line]
        elif current_agent and line.strip():
            current_message.append(line)

    # Don't forget the last message
    if current_agent and current_message:
        message_text = '\n'.join(current_message).strip()
        if message_text:
            agent_outputs[current_agent].append(message_text)

    return agent_outputs

def extract_structured_findings(conversation, structured_findings):
    """Extract key findings information for better progress tracking."""
    findings_summary = {
        'priority_found': False,
        'context_searched': False,
        'analysis_completed': False,
        'priority_level': 'unknown',
        'threat_type': 'unknown'
    }

    # Check structured findings first
    if structured_findings and 'priority_threat' in structured_findings:
        priority_threat = structured_findings['priority_threat']
        if priority_threat:
            findings_summary['priority_found'] = True
            findings_summary['priority_level'] = priority_threat.get('priority', 'unknown').lower()
            findings_summary['threat_type'] = priority_threat.get('threat_type', 'unknown')

    if structured_findings and 'detailed_analysis' in structured_findings:
        if structured_findings['detailed_analysis']:
            findings_summary['analysis_completed'] = True

    # Check conversation for context search activity
    if 'search_historical_incidents' in conversation or 'ChromaDB' in conversation:
        findings_summary['context_searched'] = True

    # Fallback to conversation parsing if structured findings incomplete
    conversation_lower = conversation.lower()
    if 'priority_identified' in conversation_lower or 'critical' in conversation_lower or 'high priority' in conversation_lower:
        findings_summary['priority_found'] = True

    if 'critical' in conversation_lower:
        findings_summary['priority_level'] = 'critical'
    elif 'high' in conversation_lower:
        findings_summary['priority_level'] = 'high'
    elif 'medium' in conversation_lower:
        findings_summary['priority_level'] = 'medium'

    return findings_summary
