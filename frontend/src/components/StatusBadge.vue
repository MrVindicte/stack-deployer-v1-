<script setup>
const props = defineProps({ status: String })

const map = {
  pending:      { label: 'En attente',    class: 'badge-neutral' },
  provisioning: { label: 'Provisioning',  class: 'badge-info' },
  configuring:  { label: 'Configuration', class: 'badge-info' },
  running:      { label: 'En cours',      class: 'badge-success' },
  stopped:      { label: 'Arrêté',        class: 'badge-warning' },
  failed:       { label: 'Échec',         class: 'badge-danger' },
  partial:      { label: 'Partiel',       class: 'badge-warning' },
  destroyed:    { label: 'Détruit',       class: 'badge-neutral' },
  created:      { label: 'Créé',          class: 'badge-info' },
  configured:   { label: 'Configuré',     class: 'badge-success' },
  starting:     { label: 'Démarrage',     class: 'badge-info' },
}

const info = map[props.status] || { label: props.status, class: 'badge-neutral' }
</script>

<template>
  <span :class="info.class">
    <span
      v-if="['provisioning','configuring','starting'].includes(status)"
      class="w-1.5 h-1.5 rounded-full bg-current animate-pulse-dot"
    />
    {{ info.label }}
  </span>
</template>
