import { useEffect, useState } from 'react'
import { Shield, Check, X, Clock, AlertTriangle, History } from 'lucide-react'
import { useApprovalStore } from '@/stores'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
  Button,
  ScrollArea,
  Skeleton,
} from '@/components/ui'
import { cn, formatRelativeTime } from '@/lib/utils'
import type { ApprovalListItem, RiskLevel, ApprovalStatus } from '@/types'
import { ApprovalDialog } from './ApprovalDialog'

const riskLevelColors: Record<RiskLevel, string> = {
  low: 'bg-green-500',
  medium: 'bg-yellow-500',
  high: 'bg-orange-500',
  critical: 'bg-red-500',
}

const statusConfig: Record<
  ApprovalStatus,
  { label: string; color: string; icon: typeof Check }
> = {
  pending: {
    label: '待审批',
    color: 'bg-yellow-500',
    icon: Clock,
  },
  approved: {
    label: '已批准',
    color: 'bg-green-500',
    icon: Check,
  },
  rejected: {
    label: '已拒绝',
    color: 'bg-red-500',
    icon: X,
  },
  expired: {
    label: '已过期',
    color: 'bg-gray-500',
    icon: Clock,
  },
  escalated: {
    label: '已升级',
    color: 'bg-purple-500',
    icon: AlertTriangle,
  },
  cancelled: {
    label: '已取消',
    color: 'bg-gray-500',
    icon: X,
  },
}

interface ApprovalListProps {
  onApprovalAction?: () => void
}

export function ApprovalList({ onApprovalAction }: ApprovalListProps) {
  const {
    pendingApprovals,
    historyApprovals,
    isLoading,
    submitDecision,
    setCurrentApproval,
    currentApproval,
    fetchHistory,
  } = useApprovalStore()

  const [selectedApproval, setSelectedApproval] = useState<ApprovalListItem | null>(null)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    if (showHistory && historyApprovals.length === 0) {
      fetchHistory()
    }
  }, [showHistory, historyApprovals.length, fetchHistory])

  const handleOpenDialog = (approval: ApprovalListItem) => {
    setSelectedApproval(approval)
    setIsDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setIsDialogOpen(false)
    setSelectedApproval(null)
  }

  const handleApprove = async (id: string, reason?: string) => {
    setActionLoading(true)
    try {
      await submitDecision(id, 'approve', reason, 'current-user')
      handleCloseDialog()
      onApprovalAction?.()
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async (id: string, reason?: string) => {
    setActionLoading(true)
    try {
      await submitDecision(id, 'reject', reason, 'current-user')
      handleCloseDialog()
      onApprovalAction?.()
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <>
      <Card className="w-80 h-full border-l-0">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5" />
            {showHistory ? '审批历史' : '待审批请求'}
            {!showHistory && pendingApprovals.length > 0 && (
              <Badge variant="destructive" className="ml-auto">
                {pendingApprovals.length}
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-7 w-7 p-0"
              onClick={() => setShowHistory(!showHistory)}
              title={showHistory ? '返回待审批' : '查看历史'}
            >
              <History className="h-4 w-4" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[calc(100vh-180px)]">
            <div className="px-4 pb-4 space-y-3">
              {showHistory ? (
                /* ---- History view ---- */
                historyApprovals.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">暂无审批历史</p>
                  </div>
                ) : (
                  historyApprovals.map((approval) => {
                    const sts = statusConfig[approval.status]
                    const StsIcon = sts.icon
                    return (
                      <div
                        key={approval.id}
                        className="p-3 rounded-lg border opacity-80"
                      >
                        <div className="flex items-start gap-3">
                          <div className={cn('mt-0.5 h-3 w-3 rounded-full shrink-0', riskLevelColors[approval.risk_level])} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <p className="font-medium text-sm truncate">{approval.tool_name}</p>
                              <Badge variant="secondary" className="text-xs">
                                <StsIcon className="h-3 w-3 mr-1" />
                                {sts.label}
                              </Badge>
                            </div>
                            {approval.description && (
                              <p className="text-xs text-muted-foreground mt-1 truncate">{approval.description}</p>
                            )}
                            <p className="text-xs text-muted-foreground mt-1">{formatRelativeTime(approval.requested_at)}</p>
                          </div>
                        </div>
                      </div>
                    )
                  })
                )
              ) : (
              /* ---- Pending view ---- */
              isLoading ? (
                <div className="space-y-3">
                  {[...Array(3)].map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
              ) : pendingApprovals.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Shield className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p className="text-sm">暂无待审批请求</p>
                  <p className="text-xs mt-1">所有审批请求已处理完毕</p>
                </div>
              ) : (
                pendingApprovals.map((approval) => {
                  const status = statusConfig[approval.status]
                  const StatusIcon = status.icon

                  return (
                    <div
                      key={approval.id}
                      onClick={() => handleOpenDialog(approval)}
                      className={cn(
                        'p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md',
                        approval.risk_level === 'critical' &&
                          'border-red-200 bg-red-50/50',
                        approval.risk_level === 'high' &&
                          'border-orange-200 bg-orange-50/50'
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={cn(
                            'mt-0.5 h-3 w-3 rounded-full shrink-0',
                            riskLevelColors[approval.risk_level]
                          )}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="font-medium text-sm truncate">
                              {approval.tool_name}
                            </p>
                            <Badge
                              variant="secondary"
                              className={cn(
                                'text-xs',
                                status.color.replace('bg-', 'bg-opacity-20 text-')
                              )}
                            >
                              <StatusIcon className="h-3 w-3 mr-1" />
                              {status.label}
                            </Badge>
                          </div>

                          {approval.description && (
                            <p className="text-xs text-muted-foreground mt-1 truncate">
                              {approval.description}
                            </p>
                          )}

                          <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                            <span>{formatRelativeTime(approval.requested_at)}</span>
                            <div className="flex items-center gap-2">
                              <span className="flex items-center gap-1">
                                <Check className="h-3 w-3 text-green-600" />
                                {approval.approval_count}
                              </span>
                              <span className="flex items-center gap-1">
                                <X className="h-3 w-3 text-red-600" />
                                {approval.rejection_count}
                              </span>
                            </div>
                          </div>

                          <div className="flex gap-2 mt-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 px-2 text-xs flex-1"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleOpenDialog(approval)
                              }}
                            >
                              查看详情
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })
              )
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <ApprovalDialog
        approval={selectedApproval}
        isOpen={isDialogOpen}
        onClose={handleCloseDialog}
        onApprove={handleApprove}
        onReject={handleReject}
        isLoading={actionLoading}
      />
    </>
  )
}
