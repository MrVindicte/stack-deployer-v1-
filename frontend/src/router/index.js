import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { auth: true },
  },
  {
    path: '/stacks',
    name: 'Stacks',
    component: () => import('@/views/StackCatalog.vue'),
    meta: { auth: true },
  },
  {
    path: '/stacks/:slug',
    name: 'StackDetail',
    component: () => import('@/views/StackDetail.vue'),
    meta: { auth: true },
    props: true,
  },
  {
    path: '/deployments',
    name: 'Deployments',
    component: () => import('@/views/DeploymentList.vue'),
    meta: { auth: true },
  },
  {
    path: '/deployments/:id',
    name: 'DeploymentDetail',
    component: () => import('@/views/DeploymentDetail.vue'),
    meta: { auth: true },
    props: true,
  },
  {
    path: '/infra',
    name: 'Infrastructure',
    component: () => import('@/views/InfraView.vue'),
    meta: { auth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = sessionStorage.getItem('sd_token')
  if (to.meta.auth && !token) return next('/login')
  if (to.meta.guest && token) return next('/')
  next()
})

export default router
