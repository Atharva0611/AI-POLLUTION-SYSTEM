from typing import TypedDict, Optional, Dict, List

class AgentState(TypedDict, total=False):
    user_query: str
    location: Optional[str]
    pollutant: Optional[str]
    current_data: Optional[Dict]
    forecast: Optional[Dict]
    source_analysis: Optional[Dict]
    hotspots: Optional[List]
    retrieved_documents: Optional[List]
    policy_recommendation: Optional[str]
    validation_result: Optional[Dict]
    final_response: Optional[str]
    errors: Optional[List[str]]
