import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui'
import { useToast } from '@/components/ui/toaster'
import apiClient from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Users, Shield, FileText, Plug, Trash2 } from 'lucide-react'

interface AuditLogEntry {
  id: string
  timestamp: string
  action: string
  resource_type: string
  user_id: string | null
  details: Record<string, unknown>
  success: boolean | null
}

interface AuditLogResponse {
  items: AuditLogEntry[]
  total: number
  limit: number
  offset: number
}

interface UserItem {
  id: string
  email: string
  display_name: string | null
  role: string
  status: string
  created_at: string | null
}

interface SkillItem {
  name: string
  display_name: string | null
  visibility: string
  is_installed: boolean
}

interface ConnectorItem {
  id: string
  name: string
  display_name: string | null
  auth_type: string
  status: string
}

type Tab = 'audit' | 'users' | 'skills' | 'connectors'

export function AdminPage() {
  const [tab, setTab] = useState<Tab>('audit')
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // --- Queries ---
  const { data: auditLogs, isLoading: auditLoading } = useQuery<AuditLogResponse>({
    queryKey: ['admin-audit'],
    queryFn: async () => (await apiClient.get('/admin/audit-logs?limit=50')).data,
    enabled: tab === 'audit',
  })

  const { data: users = [], isLoading: usersLoading } = useQuery<UserItem[]>({
    queryKey: ['admin-users'],
    queryFn: async () => {
      const res = await apiClient.get('/users?page_size=100')
      return res.data.items ?? res.data
    },
    enabled: tab === 'users',
  })

  const { data: skills = [], isLoading: skillsLoading } = useQuery<SkillItem[]>({
    queryKey: ['admin-skills'],
    queryFn: async () => {
      const res = await apiClient.get('/skills')
      return res.data.items ?? res.data
    },
    enabled: tab === 'skills',
  })

  const { data: connectors = [], isLoading: connectorsLoading } = useQuery<ConnectorItem[]>({
    queryKey: ['admin-connectors'],
    queryFn: async () => {
      const res = await apiClient.get('/connectors')
      return res.data.items ?? res.data
    },
    enabled: tab === 'connectors',
  })

  // --- Mutations ---
  const deleteUser = useMutation({
    mutationFn: async (id: string) => apiClient.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast('用户已删除', 'success')
    },
    onError: () => toast('删除失败', 'error'),
  })

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'audit', label: '审计日志', icon: <FileText className="h-4 w-4" /> },
    { key: 'users', label: '用户管理', icon: <Users className="h-4 w-4" /> },
    { key: 'skills', label: '技能管理', icon: <Shield className="h-4 w-4" /> },
    { key: 'connectors', label: '连接器', icon: <Plug className="h-4 w-4" /> },
  ]

  const roleBadge = (role: string) => {
    const colors: Record<string, string> = {
      platform_admin: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
      org_admin: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      developer: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      viewer: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[role] ?? colors.viewer}`}>
        {role}
      </span>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-bold mb-6">管理后台</h1>

          {/* Tabs */}
          <div className="flex gap-1 mb-6 border-b">
            {tabs.map((t) => (
              <Button
                key={t.key}
                variant={tab === t.key ? 'default' : 'ghost'}
                size="sm"
                className="gap-1.5 rounded-b-none"
                onClick={() => setTab(t.key)}
              >
                {t.icon}
                {t.label}
              </Button>
            ))}
          </div>

          {/* ====== Audit Tab ====== */}
          {tab === 'audit' && (
            <div>
              {auditLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : !auditLogs?.items.length ? (
                <p className="text-center py-12 text-muted-foreground">暂无审计日志</p>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">时间</th>
                        <th className="text-left p-3 font-medium">操作</th>
                        <th className="text-left p-3 font-medium">资源类型</th>
                        <th className="text-left p-3 font-medium">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {auditLogs.items.map((log) => (
                        <tr key={log.id} className="hover:bg-accent/30">
                          <td className="p-3">{new Date(log.timestamp).toLocaleString('zh-CN')}</td>
                          <td className="p-3">
                            <span className="px-2 py-0.5 rounded bg-muted text-xs font-mono">
                              {log.action}
                            </span>
                          </td>
                          <td className="p-3">{log.resource_type}</td>
                          <td className="p-3">
                            {log.success === true && <span className="text-green-600">成功</span>}
                            {log.success === false && <span className="text-red-600">失败</span>}
                            {log.success === null && <span className="text-muted-foreground">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {auditLogs.total > 50 && (
                    <div className="p-3 text-center text-sm text-muted-foreground border-t">
                      显示 {auditLogs.items.length} / {auditLogs.total} 条
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ====== Users Tab ====== */}
          {tab === 'users' && (
            <div>
              {usersLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : users.length === 0 ? (
                <p className="text-center py-12 text-muted-foreground">暂无用户</p>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">用户</th>
                        <th className="text-left p-3 font-medium">邮箱</th>
                        <th className="text-left p-3 font-medium">角色</th>
                        <th className="text-left p-3 font-medium">状态</th>
                        <th className="text-right p-3 font-medium">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {users.map((u) => (
                        <tr key={u.id} className="hover:bg-accent/30">
                          <td className="p-3 font-medium">{u.display_name || '—'}</td>
                          <td className="p-3 text-muted-foreground">{u.email}</td>
                          <td className="p-3">{roleBadge(u.role)}</td>
                          <td className="p-3">
                            <span className={u.status === 'active' ? 'text-green-600' : 'text-muted-foreground'}>
                              {u.status}
                            </span>
                          </td>
                          <td className="p-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700"
                              onClick={() => deleteUser.mutate(u.id)}
                              disabled={deleteUser.isPending}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ====== Skills Tab ====== */}
          {tab === 'skills' && (
            <div>
              {skillsLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : skills.length === 0 ? (
                <p className="text-center py-12 text-muted-foreground">暂无技能</p>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">技能</th>
                        <th className="text-left p-3 font-medium">可见性</th>
                        <th className="text-left p-3 font-medium">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {skills.map((s) => (
                        <tr key={s.name} className="hover:bg-accent/30">
                          <td className="p-3 font-medium">{s.display_name || s.name}</td>
                          <td className="p-3">
                            <span className="px-2 py-0.5 rounded bg-muted text-xs">
                              {s.visibility}
                            </span>
                          </td>
                          <td className="p-3">
                            {s.is_installed ? (
                              <span className="text-green-600 text-xs">已安装</span>
                            ) : (
                              <span className="text-muted-foreground text-xs">未安装</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ====== Connectors Tab ====== */}
          {tab === 'connectors' && (
            <div>
              {connectorsLoading ? (
                <div className="flex justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : connectors.length === 0 ? (
                <p className="text-center py-12 text-muted-foreground">暂无连接器</p>
              ) : (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left p-3 font-medium">名称</th>
                        <th className="text-left p-3 font-medium">认证方式</th>
                        <th className="text-left p-3 font-medium">状态</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {connectors.map((c) => (
                        <tr key={c.id} className="hover:bg-accent/30">
                          <td className="p-3 font-medium">{c.display_name || c.name}</td>
                          <td className="p-3">
                            <span className="px-2 py-0.5 rounded bg-muted text-xs font-mono">
                              {c.auth_type}
                            </span>
                          </td>
                          <td className="p-3">
                            <span className={c.status === 'active' ? 'text-green-600' : 'text-muted-foreground'}>
                              {c.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
