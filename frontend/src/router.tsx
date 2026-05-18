import {
  createRouter,
  createRoute,
  createRootRoute,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import i18next from 'i18next'
import { getAccessToken } from '@/lib/api'

// Pages
import { LoginPage } from '@/pages/LoginPage'
import { WorkspacePage } from '@/pages/WorkspacePage'
import { TasksPage } from '@/pages/TasksPage'
import { TaskDetailPage } from '@/pages/TaskDetailPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AdminPage } from '@/pages/AdminPage'
import { ModelsPage } from '@/pages/ModelsPage'
import { MemoryPage } from '@/pages/MemoryPage'
import { MCPPage } from '@/pages/MCPPage'

// Root layout — just renders child routes
const rootRoute = createRootRoute({
  component: () => <Outlet />,
})

// Public: login
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
})

// Auth guard helper
function requireAuth() {
  const token = getAccessToken()
  if (!token) {
    throw redirect({ to: '/login' })
  }
}

// Protected: workspace / chat (default page)
const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: requireAuth,
  component: WorkspacePage,
})

// Protected: tasks list
const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/tasks',
  beforeLoad: requireAuth,
  component: TasksPage,
})

// Protected: task detail
const taskDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/tasks/$taskId',
  beforeLoad: requireAuth,
  component: TaskDetailPage,
})

// Protected: settings
const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  beforeLoad: requireAuth,
  component: SettingsPage,
})

// Protected: models
const modelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/models',
  beforeLoad: requireAuth,
  component: ModelsPage,
})

// Protected: memory
const memoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/memory',
  beforeLoad: requireAuth,
  component: MemoryPage,
})

// Protected: mcp
const mcpRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/mcp',
  beforeLoad: requireAuth,
  component: MCPPage,
})

// Protected: admin
const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin',
  beforeLoad: requireAuth,
  component: AdminPage,
})

// Build route tree
const routeTree = rootRoute.addChildren([
  loginRoute,
  workspaceRoute,
  tasksRoute,
  taskDetailRoute,
  skillsRoute,
  modelsRoute,
  memoryRoute,
  mcpRoute,
  settingsRoute,
  adminRoute,
])

// Create router instance
export const router = createRouter({
  routeTree,
  defaultNotFoundComponent: () => (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">404</h1>
        <p className="text-muted-foreground">{i18next.t('error.not_found')}</p>
      </div>
    </div>
  ),
})

// Type registration for type-safe navigation
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
