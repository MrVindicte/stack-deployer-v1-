<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStacksStore } from '@/stores/stacks'
import { useDeploymentsStore } from '@/stores/deployments'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  ArrowLeft, Rocket, Check, Lock, Info, Cpu, MemoryStick,
  HardDrive, Network, ChevronDown, ChevronUp
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const stackStore = useStacksStore()
const deployStore = useDeploymentsStore()

const stack = ref(null)
const selectedServices = ref(new Set())
const deployName = ref('')
const showAdvanced = ref(false)
const deploying = ref(false)
const error = ref('')
const success = ref('')

// VM spec overrides
const vmOverrides = ref({})

onMounted(async () => {
  const data = await stackStore.fetchStack(route.params.slug)
  if (data) {
    stack.value = data
    // Pre-select required services
    data.services.filter(s => s.required).forEach(s => selectedServices.value.add(s.id))
    // Init deploy name
    deployName.value = `${data.name} — ${new Date().toLocaleDateString('fr-FR')}`
  }
})

function toggleService(svc) {
  if (svc.required) return
  if (selectedServices.value.has(svc.id)) {
    // Check if other selected services depend on this one
    const dependents = stack.value.services.filter(
      s => s.depends_on?.includes(svc.id) && selectedServices.value.has(s.id)
    )
    if (dependents.length > 0) return // Cannot deselect — others depend on it
    selectedServices.value.delete(svc.id)
  } else {
    selectedServices.value.add(svc.id)
    // Auto-select dependencies
    const svcDef = stack.value.services.find(s => s.id === svc.id)
    svcDef?.depends_on?.forEach(depId => selectedServices.value.add(depId))
  }
}

const activeVMs = computed(() => {
  if (!stack.value) return []
  // A VM is needed if any of its roles map to a selected service
  const roleToService = {}
  stack.value.services.forEach(svc => {
    svc.roles?.forEach(role => { roleToService[role] = svc.id })
  })

  return stack.value.vms.filter(vm =>
    vm.roles.some(role => {
      const svcId = roleToService[role]
      return svcId && selectedServices.value.has(svcId)
    })
  )
})

const totalResources = computed(() => {
  return activeVMs.value.reduce((acc, vm) => {
    const specs = vm.default_specs || {}
    return {
      cores: acc.cores + (specs.cores || 0),
      ram: acc.ram + (specs.ram || 0),
      disk: acc.disk + (specs.disk || 0),
    }
  }, { cores: 0, ram: 0, disk: 0 })
})

async function handleDeploy() {
  deploying.value = true
  error.value = ''
  success.value = ''
  try {
    const result = await deployStore.deploy({
      stack_slug: stack.value.slug,
      name: deployName.value,
      selected_services: [...selectedServices.value],
      vm_specs_override: Object.keys(vmOverrides.value).length ? vmOverrides.value : null,
    })
    success.value = `Déploiement lancé ! ID: ${result.id}`
    setTimeout(() => router.push(`/deployments/${result.id}`), 1500)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Échec du déploiement'
  } finally {
    deploying.value = false
  }
}
</script>

<template>
  <div class="p-6 lg:p-8 max-w-5xl mx-auto space-y-6" v-if="stack">
    <!-- Back -->
    <button @click="router.push('/stacks')" class="btn-ghost btn-sm -ml-2">
      <ArrowLeft class="w-4 h-4" /> Catalogue
    </button>

    <!-- Header -->
    <div>
      <h1 class="text-2xl font-semibold text-surface-100">{{ stack.name }}</h1>
      <p class="text-sm text-surface-400 mt-1">{{ stack.description }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left: Service picker -->
      <div class="lg:col-span-2 space-y-4">
        <div class="card p-5">
          <h2 class="text-sm font-medium text-surface-300 mb-4">Sélection des services</h2>

          <div class="space-y-2">
            <div
              v-for="svc in stack.services"
              :key="svc.id"
              @click="toggleService(svc)"
              class="flex items-start gap-3 p-3.5 rounded-lg border transition-all duration-150 cursor-pointer"
              :class="selectedServices.has(svc.id)
                ? 'bg-brand-600/10 border-brand-500/30'
                : 'bg-surface-800/30 border-surface-800 hover:border-surface-700'"
            >
              <!-- Checkbox -->
              <div
                class="w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 transition-all"
                :class="selectedServices.has(svc.id)
                  ? 'bg-brand-600 border-brand-600'
                  : 'border-surface-600'"
              >
                <Check v-if="selectedServices.has(svc.id)" class="w-3 h-3 text-white" />
              </div>

              <!-- Info -->
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium" :class="selectedServices.has(svc.id) ? 'text-surface-100' : 'text-surface-300'">
                    {{ svc.name }}
                  </span>
                  <Lock v-if="svc.required" class="w-3 h-3 text-surface-500" title="Requis" />
                </div>
                <p class="text-xs text-surface-500 mt-0.5">{{ svc.description }}</p>
                <div v-if="svc.depends_on?.length" class="flex items-center gap-1 mt-1.5">
                  <Info class="w-3 h-3 text-surface-600" />
                  <span class="text-xs text-surface-600">
                    Requiert : {{ svc.depends_on.join(', ') }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- VMs that will be deployed -->
        <div class="card p-5">
          <h2 class="text-sm font-medium text-surface-300 mb-4">
            VMs à déployer ({{ activeVMs.length }})
          </h2>
          <div v-if="activeVMs.length === 0" class="text-center py-4">
            <p class="text-sm text-surface-500">Sélectionnez des services pour voir les VMs</p>
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="vm in activeVMs"
              :key="vm.name"
              class="flex items-center gap-4 p-3 rounded-lg bg-surface-800/40"
            >
              <div class="w-8 h-8 rounded bg-surface-700 flex items-center justify-center">
                <Cpu class="w-4 h-4 text-surface-400" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-mono font-medium text-surface-200">{{ vm.name }}</div>
                <div class="text-xs text-surface-500">{{ vm.roles.join(', ') }}</div>
              </div>
              <div class="flex items-center gap-3 text-xs text-surface-500">
                <span class="flex items-center gap-1">
                  <Cpu class="w-3 h-3" /> {{ vm.default_specs?.cores || 2 }}
                </span>
                <span class="flex items-center gap-1">
                  <MemoryStick class="w-3 h-3" /> {{ ((vm.default_specs?.ram || 2048) / 1024).toFixed(0) }}G
                </span>
                <span class="flex items-center gap-1">
                  <HardDrive class="w-3 h-3" /> {{ vm.default_specs?.disk || 40 }}G
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Deploy panel -->
      <div class="space-y-4">
        <!-- Resource summary -->
        <div class="card p-5 space-y-4">
          <h2 class="text-sm font-medium text-surface-300">Ressources totales</h2>
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-xs text-surface-500 flex items-center gap-2">
                <Cpu class="w-3.5 h-3.5" /> CPU
              </span>
              <span class="text-sm font-mono text-surface-200">{{ totalResources.cores }} vCPU</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xs text-surface-500 flex items-center gap-2">
                <MemoryStick class="w-3.5 h-3.5" /> RAM
              </span>
              <span class="text-sm font-mono text-surface-200">{{ (totalResources.ram / 1024).toFixed(1) }} Go</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xs text-surface-500 flex items-center gap-2">
                <HardDrive class="w-3.5 h-3.5" /> Stockage
              </span>
              <span class="text-sm font-mono text-surface-200">{{ totalResources.disk }} Go</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xs text-surface-500 flex items-center gap-2">
                <Network class="w-3.5 h-3.5" /> VMs
              </span>
              <span class="text-sm font-mono text-surface-200">{{ activeVMs.length }}</span>
            </div>
          </div>
        </div>

        <!-- Deploy form -->
        <div class="card p-5 space-y-4">
          <h2 class="text-sm font-medium text-surface-300">Déployer</h2>

          <div>
            <label class="block text-xs text-surface-500 mb-1.5">Nom du déploiement</label>
            <input v-model="deployName" class="input" />
          </div>

          <!-- Advanced toggle -->
          <button
            @click="showAdvanced = !showAdvanced"
            class="flex items-center gap-2 text-xs text-surface-500 hover:text-surface-300 transition-colors"
          >
            <component :is="showAdvanced ? ChevronUp : ChevronDown" class="w-3.5 h-3.5" />
            Options avancées
          </button>

          <div v-if="showAdvanced" class="space-y-3 p-3 rounded-lg bg-surface-800/30 border border-surface-800">
            <div>
              <label class="block text-xs text-surface-500 mb-1">VLAN ID</label>
              <input class="input" type="number" placeholder="Aucun" />
            </div>
            <div>
              <label class="block text-xs text-surface-500 mb-1">Domaine</label>
              <input class="input" value="lab.local" />
            </div>
          </div>

          <!-- Error / Success -->
          <div v-if="error" class="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {{ error }}
          </div>
          <div v-if="success" class="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-sm text-emerald-400">
            {{ success }}
          </div>

          <!-- Deploy button -->
          <button
            @click="handleDeploy"
            :disabled="deploying || activeVMs.length === 0"
            class="btn-primary w-full"
          >
            <span v-if="deploying" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <Rocket v-else class="w-4 h-4" />
            {{ deploying ? 'Déploiement en cours...' : 'Lancer le déploiement' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Loading -->
  <div v-else class="p-8 text-center">
    <div class="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin mx-auto" />
  </div>
</template>
