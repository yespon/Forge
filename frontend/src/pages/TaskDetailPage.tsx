import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from '@tanstack/react-router'
import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui'
import apiClient from '@/lib/api'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  FileText,
} from 'lucide-react'

interface TaskDetail {
  id: string
  prompt: string
  status: string
  type: string
  priority: number
  progress: number
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  result_summary: string | null
  error_message: string | null
  stream_url: string
  artifacts_url: string
}

interface ArtifactItem {
  name: string
  url: string
  [key: string]: unknown
}

export function TaskDetailPage() {
  const { taskId } = useParams({ from: '/tasks/$taskId' })
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: task, isLoading } = useQuery<TaskDetail>({
    queryKey: ['task', taskId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/tasks/${taskId}`)
      return res.data
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ['running', 'pending', 'queued'].includes(status) ? 3000 : false
    },
  })

  const { data: artifacts } = useQuery<{ items: ArtifactItem[] }>({
    queryKey: ['task-artifacts', taskId],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/tasks/${taskId}/artifacts`)
      return res.data
    },
    enabled: !!task,
  })

  const cancelMutation = useMutation({
    mutationFn: () => apiClient.post(`/api/v1/tasks/${taskId}/cancel`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['task', taskId] }),
  })

  // SSE streaming for running tasks
  const [streamContent, setStreamContent] = useState<string[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!task || !['running', 'pending', 'queued'].includes(task.status)) {
      return
    }

    const token = localStorage.getItem('auth_token')
    const baseUrl = apiClient.defaults.baseURL || ''
    const url = `${baseUrl}/api/v1/tasks/${taskId}/stream${token ? `?token=${token}` : ''}`

    const es = new EventSource(url)
    eventSourceRef.current = es

    es.addEventListener('content', (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.content) {
          setStreamContent((prev) => [...prev, data.content])
        }
      } catch { /* ignore parse errors */ }
    })

    es.addEventListener('done', () => {
      es.close()
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
    })

    es.addEventListener('error', () => {
      es.close()
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
    })

    es.onerror = () => {
      es.close()
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [task?.status, taskId, queryClient])

  if (isLoading) {
    return (
      <div className="flex flex-col h-screen bg-background">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="flex flex-col h-screen bg-background">
        <Header />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-muted-foreground">任务未找到</p>
        </div>
      </div>
    )
  }

  const statusConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
    pending: { icon: <Clock className="h-5 w-5" />, label: '等待中', color: 'text-yellow-500' },
    queued: { icon: <Clock className="h-5 w-5" />, label: '排队中', color: 'text-blue-500' },
    running: { icon: <Loader2 className="h-5 w-5 animate-spin" />, label: '运行中', color: 'text-blue-500' },
    completed: { icon: <CheckCircle className="h-5 w-5" />, label: '已完成', color: 'text-green-500' },
    failed: { icon: <XCircle className="h-5 w-5" />, label: '失败', color: 'text-red-500' },
    cancelled: { icon: <XCircle className="h-5 w-5" />, label: '已取消', color: 'text-gray-400' },
  }

  const sc = statusConfig[task.status] || statusConfig.pending

  return (
    <div className="flex flex-col h-screen bg-background">
      <Header />
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl mx-auto">
          {/* Back button */}
          <Button
            variant="ghost"
            size="sm"
            className="mb-4"
            onClick={() => navigate({ to: '/tasks' })}
          >
            <ArrowLeft className="h-4 w-4 mr-1" /> 返回任务列表
          </Button>

          {/* Task header */}
          <div className="border rounded-lg p-6 mb-4">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h1 className="text-xl font-bold mb-2">{task.prompt}</h1>
                <div className={`flex items-center gap-2 ${sc.color}`}>
                  {sc.icon}
                  <span className="font-medium">{sc.label}</span>
                  {task.progress > 0 && task.progress < 100 && (
                    <span className="text-sm text-muted-foreground">({task.progress}%)</span>
                  )}
                </div>
              </div>
              {['pending', 'queued', 'running'].includes(task.status) && (
                <Button
                  variant="outline"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                >
                  取消任务
                </Button>
              )}
            </div>

            {/* Progress bar */}
            {task.progress > 0 && (
              <div className="w-full bg-muted rounded-full h-2 mb-4">
                <div
                  className="bg-primary rounded-full h-2 transition-all"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
            )}

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">类型：</span>
                {task.type}
              </div>
              <div>
                <span className="text-muted-foreground">优先级：</span>
                {task.priority === 0 ? '紧急' : task.priority === 1 ? '普通' : '后台'}
              </div>
              {task.created_at && (
                <div>
                  <span className="text-muted-foreground">创建：</span>
                  {new Date(task.created_at).toLocaleString('zh-CN')}
                </div>
              )}
              {task.completed_at && (
                <div>
                  <span className="text-muted-foreground">完成：</span>
                  {new Date(task.completed_at).toLocaleString('zh-CN')}
                </div>
              )}
            </div>
          </div>

          {/* Live streaming output */}
          {streamContent.length > 0 && (
            <div className="border rounded-lg p-4 mb-4 bg-muted/30">
              <h3 className="font-medium mb-2 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                实时输出
              </h3>
              <pre className="text-sm whitespace-pre-wrap font-mono max-h-96 overflow-auto">
                {streamContent.join('')}
              </pre>
            </div>
          )}

          {/* Result / Error */}
          {task.result_summary && (
            <div className="border rounded-lg p-4 mb-4 bg-green-50 dark:bg-green-950">
              <h3 className="font-medium mb-2 text-green-700 dark:text-green-300">执行结果</h3>
              <p className="text-sm whitespace-pre-wrap">{task.result_summary}</p>
            </div>
          )}

          {task.error_message && (
            <div className="border rounded-lg p-4 mb-4 bg-red-50 dark:bg-red-950">
              <h3 className="font-medium mb-2 text-red-700 dark:text-red-300">错误信息</h3>
              <p className="text-sm whitespace-pre-wrap">{task.error_message}</p>
            </div>
          )}

          {/* Artifacts */}
          {artifacts?.items && artifacts.items.length > 0 && (
            <div className="border rounded-lg p-4">
              <h3 className="font-medium mb-3">产出文件</h3>
              <div className="space-y-2">
                {artifacts.items.map((artifact, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 p-2 border rounded hover:bg-accent/50"
                  >
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">{artifact.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
