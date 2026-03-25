<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  LayoutDashboard, Layers, Rocket, Server, LogOut, Terminal
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { name: 'Dashboard',      path: '/',             icon: LayoutDashboard },
  { name: 'Catalogue',      path: '/stacks',       icon: Layers },
  { name: 'Déploiements',   path: '/deployments',  icon: Rocket },
  { name: 'Infrastructure', path: '/infra',         icon: Server },
]

function isActive(path) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="w-64 h-screen bg-surface-950 border-r border-surface-800/60 flex flex-col shrink-0">
    <!-- Logo -->
    <div class="px-5 py-6 border-b border-surface-800/60">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center">
          <Terminal class="w-5 h-5 text-white" />
        </div>
        <div>
          <div class="text-sm font-semibold text-surface-100">Stack Deployer</div>
          <div class="text-xs text-surface-500">Proxmox Orchestrator</div>
        </div>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-150"
        :class="isActive(item.path)
          ? 'bg-brand-600/15 text-brand-400 font-medium'
          : 'text-surface-400 hover:text-surface-200 hover:bg-surface-800/60'"
      >
        <component
          :is="item.icon"
          class="w-[18px] h-[18px] shrink-0"
          :class="isActive(item.path) ? 'text-brand-400' : 'text-surface-500'"
        />
        {{ item.name }}
      </router-link>
    </nav>

    <!-- User section -->
    <div class="px-3 py-4 border-t border-surface-800/60">
      <div class="flex items-center justify-between px-3 py-2">
        <div>
          <div class="text-sm font-medium text-surface-200">{{ auth.username }}</div>
          <div class="text-xs text-surface-500 capitalize">{{ auth.role }}</div>
        </div>
        <button
          @click="logout"
          class="p-2 rounded-lg text-surface-500 hover:text-red-400 hover:bg-surface-800 transition-colors"
          title="Déconnexion"
        >
          <LogOut class="w-4 h-4" />
        </button>
      </div>
    </div>
  </aside>
</template>
