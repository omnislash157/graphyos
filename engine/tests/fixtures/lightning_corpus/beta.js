// beta — the brace-language fixture (pseudo_ast lane).
function resolveWidget(widgetId) {
  return `widget:${widgetId}`;
}

const widgetStore = {
  rows: new Map(),
  resolve_widget(widgetId) {
    const marker = resolveWidget(widgetId);
    this.rows.set(widgetId, marker);
    return marker;
  },
};

function orchestrate() {
  return widgetStore.resolve_widget("w-2");
}

module.exports = { resolveWidget, widgetStore, orchestrate };
