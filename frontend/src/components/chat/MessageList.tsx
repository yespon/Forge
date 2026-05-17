import { useEffect, useRef } from 'react'
import { Bot, User, Wrench } from 'lucide-react'
import { useChatStore } from '@/stores'
import { ScrollArea } from '@/components/ui'
import { cn, formatDate } from '@/lib/utils'
import type { Message } from '@/types'

interface MessageItemProps {
  message: Message
  isStreaming?: boolean
}

function MessageItem({ message, isStreaming }: MessageItemProps) {
  const isUser = message.role === 'user'
  const isToolCall = message.tool_calls && message.tool_calls.length > 0

  return (
    <div
      className={cn(
        'message-enter py-4',
        isUser ? 'bg-primary/5' : 'bg-background'
      )}
    >
      <div className="max-w-3xl mx-auto px-4 flex gap-4">
        {/* Avatar */}
        <div
          className={cn(
            'shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted text-muted-foreground'
          )}
        >
          {isUser ? (
            <User className="h-5 w-5" />
          ) : (
            <Bot className="h-5 w-5" />
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">
              {isUser ? '你' : 'AI 助手'}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatDate(message.created_at)}
            </span>
          </div>

          <div
            className={cn(
              'text-sm leading-relaxed whitespace-pre-wrap',
              isUser && 'text-primary-foreground'
            )}
          >
            {message.content}
          </div>

          {/* Tool Calls */}
          {isToolCall && (
            <div className="mt-3 space-y-2">
              {message.tool_calls?.map((tool) => (
                <div
                  key={tool.id}
                  className="bg-muted rounded-lg p-3 border"
                >
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                    <Wrench className="h-3 w-3" />
                    <span>工具调用: {tool.function.name}</span>
                  </div>
                  <pre className="text-xs bg-background p-2 rounded overflow-x-auto">
                    {JSON.stringify(
                      JSON.parse(tool.function.arguments),
                      null,
                      2
                    )}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

interface StreamingMessageProps {
  content: string
}

function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className="message-enter py-4 bg-background">
      <div className="max-w-3xl mx-auto px-4 flex gap-4">
        <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-muted text-muted-foreground">
          <Bot className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-sm">AI 助手</span>
            <span className="text-xs text-muted-foreground">思考中...</span>
          </div>
          <div className="text-sm leading-relaxed whitespace-pre-wrap streaming-cursor">
            {content}
          </div>
        </div>
      </div>
    </div>
  )
}

interface MessageListProps {
  sessionId: string
}

export function MessageList({ sessionId }: MessageListProps) {
  const { messages, isLoading, isStreaming, streamingContent, fetchHistory } =
    useChatStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (sessionId) {
      fetchHistory(sessionId)
    }
  }, [sessionId, fetchHistory])

  useEffect(() => {
    // Scroll to bottom when messages change
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  return (
    <ScrollArea className="flex-1" ref={scrollRef}>
      <div className="min-h-full">
        {messages.length === 0 && !isLoading ? (
          <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-muted-foreground">
            <Bot className="h-12 w-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">开始新的对话</p>
            <p className="text-sm mt-2">发送消息与 AI 助手开始对话</p>
          </div>
        ) : (
          <>
            {messages.map((message, index) => (
              <MessageItem
                key={`${message.id}-${index}`}
                message={message}
                isStreaming={
                  isStreaming && index === messages.length - 1
                }
              />
            ))}
            {isStreaming && streamingContent && (
              <StreamingMessage content={streamingContent} />
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
