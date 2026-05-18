import { useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  { color: string; bg: string; labelKey: string; icon: typeof AlertTriangle }
> = {
  low: {
    color: 'text-green-600',
    bg: 'bg-green-500/10',
    labelKey: 'approval.risk_low',
    icon: Shield,
  },
  medium: {
    color: 'text-yellow-600',
    bg: 'bg-yellow-500/10',
    labelKey: 'approval.risk_medium',
    icon: Shield,
  },
  high: {
    color: 'text-orange-600',
    bg: 'bg-orange-500/10',
    labelKey: 'approval.risk_high',
    icon: AlertTriangle,
  },
  critical: {
    color: 'text-red-600',
    bg: 'bg-red-500/10',
    labelKey: 'approval.risk_critical',
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
  const { t } = useTranslation()

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
            {t('approval.request')}
          </DialogTitle>
          <DialogDescription>
            {t('approval.review_desc')}
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
              {t(riskConfig.labelKey)}
            </p>
            <p className="text-sm text-muted-foreground">
              {t('approval.risk_desc', { level: t(riskConfig.labelKey) })}
            </p>
          </div>
        </div>

        {isExpired && (
          <Alert variant="destructive">
            <AlertDescription>{t('approval.expired')}</AlertDescription>
          </Alert>
        )}

        {/* Tool Info */}
        <div className="space-y-3">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              {t('approval.tool_name')}
            </p>
            <p className="text-lg font-semibold">{approval.tool_name}</p>
          </div>

          {approval.description && (
            <div>
              <p className="text-sm font-medium text-muted-foreground">
                {t('approval.description')}
              </p>
              <p className="text-sm">{approval.description}</p>
            </div>
          )}

          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1 text-muted-foreground">
              <Clock className="h-4 w-4" />
              <span>{new Date(approval.requested_at).toLocaleString()}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              <Check className="h-3 w-3 mr-1" />
              {t('approval.approved_count', { count: approval.approval_count })}
            </Badge>
            <Badge variant="destructive">
              <X className="h-3 w-3 mr-1" />
              {t('approval.rejected_count', { count: approval.rejection_count })}
            </Badge>
          </div>
        </div>

        <Separator />

        {/* Reason Input */}
        <div className="space-y-2">
          <label className="text-sm font-medium">
            {t('approval.reason_label')}
          </label>
          <Textarea
            placeholder={t('approval.reason_placeholder')}
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
            {t('common.cancel')}
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
            {t('approval.reject')}
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
            {t('approval.approve')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
