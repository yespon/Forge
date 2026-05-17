import { useEffect } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { MessageList } from './MessageList'
import { InputArea } from './InputArea'
import { ToolCallCard } from './ToolCallCard'
import { useChatStore, useSessionStore } from '@/stores'
import { Alert, AlertDescription, Button, ScrollArea } from '@/components/ui'
import { cn } from '@/lib/utils'

interface ChatPanelProps {
  sessionId?: string
}

export function ChatPanel({ sessionId }: ChatPanelProps) {
  const { currentSession } = useSessionStore()
  const {
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    currentToolCall,
    error,
    streamMessage,
    clearError,
    reset,
  } = useChatStore()

  const activeSessionId = sessionId || currentSession?.id

  useEffect(() => {
    return () => {
      reset()
    }
  }, [reset])

  const handleSend = async (content: string) => {
    if (!activeSessionId) return
    await streamMessage(activeSessionId, content)
  }

  if (!activeSessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-muted/30">
        <div className="text-center">
          <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="h-8 w-8 text-primary" />
          </div>
          <h3 className="text-lg font-medium mb-2">选择一个会话</h3>
          <p className="text-muted-foreground text-sm">
            从左侧边栏选择一个会话，或创建新会话开始对话
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Session Header */}
      <div className="border-b bg-background px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div>
            <h2 className="font-semibold">{currentSession?.name}</h2>
            <p className="text-xs text-muted-foreground">
              {currentSession?.model} • {currentSession?.message_count} 消息
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={cn(
                'h-2 w-2 rounded-full',
                currentSession?.status === 'active' && 'bg-green-500',
                currentSession?.status === 'paused' && 'bg-yellow-500',
                currentSession?.status === 'error' && 'bg-red-500',
                currentSession?.status === 'terminated' && 'bg-gray-400'
              )}
            />
            <span className="text-xs text-muted-foreground capitalize">
              {currentSession?.status}
            </span>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive" className="m-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={clearError}
              className="h-6 px-2"
            >
              关闭
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-hidden">
        <MessageList sessionId={activeSessionId} />
      </div>

      {/* Current Tool Call */}
      {currentToolCall && (
        <div className="border-t bg-muted/30 px-4 py-2">
          <div className="max-w-3xl mx-auto">
            <ToolCallCard toolCall={currentToolCall} status="running" />
          </div>
        </div>
      )}

      {/* Input */}
      <InputArea
        onSend={handleSend}
        isLoading={isLoading || isStreaming}
        disabled={currentSession?.status === 'terminated'}
        placeholder={
          currentSession?.status === 'terminated'
            ? '会话已终止，无法发送消息'
            : isStreaming
              ? 'AI 正在回复...'
              : '输入消息...'
        }
      />
    </div>
  )
}
