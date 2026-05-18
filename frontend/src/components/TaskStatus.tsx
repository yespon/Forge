import { useChatStore } from '@/stores/chatStore'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'
import type { TaskStatus, TaskEvent } from '@/types'

function useStatusConfig() {
  const { t } = useTranslation()
  return {
    pending: { label: t('task.status_pending'), variant: 'secondary' as const },
    queued: { label: t('task.status_queued'), variant: 'secondary' as const },
    running: { label: t('task.status_running'), variant: 'default' as const },
    waiting_hitl: { label: t('task.status_waiting_hitl'), variant: 'outline' as const },
    completed: { label: t('task.status_completed'), variant: 'default' as const },
    failed: { label: t('task.status_failed'), variant: 'destructive' as const },
    cancelled: { label: t('task.status_cancelled'), variant: 'secondary' as const },
  }
}

function useEventTypeLabels() {
  const { t } = useTranslation()
  return {
    task_created: t('task.event_task_created'),
    task_queued: t('task.event_task_queued'),
    task_started: t('task.event_task_started'),
    planning_started: t('task.event_planning_started'),
    planning_completed: t('task.event_planning_completed'),
    step_started: t('task.event_step_started'),
    step_completed: t('task.event_step_completed'),
    step_failed: t('task.event_step_failed'),
    tool_calling: t('task.event_tool_calling'),
    tool_result: t('task.event_tool_result'),
    hitl_required: t('task.event_hitl_required'),
    hitl_resolved: t('task.event_hitl_resolved'),
    task_completed: t('task.event_task_completed'),
    task_failed: t('task.event_task_failed'),
    task_cancelled: t('task.event_task_cancelled'),
  } as Record<string, string>
}

export function TaskStatusPanel() {
  const { currentTaskId, currentTaskStatus, currentTaskProgress, taskEvents } = useChatStore()
  const { t, i18n } = useTranslation()
  const statusConfig = useStatusConfig()
  const eventTypeLabels = useEventTypeLabels()

  if (!currentTaskId) return null

  const status = currentTaskStatus ? statusConfig[currentTaskStatus] : null

  return (
    <div className="border rounded-lg p-4 mb-4 bg-card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">{t('task.task_label')}</span>
          <span className="text-sm font-mono">{currentTaskId.slice(0, 8)}</span>
        </div>
        {status && (
          <Badge variant={status.variant}>{status.label}</Badge>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-muted-foreground mb-1">
          <span>{t('task.progress')}</span>
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
          <h4 className="text-xs font-medium text-muted-foreground mb-2">{t('task.execution_log')}</h4>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {taskEvents.slice(-5).map((event, index) => (
              <TaskEventItem key={`${event.id}-${index}`} event={event} eventTypeLabels={eventTypeLabels} locale={i18n.language} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TaskEventItem({ event, eventTypeLabels, locale }: { event: TaskEvent; eventTypeLabels: Record<string, string>; locale: string }) {
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
        {new Date(event.created_at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })}
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
