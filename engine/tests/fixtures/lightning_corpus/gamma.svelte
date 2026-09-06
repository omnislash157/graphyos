<script>
  let widgetId = "w-3";

  function resolve_widget(id) {
    return `widget:${id}`;
  }

  $: marker = resolve_widget(widgetId);
</script>

<main>
  <h1>Widget viewer</h1>
  <p>{marker}</p>
</main>

<style>
  main {
    padding: 1rem;
  }
</style>
