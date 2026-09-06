# session transcript fixture — the prose grammar lane

--- [1] USER

How do I resolve a widget by id from the store?

--- [1] ASSISTANT

Call the store's resolver with the id; it returns the marker string and caches the row.

--- [2] USER

And if the id is unknown?

--- [2] ASSISTANT

The resolver still mints a marker; unknown ids surface at read time, not at resolution.
