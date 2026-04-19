from easyatcal.backends.base import CalendarBackend, Changes


def test_changes_is_dataclass():
    c = Changes(adds=[], updates=[], deletes=[])
    assert c.adds == []
    assert c.is_empty()


def test_backend_is_protocol_with_apply():
    class Dummy:
        def apply(self, changes: Changes) -> dict[str, str]:
            return {}

    d: CalendarBackend = Dummy()
    assert d.apply(Changes([], [], [])) == {}
