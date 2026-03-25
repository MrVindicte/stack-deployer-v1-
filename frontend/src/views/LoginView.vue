<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Terminal, AlertCircle } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Connexion échouée'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-surface-950 px-4">
    <div class="w-full max-w-sm animate-fade-in">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-14 h-14 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-4">
          <Terminal class="w-7 h-7 text-white" />
        </div>
        <h1 class="text-xl font-semibold text-surface-100">Stack Deployer</h1>
        <p class="text-sm text-surface-500 mt-1">Connexion à l'orchestrateur</p>
      </div>

      <!-- Form -->
      <div class="card p-6 space-y-5">
        <!-- Error -->
        <div v-if="error" class="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <AlertCircle class="w-4 h-4 text-red-400 shrink-0" />
          <span class="text-sm text-red-400">{{ error }}</span>
        </div>

        <div>
          <label class="block text-xs font-medium text-surface-400 mb-1.5">Utilisateur</label>
          <input
            v-model="username"
            type="text"
            class="input"
            placeholder="admin"
            autofocus
            @keyup.enter="handleLogin"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-surface-400 mb-1.5">Mot de passe</label>
          <input
            v-model="password"
            type="password"
            class="input"
            placeholder="••••••••"
            @keyup.enter="handleLogin"
          />
        </div>
        <button
          @click="handleLogin"
          :disabled="loading || !username || !password"
          class="btn-primary w-full"
        >
          <span v-if="loading" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          {{ loading ? 'Connexion...' : 'Se connecter' }}
        </button>
      </div>
    </div>
  </div>
</template>
