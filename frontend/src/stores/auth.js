import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('sd_token') || '')
  const username = ref(localStorage.getItem('sd_user') || '')
  const role = ref(localStorage.getItem('sd_role') || '')

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function login(user, password) {
    const { data } = await api.post('/auth/login', { username: user, password })
    token.value = data.access_token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('sd_token', data.access_token)
    localStorage.setItem('sd_user', data.username)
    localStorage.setItem('sd_role', data.role)
    return data
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('sd_token')
    localStorage.removeItem('sd_user')
    localStorage.removeItem('sd_role')
  }

  return { token, username, role, isAuthenticated, isAdmin, login, logout }
})
