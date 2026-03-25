import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/composables/useApi'

export const useStacksStore = defineStore('stacks', () => {
  const stacks = ref([])
  const currentStack = ref(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchStacks() {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get('/stacks/')
      stacks.value = data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Erreur de chargement'
    } finally {
      loading.value = false
    }
  }

  async function fetchStack(slug) {
    loading.value = true
    error.value = null
    try {
      const { data } = await api.get(`/stacks/${slug}`)
      currentStack.value = data
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Stack introuvable'
      return null
    } finally {
      loading.value = false
    }
  }

  return { stacks, currentStack, loading, error, fetchStacks, fetchStack }
})
