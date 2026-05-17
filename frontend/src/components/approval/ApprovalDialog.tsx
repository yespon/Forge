import { useState } from 'react'
import { Shield, AlertTriangle, Check, X, Clock, User } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  Button,
  Badge,
  Textarea,
  Alert,
  AlertDescription,
  Separator,
} from '@/components/ui'
import { cn } from '@/lib/utils'
import type { ApprovalListItem, RiskLevel } from '@/types'

interface ApprovalDialogProps {
  approval: ApprovalListItem | null
  isOpen: boolean
  onClose: () => void
  onApprove: (id: string, reason?: string) => void
  onReject: (id: string, reason?: string) => void
  isLoading?: boolean
}

const riskLevelConfig: Record<
  RiskLevel,
  { color: string; bg: string; label: string; icon: typeof AlertTriangle }
> = {
  low: {
    color: 'text-green-600',
    bg: 'bg-green-500/10',
    label: '低风险',
    icon: Shield,
  },
  medium: {
    color: 'text-yellow-600',
    bg: 'bg-yellow-500/10',
    label: '中等风险',
    icon: Shield,
  },
  high: {
    color: 'text-orange-600',
    bg: 'bg-orange-500/10',
    label: '高风险',
    icon: AlertTriangle,
  },
  critical: {
    color: 'text-red-600',
    bg: 'bg-red-500/10',
    label: '严重风险',
    icon: AlertTriangle,
  },
}

export function ApprovalDialog({
  approval,
  isOpen,
  onClose,
  onApprove,
  onReject,
  isLoading = false,
}: ApprovalDialogProps) {
  const [reason, setReason] = useState('')
  const [action, setAction] = useState<'approve' | 'reject' | null>(null)

  if (!approval) return null

  const riskConfig = riskLevelConfig[approval.risk_level]
  const RiskIcon = riskConfig.icon

  const handleApprove = () => {
    if (approval) {
      onApprove(approval.id, reason)
      setReason('')
      setAction(null)
    }
  }

  const handleReject = () => {
    if (approval) {
      onReject(approval.id, reason)
      setReason('')
      setAction(null)
    }
  }

  const expiresAt = new Date(approval.expires_at)
  const isExpired = approval.is_expired || expiresAt < new Date()

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            审批请求
          </DialogTitle>
          <DialogDescription>
            请审核以下工具调用请求，确认是否批准执行
          </DialogDescription>
        </DialogHeader>

        {/* Risk Level */}
        <div
          className={cn(
            'flex items-center gap-3 p-3 rounded-lg',
            riskConfig.bg
          )}
        >
          <div className={cn('p-2 rounded-full bg-white/50', riskConfig.color)}>
            <RiskIcon className="h-5 w-5" />
          </div>
          <div>
            <p className={cn('font-medium', riskConfig.color)}>
              {riskConfig.label}
            </p>
            <p className="text-sm text-muted-foreground">
              此操作被标记为{riskConfig.label}，需要审批后执行
            </p>
          </div>
        </div>

        {isExpired && (
          <Alert variant="destructive">
            <AlertDescription>此审批请求已过期</AlertDescription>
          </Alert>
        )}

        {/* Tool Info */}
        <div className="space-y-3">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              工具名称
            </p>
            <p className="text-lg font-semibold">{approval.tool_name}</p>
          </div>

          {approval.description && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                描述
              </p>
              <p className="text-sm">{approval.description}</p>
            </div>
          )}

          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>请求时间: {new Date(approval.requested_at).toLocaleString('zh-CN')}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              <Check className="h-3 w-3 mr-1" />
              {approval.approval_count} 批准
            </Badge>
            <Badge variant="destructive">
              <X className="h-3 w-3 mr-1" />
              {approval.rejection_count} 拒绝
            </Badge>
          </div>
        </div>

        <Separator />

        {/* Reason Input */}
        <div className="space-y-2">
          <label className="text-sm font-medium">
            审批意见（可选）
          </label>
          <Textarea
            placeholder="输入您的审批意见..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="min-h-[80px]"
            disabled={isLoading || isExpired}
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
          >
            取消
          </Button>
          <Button
            variant="outline"
            onClick={handleReject}
            disabled={isLoading || isExpired}
            className="gap-2 border-red-200 hover:bg-red-50 hover:text-red-600"
          >
            {isLoading && action === 'reject' ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <X className="h-4 w-4" />
            )}
            拒绝
          </Button>
          <Button
            onClick={handleApprove}
            disabled={isLoading || isExpired}
            className="gap-2"
          >
            {isLoading && action === 'approve' ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            批准
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
