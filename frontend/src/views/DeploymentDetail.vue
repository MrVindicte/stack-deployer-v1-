<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores/deployments'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  ArrowLeft, Cpu, MemoryStick, HardDrive, Network,
  Square, Trash2, RefreshCw, Clock, ScrollText,
  CheckCircle2, AlertTriangle, XCircle, Info
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useDeploymentsStore()

const activeTab = ref('vms')
const confirmDestroy = ref(false)
let logPoll = null

onMounted(async () => {
  await store.fetchDeployment(route.params.id)
  await store.fetchLogs(route.params.id)

  const TERMINAL_STATUSES = ['running', 'partial', 'failed', 'stopped', 'destroyed']

  // Poll logs while deployment is in progress; stop automatically on terminal status
  logPoll = setInterval(async () => {
    if (['provisioning', 'configuring', 'pending'].includes(store.current?.status)) {
      await store.fetchDeployment(route.params.id)
      await store.fetchLogs(route.params.id)
    }
    if (TERMINAL_STATUSES.includes(store.current?.status)) {
      clearInterval(logPoll)
      logPoll = null
    }
  }, 5000)
})

onUnmounted(() => {
  if (logPoll) clearInterval(logPoll)
})

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

const logIcons = {
  info:    Info,
  success: CheckCircle2,
  warn:    AlertTriangle,
  error:   XCircle,
}

const logColors = {
  info:    'text-blue-400',
  success: 'text-emerald-400',
  warn:    'text-amber-400',
  error:   'text-red-400',
}

async function handleStop() {
  await store.stopDeployment(route.params.id)
}

async function handleDestroy() {
  await store.destroyDeployment(route.params.id)
  router.push('/deployments')
}

async function handleRefresh() {
  await store.fetchDeployment(route.params.id)
  await store.fetchLogs(route.params.id)
}
</script>

<template>
  <div class="p-6 lg:p-8 max-w-5xl mx-auto space-y-6" v-if="store.current">
    <!-- Back -->
    <button @click="router.push('/deployments')" class="btn-ghost btn-sm -ml-2">
      <ArrowLeft class="w-4 h-4" /> Déploiements
    </button>

    <!-- Header -->
    <div class="flex items-start justify-between">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-semibold text-surface-100">{{ store.current.name }}</h1>
          <StatusBadge :status="store.current.status" />
        </div>
        <p class="text-sm text-surface-500 mt-1">
          Stack : {{ store.current.stack_name }} — {{ store.current.vms?.length || 0 }} VM(s)
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button @click="handleRefresh" class="btn-ghost btn-sm">
          <RefreshCw class="w-4 h-4" />
        </button>
        <button
          v-if="store.current.status === 'running'"
          @click="handleStop"
          class="btn-secondary btn-sm"
        >
          <Square class="w-3.5 h-3.5" /> Arrêter
        </button>
        <button
          v-if="!confirmDestroy"
          @click="confirmDestroy = true"
          class="btn-danger btn-sm"
        >
          <Trash2 class="w-3.5 h-3.5" /> Détruire
        </button>
        <div v-else class="flex items-center gap-2">
          <span class="text-xs text-red-400">Confirmer ?</span>
          <button @click="handleDestroy" class="btn-danger btn-sm">Oui</button>
          <button @click="confirmDestroy = false" class="btn-ghost btn-sm">Non</button>
        </div>
      </div>
    </div>

    <!-- Info cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="card p-4">
        <p class="text-xs text-surface-500">Créé le</p>
        <p class="text-sm font-mono text-surface-200 mt-1">{{ formatDate(store.current.created_at) }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-surface-500">Démarré le</p>
        <p class="text-sm font-mono text-surface-200 mt-1">{{ formatDate(store.current.started_at) }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-surface-500">Services</p>
        <p class="text-sm text-surface-200 mt-1">{{ store.current.selected_services?.length || 0 }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-surface-500">VMs</p>
        <p class="text-sm text-surface-200 mt-1">{{ store.current.vms?.length || 0 }}</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-surface-800">
      <button
        v-for="tab in [{id:'vms', label:'Machines virtuelles'}, {id:'logs', label:'Logs'}]"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="px-4 py-2.5 text-sm transition-colors relative"
        :class="activeTab === tab.id
          ? 'text-brand-400'
          : 'text-surface-500 hover:text-surface-300'"
      >
        {{ tab.label }}
        <div
          v-if="activeTab === tab.id"
          class="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-500 rounded-full"
        />
      </button>
    </div>

    <!-- VMs tab -->
    <div v-if="activeTab === 'vms'" class="space-y-2">
      <div v-if="!store.current.vms?.length" class="card p-8 text-center">
        <p class="text-sm text-surface-500">Aucune VM encore créée</p>
      </div>
      <div
        v-for="vm in store.current.vms"
        :key="vm.id"
        class="card p-4"
      >
        <div class="flex items-center gap-4">
          <div class="w-10 h-10 rounded-lg bg-surface-800 flex items-center justify-center shrink-0">
            <Cpu class="w-5 h-5 text-surface-400" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-mono font-medium text-surface-200">{{ vm.vm_name }}</span>
              <StatusBadge :status="vm.status" />
            </div>
            <div class="flex items-center gap-4 text-xs text-surface-500 mt-1">
              <span v-if="vm.proxmox_vmid">VMID: {{ vm.proxmox_vmid }}</span>
              <span v-if="vm.ip_address" class="flex items-center gap-1">
                <Network class="w-3 h-3" /> {{ vm.ip_address }}
              </span>
              <span v-if="vm.roles?.length">Rôles : {{ vm.roles.join(', ') }}</span>
            </div>
          </div>
          <div v-if="vm.specs" class="flex items-center gap-4 text-xs text-surface-500">
            <span class="flex items-center gap-1">
              <Cpu class="w-3 h-3" /> {{ vm.specs.cores || '?' }}
            </span>
            <span class="flex items-center gap-1">
              <MemoryStick class="w-3 h-3" /> {{ ((vm.specs.ram || 0) / 1024).toFixed(0) }}G
            </span>
            <span class="flex items-center gap-1">
              <HardDrive class="w-3 h-3" /> {{ vm.specs.disk || '?' }}G
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Logs tab -->
    <div v-if="activeTab === 'logs'">
      <div v-if="!store.logs.length" class="card p-8 text-center">
        <ScrollText class="w-8 h-8 text-surface-700 mx-auto mb-2" />
        <p class="text-sm text-surface-500">Aucun log disponible</p>
      </div>
      <div v-else class="card p-4 max-h-[500px] overflow-y-auto font-mono text-xs space-y-0.5">
        <div
          v-for="(log, i) in store.logs"
          :key="i"
          class="flex items-start gap-2 py-1 px-2 rounded hover:bg-surface-800/50"
        >
          <component
            :is="logIcons[log.level] || Info"
            class="w-3.5 h-3.5 shrink-0 mt-0.5"
            :class="logColors[log.level] || 'text-surface-500'"
          />
          <span class="text-surface-600 shrink-0 w-16">
            {{ new Date(log.timestamp).toLocaleTimeString('fr-FR') }}
          </span>
          <span
            v-if="log.phase"
            class="text-surface-600 shrink-0 w-24 truncate"
          >
            [{{ log.phase }}]
          </span>
          <span :class="logColors[log.level] || 'text-surface-300'">
            {{ log.message }}
          </span>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="p-8 text-center">
    <div class="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin mx-auto" />
  </div>
</template>
