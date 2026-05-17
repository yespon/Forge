import { useChatStore } from '@/stores/chatStore'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { TaskStatus, TaskEvent } from '@/types'

const statusConfig: Record<TaskStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  pending: { label: '等待中', variant: 'secondary' },
  queued: { label: '队列中', variant: 'secondary' },
  running: { label: '执行中', variant: 'default' },
  waiting_hitl: { label: '等待审批', variant: 'outline' },
  completed: { label: '已完成', variant: 'default' },
  failed: { label: '失败', variant: 'destructive' },
  cancelled: { label: '已取消', variant: 'secondary' },
}

const eventTypeLabels: Record<string, string> = {
  task_created: '任务创建',
  task_queued: '进入队列',
  task_started: '开始执行',
  planning_started: '规划开始',
  planning_completed: '规划完成',
  step_started: '步骤开始',
  step_completed: '步骤完成',
  step_failed: '步骤失败',
  tool_calling: '调用工具',
  tool_result: '工具结果',
  hitl_required: '需要审批',
  hitl_resolved: '审批完成',
  task_completed: '任务完成',
  task_failed: '任务失败',
  task_cancelled: '任务取消',
}

export function TaskStatusPanel() {
  const { currentTaskId, currentTaskStatus, currentTaskProgress, taskEvents } = useChatStore()

  if (!currentTaskId) return null

  const status = currentTaskStatus ? statusConfig[currentTaskStatus] : null

  return (
    <div className="border rounded-lg p-4 mb-4 bg-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">任务</span>
          <span className="text-sm font-mono">{currentTaskId.slice(0, 8)}</span>
        </div>
        {status && (
          <Badge variant={status.variant}>{status.label}</Badge>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-muted-foreground mb-1">
          <span>进度</span>
          <span>{currentTaskProgress}%</span>
        </div>
        <div className="h-2 bg-secondary rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-300',
              currentTaskStatus === 'failed' ? 'bg-destructive' :
              currentTaskStatus === 'completed' ? 'bg-green-500' :
              'bg-primary'
            )}
            style={{ width: `${currentTaskProgress}%` }}
          />
        </div>
      </div>

      {/* Event timeline */}
      {taskEvents.length > 0 && (
        <div className="border-t pt-3 mt-3">
          <h4 className="text-xs font-medium text-muted-foreground mb-2">执行记录</h4>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {taskEvents.slice(-5).map((event, index) => (
              <TaskEventItem key={`${event.id}-${index}`} event={event} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TaskEventItem({ event }: { event: TaskEvent }) {
  const label = eventTypeLabels[event.type] || event.type

  return (
    <div className="flex items-start gap-2 text-xs">
      <div className={cn(
        'w-2 h-2 rounded-full mt-0.5 flex-shrink-0',
        event.type.includes('failed') ? 'bg-destructive' :
        event.type.includes('completed') ? 'bg-green-500' :
        'bg-primary'
      )} />
      <div className="flex-1 min-w-0">
        <span className="font-medium">{label}</span>
        {event.message && (
          <p className="text-muted-foreground truncate">{event.message}</p>
        )}
      </div>
      <span className="text-muted-foreground flex-shrink-0">
        {new Date(event.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  )
}

// Compact version for header/toolbar
export function TaskStatusBadge() {
  const { currentTaskId, currentTaskStatus, currentTaskProgress } = useChatStore()

  if (!currentTaskId || !currentTaskStatus) return null

  const status = statusConfig[currentTaskStatus]
  if (!status) return null

  return (
    <div className="flex items-center gap-2">
      <Badge variant={status.variant}>{status.label}</Badge>
      {currentTaskStatus === 'running' && (
        <span className="text-xs text-muted-foreground">{currentTaskProgress}%</span>
      )}
    </div>
  )
}
