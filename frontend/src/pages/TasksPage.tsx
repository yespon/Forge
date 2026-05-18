import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Header } from '@/components/layout/Header'
import { Loader2, Play, CheckCircle, XCircle, Clock, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui'
import apiClient from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

interface TaskItem {
  id: string
  prompt: string
  status: string
  type: string
  priority: number
  progress: number
  created_at: string | null
  completed_at: string | null
  result_summary: string | null
  error_message: string | null
}

interface TaskListResponse {
  items: TaskItem[]
  total: number
  page: number
  page_size: number
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending: <Clock className="h-4 w-4 text-yellow-500" />,
  queued: <Clock className="h-4 w-4 text-blue-500" />,
  running: <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />,
  completed: <CheckCircle className="h-4 w-4 text-green-500" />,
  failed: <XCircle className="h-4 w-4 text-red-500" />,
  cancelled: <XCircle className="h-4 w-4 text-gray-400" />,
}

const STATUS_LABELS: Record<string, string> = {}

function useStatusLabels() {
  const { t } = useTranslation()
  return {
    pending: t('task.status_pending'),
    queued: t('task.status_queued'),
    running: t('task.status_running'),
    waiting_hitl: t('task.status_waiting_hitl'),
    completed: t('task.status_completed'),
    failed: t('task.status_failed'),
    cancelled: t('task.status_cancelled'),
  }
}

export function TasksPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery<TaskListResponse>({
    queryKey: ['tasks', statusFilter, page],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), page_size: '20' })
      if (statusFilter) params.set('status', statusFilter)
      const res = await apiClient.get(`/api/v1/tasks?${params}`)
      return res.data
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) => apiClient.post(`/api/v1/tasks/${taskId}/cancel`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => apiClient.delete(`/api/v1/tasks/${taskId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const statusLabels = useStatusLabels()

  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold">{t('task.title')}</h1>
            <div className="flex gap-2">
              {['', 'pending', 'running', 'completed', 'failed'].map((s) => (
                <Button
                  key={s}
                  variant={statusFilter === s ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => { setStatusFilter(s); setPage(1) }}
                >
                  {s ? statusLabels[s as keyof typeof statusLabels] || s : t('common.all')}
                </Button>
              ))}
            </div>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : !data?.items.length ? (
            <div className="text-center py-12 text-muted-foreground">{t('task.no_tasks')}</div>
          ) : (
            <>
              <div className="space-y-2">
                {data.items.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center gap-4 p-4 border rounded-lg hover:bg-accent/50 cursor-pointer transition-colors"
                    onClick={() => navigate({ to: '/tasks/$taskId', params: { taskId: task.id } })}
                  >
                    <div className="flex-shrink-0">
                      {STATUS_ICONS[task.status] || <Clock className="h-4 w-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{task.prompt}</p>
                      <p className="text-sm text-muted-foreground">
                        {statusLabels[task.status as keyof typeof statusLabels] || task.status}
                        {task.progress > 0 && task.progress < 100 && ` · ${task.progress}%`}
                        {task.created_at && ` · ${new Date(task.created_at).toLocaleString()}`}
                      </p>
                    </div>
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      {['pending', 'queued', 'running'].includes(task.status) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => cancelMutation.mutate(task.id)}
                        >
                          {t('common.cancel')}
                        </Button>
                      )}
                      {['completed', 'failed', 'cancelled'].includes(task.status) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteMutation.mutate(task.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {data.total > data.page_size && (
                <div className="flex justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    {t('common.prev_page')}
                  </Button>
                  <span className="flex items-center text-sm text-muted-foreground">
                    {page} / {Math.ceil(data.total / data.page_size)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= Math.ceil(data.total / data.page_size)}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    {t('common.next_page')}
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
