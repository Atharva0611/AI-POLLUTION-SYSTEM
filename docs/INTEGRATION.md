# Integration notes

1. Keep the existing RAG, XGBoost, WeatherAPI, SHAP, DBSCAN, source-analysis, and LangGraph nodes.
2. Add the innovation node after the existing environment node and before the response node.
3. The node obtains location from graph state or the existing location resolver.
4. No city/station is hard-coded.
5. If the innovation layer fails, the node returns `innovation_status=unavailable` and does not break the existing graph.
