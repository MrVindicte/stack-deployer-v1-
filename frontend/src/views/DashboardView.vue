<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores/deployments'
import { useStacksStore } from '@/stores/stacks'
import api from '@/composables/useApi'
import StatusBadge from '@/components/StatusBadge.vue'
import { Layers, Rocket, Server, Activity, ArrowRight, Plus } from 'lucide-vue-next'

const router = useRouter()
const deployStore = useDeploymentsStore()
const stackStore = useStacksStore()
const proxmoxStatus = ref(null)

onMounted(async () => {
  await Promise.all([
    deployStore.fetchDeployments(),
    stackStore.fetchStacks(),
    api.get('/infra/proxmox/status').then(r => proxmoxStatus.value = r.data).catch(() => null),
  ])
})

const stats = [
  { label: 'Stacks disponibles', icon: Layers, get: () => stackStore.stacks.length, color: 'text-brand-400' },
  { label: 'Déploiements actifs', icon: Rocket, get: () => deployStore.deployments.filter(d => d.status === 'running').length, color: 'text-emerald-400' },
  { label: 'Total déploiements', icon: Activity, get: () => deployStore.deployments.length, color: 'text-amber-400' },
]
</script>

<template>
  <div class="p-6 lg:p-8 max-w-7xl mx-auto space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-surface-100">Dashboard</h1>
        <p class="text-sm text-surface-500 mt-1">Vue d'ensemble de votre infrastructure</p>
      </div>
      <router-link to="/stacks" class="btn-primary">
        <Plus class="w-4 h-4" /> Nouveau déploiement
      </router-link>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div v-for="stat in stats" :key="stat.label" class="card p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-surface-500 uppercase tracking-wider">{{ stat.label }}</p>
            <p class="text-2xl font-semibold mt-1" :class="stat.color">{{ stat.get() }}</p>
          </div>
          <div class="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center">
            <component :is="stat.icon" class="w-5 h-5 text-surface-400" />
          </div>
        </div>
      </div>
    </div>

    <!-- Proxmox Status -->
    <div class="card p-5" v-if="proxmoxStatus">
      <div class="flex items-center gap-3 mb-4">
        <Server class="w-5 h-5 text-surface-400" />
        <h2 class="text-sm font-medium text-surface-200">Proxmox VE</h2>
        <span
          class="ml-auto badge"
          :class="proxmoxStatus.online ? 'badge-success' : 'badge-danger'"
        >
          {{ proxmoxStatus.online ? 'En ligne' : 'Hors ligne' }}
        </span>
      </div>
      <div v-if="proxmoxStatus.online" class="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div>
          <p class="text-xs text-surface-500">CPU</p>
          <p class="text-sm font-mono text-surface-200">
            {{ (proxmoxStatus.cpu_usage * 100).toFixed(1) }}%
          </p>
        </div>
        <div>
          <p class="text-xs text-surface-500">RAM</p>
          <p class="text-sm font-mono text-surface-200">
            {{ ((proxmoxStatus.memory_used / proxmoxStatus.memory_total) * 100).toFixed(1) }}%
          </p>
        </div>
        <div>
          <p class="text-xs text-surface-500">Uptime</p>
          <p class="text-sm font-mono text-surface-200">
            {{ Math.floor(proxmoxStatus.uptime / 86400) }}j
            {{ Math.floor((proxmoxStatus.uptime % 86400) / 3600) }}h
          </p>
        </div>
      </div>
    </div>

    <!-- Recent deployments -->
    <div>
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-medium text-surface-300">Déploiements récents</h2>
        <router-link to="/deployments" class="btn-ghost btn-sm">
          Tout voir <ArrowRight class="w-3.5 h-3.5" />
        </router-link>
      </div>
      <div v-if="deployStore.deployments.length === 0" class="card p-8 text-center">
        <Rocket class="w-8 h-8 text-surface-600 mx-auto mb-3" />
        <p class="text-sm text-surface-500">Aucun déploiement</p>
        <router-link to="/stacks" class="btn-primary btn-sm mt-4 inline-flex">
          Déployer une stack
        </router-link>
      </div>
      <div v-else class="space-y-2">
        <router-link
          v-for="d in deployStore.deployments.slice(0, 5)"
          :key="d.id"
          :to="`/deployments/${d.id}`"
          class="card p-4 flex items-center gap-4 hover:border-surface-700 transition-colors cursor-pointer block"
        >
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-surface-200 truncate">{{ d.name }}</div>
            <div class="text-xs text-surface-500 mt-0.5">{{ d.stack_name }}</div>
          </div>
          <StatusBadge :status="d.status" />
          <ArrowRight class="w-4 h-4 text-surface-600 shrink-0" />
        </router-link>
      </div>
    </div>
  </div>
</template>
