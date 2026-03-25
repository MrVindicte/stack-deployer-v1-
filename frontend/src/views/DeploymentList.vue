<script setup>
import { onMounted } from 'vue'
import { useDeploymentsStore } from '@/stores/deployments'
import StatusBadge from '@/components/StatusBadge.vue'
import { Rocket, ArrowRight, Clock } from 'lucide-vue-next'

const store = useDeploymentsStore()
onMounted(() => store.fetchDeployments())

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>

<template>
  <div class="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-surface-100">Déploiements</h1>
        <p class="text-sm text-surface-500 mt-1">Historique et gestion de vos stacks déployées</p>
      </div>
      <router-link to="/stacks" class="btn-primary">
        <Rocket class="w-4 h-4" /> Nouveau
      </router-link>
    </div>

    <div v-if="store.loading" class="text-center py-16">
      <div class="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin mx-auto" />
    </div>

    <div v-else-if="store.deployments.length === 0" class="card p-12 text-center">
      <Rocket class="w-10 h-10 text-surface-700 mx-auto mb-3" />
      <p class="text-surface-400">Aucun déploiement pour l'instant</p>
      <router-link to="/stacks" class="btn-primary btn-sm mt-4 inline-flex">
        Parcourir le catalogue
      </router-link>
    </div>

    <div v-else class="space-y-2">
      <router-link
        v-for="d in store.deployments"
        :key="d.id"
        :to="`/deployments/${d.id}`"
        class="card p-4 flex items-center gap-4 hover:border-surface-700 transition-colors block"
      >
        <div class="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center shrink-0">
          <Rocket class="w-5 h-5 text-surface-400" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-surface-200 truncate">{{ d.name }}</div>
          <div class="flex items-center gap-3 text-xs text-surface-500 mt-0.5">
            <span>{{ d.stack_name }}</span>
            <span class="flex items-center gap-1">
              <Clock class="w-3 h-3" /> {{ formatDate(d.created_at) }}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-xs text-surface-500">{{ d.selected_services?.length || 0 }} svc</span>
          <StatusBadge :status="d.status" />
          <ArrowRight class="w-4 h-4 text-surface-600" />
        </div>
      </router-link>
    </div>
  </div>
</template>
