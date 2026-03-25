import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/composables/useApi'

export const useDeploymentsStore = defineStore('deployments', () => {
  const deployments = ref([])
  const current = ref(null)
  const logs = ref([])
  const loading = ref(false)
  const deploying = ref(false)
  const error = ref(null)

  async function fetchDeployments() {
    loading.value = true
    try {
      const { data } = await api.get('/deployments/')
      deployments.value = data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Erreur'
    } finally {
      loading.value = false
    }
  }

  async function fetchDeployment(id) {
    loading.value = true
    try {
      const { data } = await api.get(`/deployments/${id}`)
      current.value = data
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Introuvable'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchLogs(id) {
    try {
      const { data } = await api.get(`/deployments/${id}/logs`)
      logs.value = data
      return data
    } catch (e) {
      return []
    }
  }

  async function deploy(payload) {
    deploying.value = true
    error.value = null
    try {
      const { data } = await api.post('/deployments/', payload)
      deployments.value.unshift(data)
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Échec du déploiement'
      throw e
    } finally {
      deploying.value = false
    }
  }

  async function stopDeployment(id) {
    await api.post(`/deployments/${id}/stop`)
    await fetchDeployment(id)
  }

  async function destroyDeployment(id) {
    await api.delete(`/deployments/${id}`)
    deployments.value = deployments.value.filter(d => d.id !== id)
    current.value = null
  }

  return {
    deployments, current, logs, loading, deploying, error,
    fetchDeployments, fetchDeployment, fetchLogs, deploy,
    stopDeployment, destroyDeployment,
  }
})
