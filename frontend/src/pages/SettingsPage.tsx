import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui'
import { useAuthStore } from '@/stores'
import { useToast } from '@/components/ui/toaster'
import apiClient from '@/lib/api'
import { Save, User, Bell, BellOff } from 'lucide-react'

export function SettingsPage() {
  const { user, setUser } = useAuthStore()
  const { toast } = useToast()

  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [saving, setSaving] = useState(false)

  // Notification prefs (local state — would normally come from API)
  const [notifyApproval, setNotifyApproval] = useState(true)
  const [notifyTask, setNotifyTask] = useState(true)

  const handleSaveProfile = async () => {
    setSaving(true)
    try {
      const res = await apiClient.patch(`/users/${user?.id}`, {
        display_name: displayName,
        email,
      })
      setUser(res.data)
      toast('个人信息已保存', 'success')
    } catch {
      toast('保存失败', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <h1 className="text-2xl font-bold">设置</h1>

          {/* Profile Section */}
          <div className="border rounded-lg p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <User className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-lg font-semibold">个人信息</h2>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">显示名称</label>
                <input
                  className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">邮箱</label>
                <input
                  type="email"
                  className="w-full px-3 py-2 rounded-md border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">角色</label>
                <p className="text-sm text-muted-foreground px-3 py-2 bg-muted rounded-md">
                  {user?.role ?? '—'}
                </p>
              </div>
            </div>

            <Button
              className="gap-1.5"
              onClick={handleSaveProfile}
              disabled={saving}
            >
              <Save className="h-4 w-4" />
              {saving ? '保存中...' : '保存'}
            </Button>
          </div>

          {/* Notification Section */}
          <div className="border rounded-lg p-6 space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Bell className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-lg font-semibold">通知偏好</h2>
            </div>

            <div className="space-y-3">
              <label className="flex items-center justify-between">
                <span className="text-sm">审批请求通知</span>
                <button
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${notifyApproval ? 'bg-primary' : 'bg-muted'}`}
                  onClick={() => setNotifyApproval(!notifyApproval)}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${notifyApproval ? 'translate-x-6' : 'translate-x-1'}`}
                  />
                </button>
              </label>
              <label className="flex items-center justify-between">
                <span className="text-sm">任务完成通知</span>
                <button
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${notifyTask ? 'bg-primary' : 'bg-muted'}`}
                  onClick={() => setNotifyTask(!notifyTask)}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${notifyTask ? 'translate-x-6' : 'translate-x-1'}`}
                  />
                </button>
              </label>
            </div>

            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <BellOff className="h-3 w-3" />
              通知偏好将在下次登录后生效
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
