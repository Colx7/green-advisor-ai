from app.runtime_state import RuntimeState


class FakeRedis:
    def __init__(self):
        self.values = {}

    def ping(self):
        return True

    def setex(self, key, ttl, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)


def test_runtime_state_round_trip():
    state = RuntimeState()
    state.client = FakeRedis()
    payload = {"project_id": 7, "operation": "assessment", "status": "success"}
    assert state.available() is True
    assert state.set_project_status(7, payload) is True
    assert state.get_project_status(7) == payload
