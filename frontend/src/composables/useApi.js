import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Inject JWT token
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('sd_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle 401 → redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      sessionStorage.removeItem('sd_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
