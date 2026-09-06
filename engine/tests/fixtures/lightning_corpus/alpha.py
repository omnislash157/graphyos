

def resolve_widget(widget_id: str) -> str:
    return f"widget:{widget_id}"


class WidgetStore:

    def __init__(self) -> None:
        self._rows: dict[str, str] = {}

    def resolve_widget(self, widget_id: str) -> str:
        marker = resolve_widget(widget_id)
        self._rows[widget_id] = marker
        return marker

    def unrelated_helper(self) -> int:
        return len(self._rows)


def orchestrate() -> str:
    store = WidgetStore()
    return store.resolve_widget("w-1")
