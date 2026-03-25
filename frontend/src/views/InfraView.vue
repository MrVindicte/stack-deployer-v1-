<script setup>
import { ref, onMounted } from 'vue'
import api from '@/composables/useApi'
import {
  Server, Cpu, MemoryStick, Clock, HardDrive,
  RefreshCw, Layers, Wrench, AlertCircle
} from 'lucide-vue-next'

const proxmox = ref(null)
const templates = ref([])
const roles = ref([])
const loading = ref(true)
const error = ref('')

async function fetchAll() {
  loading.value = true
  error.value = ''
  try {
    const [pxRes, tplRes, roleRes] = await Promise.all([
      api.get('/infra/proxmox/status').catch(() => ({ data: { online: false } })),
      api.get('/infra/proxmox/templates').catch(() => ({ data: [] })),
      api.get('/infra/ansible/roles').catch(() => ({ data: { roles: [] } })),
    ])
    proxmox.value = pxRes.data
    templates.value = tplRes.data
    roles.value = roleRes.data.roles || []
  } catch (e) {
    error.value = 'Erreur de connexion'
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)

function formatBytes(bytes) {
  if (!bytes) return '0'
  const gb = bytes / (1024 ** 3)
  return gb.toFixed(1)
}

function formatUptime(seconds) {
  if (!seconds) return '—'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${d}j ${h}h ${m}m`
}
</script>

<template>
  <div class="p-6 lg:p-8 max-w-5xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-surface-100">Infrastructure</h1>
        <p class="text-sm text-surface-500 mt-1">État de Proxmox, templates et rôles Ansible</p>
      </div>
      <button @click="fetchAll" class="btn-secondary btn-sm" :disabled="loading">
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" /> Rafraîchir
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="card p-4 flex items-center gap-3 border-red-500/30">
      <AlertCircle class="w-5 h-5 text-red-400" />
      <span class="text-sm text-red-400">{{ error }}</span>
    </div>

    <!-- Proxmox node -->
    <div class="card p-6">
      <div class="flex items-center gap-3 mb-5">
        <div class="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center">
          <Server class="w-5 h-5 text-surface-400" />
        </div>
        <div>
          <h2 class="text-sm font-medium text-surface-200">Proxmox VE — Dell PowerEdge T630</h2>
          <p class="text-xs text-surface-500">Hyperviseur principal</p>
        </div>
        <span
          class="ml-auto badge"
          :class="proxmox?.online ? 'badge-success' : 'badge-danger'"
        >
          {{ proxmox?.online ? 'En ligne' : 'Hors ligne' }}
        </span>
      </div>

      <div v-if="proxmox?.online" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="p-3 rounded-lg bg-surface-800/40">
          <div class="flex items-center gap-2 text-xs text-surface-500 mb-1">
            <Cpu class="w-3.5 h-3.5" /> CPU
          </div>
          <div class="text-lg font-mono text-surface-200">
            {{ (proxmox.cpu_usage * 100).toFixed(1) }}%
          </div>
          <div class="mt-2 h-1.5 bg-surface-800 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all"
              :class="proxmox.cpu_usage > 0.8 ? 'bg-red-500' : proxmox.cpu_usage > 0.5 ? 'bg-amber-500' : 'bg-emerald-500'"
              :style="{ width: `${proxmox.cpu_usage * 100}%` }"
            />
          </div>
        </div>

        <div class="p-3 rounded-lg bg-surface-800/40">
          <div class="flex items-center gap-2 text-xs text-surface-500 mb-1">
            <MemoryStick class="w-3.5 h-3.5" /> RAM
          </div>
          <div class="text-lg font-mono text-surface-200">
            {{ formatBytes(proxmox.memory_used) }} / {{ formatBytes(proxmox.memory_total) }} Go
          </div>
          <div class="mt-2 h-1.5 bg-surface-800 rounded-full overflow-hidden">
            <div
              class="h-full bg-brand-500 rounded-full transition-all"
              :style="{ width: `${(proxmox.memory_used / proxmox.memory_total) * 100}%` }"
            />
          </div>
        </div>

        <div class="p-3 rounded-lg bg-surface-800/40">
          <div class="flex items-center gap-2 text-xs text-surface-500 mb-1">
            <Clock class="w-3.5 h-3.5" /> Uptime
          </div>
          <div class="text-lg font-mono text-surface-200">{{ formatUptime(proxmox.uptime) }}</div>
        </div>

        <div class="p-3 rounded-lg bg-surface-800/40">
          <div class="flex items-center gap-2 text-xs text-surface-500 mb-1">
            <Layers class="w-3.5 h-3.5" /> Templates
          </div>
          <div class="text-lg font-mono text-surface-200">{{ templates.length }}</div>
        </div>
      </div>

      <div v-else class="p-6 text-center rounded-lg bg-surface-800/30">
        <Server class="w-8 h-8 text-surface-700 mx-auto mb-2" />
        <p class="text-sm text-surface-500">
          Proxmox est hors ligne ou inaccessible
        </p>
        <p class="text-xs text-surface-600 mt-1">Vérifiez la connexion et le token API</p>
      </div>
    </div>

    <!-- Templates -->
    <div class="card p-5">
      <h2 class="text-sm font-medium text-surface-300 mb-4 flex items-center gap-2">
        <HardDrive class="w-4 h-4 text-surface-500" /> Templates VM disponibles
      </h2>
      <div v-if="templates.length === 0" class="text-center py-6">
        <p class="text-sm text-surface-500">Aucun template détecté</p>
        <p class="text-xs text-surface-600 mt-1">Créez des templates avec Packer (voir docs/)</p>
      </div>
      <div v-else class="space-y-1.5">
        <div
          v-for="tpl in templates"
          :key="tpl.vmid"
          class="flex items-center gap-3 p-3 rounded-lg bg-surface-800/30"
        >
          <div class="w-8 h-8 rounded bg-surface-700 flex items-center justify-center">
            <HardDrive class="w-4 h-4 text-surface-400" />
          </div>
          <div class="flex-1">
            <span class="text-sm font-mono text-surface-200">{{ tpl.name }}</span>
          </div>
          <span class="text-xs text-surface-500 font-mono">VMID {{ tpl.vmid }}</span>
        </div>
      </div>
    </div>

    <!-- Ansible roles -->
    <div class="card p-5">
      <h2 class="text-sm font-medium text-surface-300 mb-4 flex items-center gap-2">
        <Wrench class="w-4 h-4 text-surface-500" /> Rôles Ansible disponibles
      </h2>
      <div v-if="roles.length === 0" class="text-center py-6">
        <p class="text-sm text-surface-500">Aucun rôle détecté</p>
      </div>
      <div v-else class="flex flex-wrap gap-2">
        <span
          v-for="role in roles"
          :key="role"
          class="px-3 py-1.5 rounded-lg bg-surface-800/50 border border-surface-800
                 text-xs font-mono text-surface-300"
        >
          {{ role }}
        </span>
      </div>
    </div>
  </div>
</template>
