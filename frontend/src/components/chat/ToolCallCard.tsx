import { useState } from 'react'
import { ChevronDown, ChevronUp, Wrench, Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button, Badge } from '@/components/ui'
import type { StreamChunk } from '@/types'

interface ToolCallCardProps {
  toolCall: StreamChunk
  onApprove?: () => void
  onReject?: () => void
  status?: 'pending' | 'running' | 'completed' | 'error'
}

export function ToolCallCard({
  toolCall,
  onApprove,
  onReject,
  status = 'pending',
}: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const statusConfig = {
    pending: {
      icon: null,
      color: 'bg-yellow-500/10 border-yellow-500/30',
      badge: 'bg-yellow-500 text-white',
      label: '等待执行',
    },
    running: {
      icon: null,
      color: 'bg-blue-500/10 border-blue-500/30',
      badge: 'bg-blue-500 text-white',
      label: '执行中',
    },
    completed: {
      icon: Check,
      color: 'bg-green-500/10 border-green-500/30',
      badge: 'bg-green-500 text-white',
      label: '已完成',
    },
    error: {
      icon: X,
      color: 'bg-red-500/10 border-red-500/30',
      badge: 'bg-red-500 text-white',
      label: '出错',
    },
  }

  const config = statusConfig[status]
  const StatusIcon = config.icon

  return (
    <div
      className={cn(
        'rounded-lg border p-3 my-2 transition-all',
        config.color,
        isExpanded && 'ring-2 ring-primary/20'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-full bg-background flex items-center justify-center">
            <Wrench className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-medium">
              {toolCall.tool_name || '工具调用'}
            </p>
            <Badge className={cn('text-xs mt-0.5', config.badge)}>
              {config.label}
            </Badge>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {status === 'pending' && onApprove && onReject && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={onReject}
                className="h-8 px-2"
              >
                <X className="h-3 w-3 mr-1" />
                拒绝
              </Button>
              <Button
                size="sm"
                onClick={onApprove}
                className="h-8 px-2"
              >
                <Check className="h-3 w-3 mr-1" />
                批准
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 w-8 p-0"
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t space-y-2">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">
              输入参数
            </p>
            <pre className="text-xs bg-background/80 p-2 rounded overflow-x-auto">
              {JSON.stringify(toolCall.tool_input || {}, null, 2)}
            </pre>
          </div>

          {toolCall.tool_output && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">
                输出结果
              </p>
              <pre className="text-xs bg-background/80 p-2 rounded overflow-x-auto">
                {toolCall.tool_output}
              </pre>
            </div>
          )}

          {toolCall.error && (
            <div>
              <p className="text-xs font-medium text-red-500 mb-1">
                错误信息
              </p>
              <p className="text-xs text-red-600 bg-red-50 p-2 rounded">
                {toolCall.error}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
