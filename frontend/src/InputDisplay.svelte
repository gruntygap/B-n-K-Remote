<script lang="ts">
  import { parameterLabel } from './parameter-display.js';

  let { parameters, readings, status, supported }: {
    parameters: { name: string; description: string; note: string }[];
    readings: Record<string, { raw: number; value: number | null; unit: string; label: string | null } | null>;
    status: string; supported: boolean;
  } = $props();
</script>

<section class="display input-display" aria-label="Current input sound settings">
  <div class="display-meta"><span>CURRENT INPUT</span><span>SOUND</span></div>
  <dl class="input-readings">
    {#each parameters as parameter}
      <div class="input-reading">
        <dt title={parameter.note}>{parameter.description}{parameter.name === 'rear_delay' ? '*' : ''}</dt>
        <dd>{parameterLabel(readings[parameter.name])}</dd>
      </div>
    {/each}
  </dl>
  {#if supported && readings.rear_delay}
    <p class="input-display-note">*Rear delay shown for non-Pro Logic. Pro Logic uses 16–30 ms.</p>
  {/if}
  <p class="input-display-status">{status}</p>
</section>
