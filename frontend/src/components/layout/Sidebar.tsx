import { useState } from 'react'
import {
  Plus,
  MessageSquare,
  MoreVertical,
  Trash2,
  Power,
  Settings,
  History,
  Loader2,
  Cpu,
  BookOpen,
  Brain,
  Server,
} from 'lucide-react'
import { useSessionStore } from '@/stores'
import {
  Button,
  ScrollArea,
  Separator,
  Badge,
  Skeleton,
} from '@/components/ui'
import { useNavigate } from '@tanstack/react-router'
import { cn, formatRelativeTime, truncateText } from '@/lib/utils'
import type { Session } from '@/types'

interface SidebarProps {
  onSelectSession?: (session: Session) => void
  onCreateSession?: () => void
}

export function Sidebar({ onSelectSession, onCreateSession }: SidebarProps) {
  const {
    sessions,
    currentSession,
    isLoading,
    fetchSessions,
    deleteSession,
    terminateSession,
    setCurrentSession,
  } = useSessionStore()

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSelectSession = (session: Session) => {
    setCurrentSession(session)
    onSelectSession?.(session)
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setDeletingId(id)
    try {
      await deleteSession(id)
    } finally {
      setDeletingId(null)
    }
  }

  const handleTerminate = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setTerminatingId(id)
    try {
      await terminateSession(id)
    } finally {
      setTerminatingId(null)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'paused':
        return 'bg-yellow-500'
      case 'error':
        return 'bg-red-500'
      case 'terminated':
        return 'bg-gray-400'
      default:
        return 'bg-gray-400'
    }
  }

  return (
    <div className="flex flex-col h-full w-64 border-r bg-muted/30">
      {/* Header */}
      <div className="p-4 border-b">
        <Button
          onClick={onCreateSession}
          className="w-full gap-2"
          variant="default"
        >
          <Plus className="h-4 w-4" />
          新建会话
        </Button>
      </div>

      {/* Navigation */}
      <div className="p-2 space-y-1">
        <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => navigate({ to: '/' })}>
          <MessageSquare className="h-4 w-4" />
          当前会话
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => navigate({ to: '/models' })}>
          <Cpu className="h-4 w-4" />
          模型管理
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => navigate({ to: '/skills' })}>
          <BookOpen className="h-4 w-4" />
          技能市场
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => navigate({ to: '/memory' })}>
          <Brain className="h-4 w-4" />
          记忆管理
        </Button>
        <Button variant="ghost" className="w-full justify-start gap-2" onClick={() => navigate({ to: '/mcp' })}>
          <Server className="h-4 w-4" />
          MCP 服务器
        </Button>
      </div>

      <Separator />

      {/* Session List */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无会话</p>
              <p className="text-xs mt-1">点击上方按钮创建新会话</p>
            </div>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session)}
                className={cn(
                  'group relative p-3 rounded-lg cursor-pointer transition-colors',
                  currentSession?.id === session.id
                    ? 'bg-primary/10 border-l-2 border-primary'
                    : 'hover:bg-muted border-l-2 border-transparent'
                )}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={cn(
                      'mt-1.5 h-2 w-2 rounded-full shrink-0',
                      getStatusColor(session.status)
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">
                      {truncateText(session.name, 20)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatRelativeTime(session.last_activity_at)}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    {session.status !== 'terminated' && (
                      <button
                        onClick={(e) => handleTerminate(session.id, e)}
                        className="p-1 hover:bg-muted-foreground/20 rounded"
                        title="终止会话"
                        disabled={terminatingId === session.id}
                      >
                        {terminatingId === session.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Power className="h-3 w-3 text-yellow-600" />
                        )}
                      </button>
                    )}
                    <button
                      onClick={(e) => handleDelete(session.id, e)}
                      className="p-1 hover:bg-muted-foreground/20 rounded"
                      title="删除会话"
                      disabled={deletingId === session.id}
                    >
                      {deletingId === session.id ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Trash2 className="h-3 w-3 text-red-600" />
                      )}
                    </button>
                  </div>
                </div>

                {session.description && (
                  <p className="text-xs text-muted-foreground mt-1 truncate">
                    {session.description}
                  </p>
                )}

                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="secondary" className="text-xs">
                    {session.model}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {session.message_count} 消息
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
