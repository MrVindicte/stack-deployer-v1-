<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import SidebarNav from '@/components/SidebarNav.vue'

const route = useRoute()
const auth = useAuthStore()
const showSidebar = computed(() => route.name !== 'Login')
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <SidebarNav v-if="showSidebar" />
    <main
      class="flex-1 overflow-y-auto"
      :class="showSidebar ? 'ml-0' : ''"
    >
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style>
.page-enter-active { transition: all 0.2s ease-out; }
.page-leave-active { transition: all 0.15s ease-in; }
.page-enter-from   { opacity: 0; transform: translateY(6px); }
.page-leave-to     { opacity: 0; transform: translateY(-4px); }
</style>
