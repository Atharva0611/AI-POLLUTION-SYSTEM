from backend.innovation.langgraph_node import resolve_location_from_state


def test_location_is_not_hardcoded():
    for value in ["Beed", "Mumbai", "Delhi NCR", "Nagpur"]:
        assert resolve_location_from_state({"location": value}) == value
