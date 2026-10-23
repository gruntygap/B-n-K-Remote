<script lang="ts">
  import Icon from './Icon.svelte';
  let { command, label, icon, variant = '', disabled = false, onpress }: {
    command: string; label: string; icon?: string; variant?: string;
    disabled?: boolean; onpress: (command: string) => void;
  } = $props();
</script>

<button class="key {variant}" {disabled} onclick={() => onpress(command)} aria-label={label} title={label} data-command={command}>
  {#if icon}<Icon name={icon} />{/if}
  <span>{label}</span>
</button>
