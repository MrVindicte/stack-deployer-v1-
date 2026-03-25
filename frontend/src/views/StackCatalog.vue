<script setup>
import { ref, computed, onMounted } from 'vue'
import { useStacksStore } from '@/stores/stacks'
import {
  Layers, ShieldCheck, Globe, Eye, Activity, Code, Search
} from 'lucide-vue-next'

const store = useStacksStore()
const search = ref('')
const categoryFilter = ref('all')

onMounted(() => store.fetchStacks())

const iconMap = {
  'shield-check': ShieldCheck,
  'globe': Globe,
  'eye': Eye,
  'activity': Activity,
  'code': Code,
  'server': Layers,
}

const categories = [
  { id: 'all', label: 'Tout' },
  { id: 'windows', label: 'Windows' },
  { id: 'linux', label: 'Linux' },
  { id: 'security', label: 'Sécurité' },
]

const categoryColors = {
  windows: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  linux: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  security: 'bg-red-500/15 text-red-400 border-red-500/20',
  hybrid: 'bg-purple-500/15 text-purple-400 border-purple-500/20',
}

const filtered = computed(() => {
  return store.stacks.filter(s => {
    const matchSearch = !search.value ||
      s.name.toLowerCase().includes(search.value.toLowerCase()) ||
      s.description?.toLowerCase().includes(search.value.toLowerCase())
    const matchCat = categoryFilter.value === 'all' || s.category === categoryFilter.value
    return matchSearch && matchCat
  })
})
</script>

<template>
  <div class="p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-surface-100">Catalogue de stacks</h1>
      <p class="text-sm text-surface-500 mt-1">Sélectionnez une stack à déployer sur Proxmox</p>
    </div>

    <!-- Filters -->
    <div class="flex flex-col sm:flex-row gap-3">
      <div class="relative flex-1">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" />
        <input v-model="search" class="input pl-10" placeholder="Rechercher une stack..." />
      </div>
      <div class="flex gap-2">
        <button
          v-for="cat in categories"
          :key="cat.id"
          @click="categoryFilter = cat.id"
          class="btn-sm"
          :class="categoryFilter === cat.id
            ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
            : 'btn-ghost'"
        >
          {{ cat.label }}
        </button>
      </div>
    </div>

    <!-- Grid -->
    <div v-if="store.loading" class="text-center py-12">
      <div class="w-8 h-8 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin mx-auto" />
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <router-link
        v-for="stack in filtered"
        :key="stack.slug"
        :to="`/stacks/${stack.slug}`"
        class="card p-5 hover:border-surface-600 transition-all duration-200 group block"
      >
        <div class="flex items-start gap-4">
          <div class="w-11 h-11 rounded-xl bg-surface-800 flex items-center justify-center shrink-0
                       group-hover:bg-brand-600/20 transition-colors">
            <component
              :is="iconMap[stack.icon] || Layers"
              class="w-5 h-5 text-surface-400 group-hover:text-brand-400 transition-colors"
            />
          </div>
          <div class="flex-1 min-w-0">
            <h3 class="text-sm font-medium text-surface-200 group-hover:text-surface-100">
              {{ stack.name }}
            </h3>
            <p class="text-xs text-surface-500 mt-1 line-clamp-2">{{ stack.description }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3 mt-4">
          <span class="badge border" :class="categoryColors[stack.category] || 'badge-neutral'">
            {{ stack.category }}
          </span>
          <span class="text-xs text-surface-500">{{ stack.vm_count }} VM(s)</span>
          <span class="text-xs text-surface-500">{{ stack.service_count }} services</span>
        </div>
      </router-link>
    </div>

    <div v-if="!store.loading && filtered.length === 0" class="text-center py-12">
      <Layers class="w-10 h-10 text-surface-700 mx-auto mb-3" />
      <p class="text-sm text-surface-500">Aucune stack trouvée</p>
    </div>
  </div>
</template>
