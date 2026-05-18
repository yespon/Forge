import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { ApprovalList } from '@/components/approval/ApprovalList'
import { useSessionStore, useApprovalStore, useAuthStore } from '@/stores'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  Button,
  Input,
  Textarea,
  Alert,
  AlertDescription,
} from '@/components/ui'
import type { Session } from '@/types'

export function WorkspacePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const {
    sessions,
    currentSession,
    fetchSessions,
    createSession,
    setCurrentSession,
    isLoading: sessionLoading,
    error: sessionError,
    clearError: clearSessionError,
  } = useSessionStore()

  const { fetchPending } = useApprovalStore()
  const { logout } = useAuthStore()

  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [newSessionName, setNewSessionName] = useState('')
  const [newSessionDescription, setNewSessionDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [showApprovals, setShowApprovals] = useState(false)

  // Load sessions on mount
  useEffect(() => {
    fetchSessions()
    fetchPending()
  }, [fetchSessions, fetchPending])

  // Poll for approvals
  useEffect(() => {
    const interval = setInterval(() => {
      fetchPending()
    }, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [fetchPending])

  const handleSelectSession = useCallback(
    (session: Session) => {
      setCurrentSession(session)
    },
    [setCurrentSession]
  )

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) return

    setIsCreating(true)
    try {
      await createSession({
        name: newSessionName.trim(),
        description: newSessionDescription.trim() || undefined,
      })
      setIsCreateDialogOpen(false)
      setNewSessionName('')
      setNewSessionDescription('')
    } finally {
      setIsCreating(false)
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate({ to: '/login' })
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <Header onOpenApprovals={() => setShowApprovals(!showApprovals)} />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          onSelectSession={handleSelectSession}
          onCreateSession={() => setIsCreateDialogOpen(true)}
        />

        {/* Chat Panel */}
        <div className="flex-1 flex">
          <ChatPanel sessionId={currentSession?.id} />

          {/* Approval Panel */}
          {showApprovals && (
            <ApprovalList
              onApprovalAction={() => {
                fetchPending()
              }}
            />
          )}
        </div>
      </div>

      {/* Create Session Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('workspace.new_session')}</DialogTitle>
            <DialogDescription>
              {t('workspace.new_session_desc')}
            </DialogDescription>
          </DialogHeader>

          {sessionError && (
            <Alert variant="destructive">
              <AlertDescription>{sessionError}</AlertDescription>
            </Alert>
          )}

          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t('workspace.session_name')} <span className="text-red-500">{t('workspace.session_name_required')}</span>
              </label>
              <Input
                placeholder={t('workspace.session_name_placeholder')}
                value={newSessionName}
                onChange={(e) => setNewSessionName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('workspace.description_optional')}</label>
              <Textarea
                placeholder={t('workspace.description_placeholder')}
                value={newSessionDescription}
                onChange={(e) => setNewSessionDescription(e.target.value)}
                rows={3}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateDialogOpen(false)
                clearSessionError()
              }}
              disabled={isCreating}
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleCreateSession}
              disabled={!newSessionName.trim() || isCreating}
            >
              {isCreating ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
              ) : (
                <Plus className="h-4 w-4 mr-2" />
              )}
              {t('common.create')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
