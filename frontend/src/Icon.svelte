<script lang="ts">
  let { name, size = 20 }: { name: string; size?: number } = $props();
  const paths: Record<string, string> = {
    power: 'M12 2v10 M5.6 5.6a9 9 0 1 0 12.8 0',
    plus: 'M12 5v14 M5 12h14',
    minus: 'M5 12h14',
    up: 'm6 15 6-6 6 6',
    down: 'm6 9 6 6 6-6',
    left: 'm15 6-6 6 6 6',
    right: 'm9 6 6 6-6 6',
    mute: 'M11 5 6 9H3v6h3l5 4z M16 9l6 6 M22 9l-6 6',
    menu: 'M4 6h16 M4 12h16 M4 18h16',
    back: 'm9 5-6 6 6 6 M3 11h11a6 6 0 0 1 0 12',
    source: 'M14 3h6v18h-6 M3 12h12 M10 7l5 5-5 5',
    radio: 'M4 7h16v14H4z M4 7l13-5 M7 12h4 M7 16h4 M16 13v4',
  };
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d={paths[name] ?? paths.source} />
</svg>
