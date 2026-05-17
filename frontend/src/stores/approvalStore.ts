import { create } from 'zustand'
import type {
  ApprovalListItem,
  ApprovalRequest,
  ApprovalDecisionRequest,
  ApprovalDecision,
  RiskLevel,
} from '@/types'
import { approvalsApi } from '@/lib/api'

interface ApprovalState {
  pendingApprovals: ApprovalListItem[]
  historyApprovals: ApprovalListItem[]
  currentApproval: ApprovalRequest | null
  isLoading: boolean
  error: string | null
  unreadCount: number
  pagination: {
    total: number
    page: number
    page_size: number
  }

  // Actions
  fetchPending: (params?: {
    session_id?: string
    risk_level?: RiskLevel
    page?: number
    page_size?: number
  }) => Promise<void>
  fetchHistory: (params?: {
    session_id?: string
    status?: string
    page?: number
    page_size?: number
  }) => Promise<void>
  fetchApproval: (id: string) => Promise<void>
  submitDecision: (
    id: string,
    decision: ApprovalDecision,
    reason?: string,
    userId?: string
  ) => Promise<void>
  cancelApproval: (id: string) => Promise<void>
  setCurrentApproval: (approval: ApprovalRequest | null) => void
  clearError: () => void
  reset: () => void
}

export const useApprovalStore = create<ApprovalState>((set, get) => ({
  pendingApprovals: [],
  historyApprovals: [],
  currentApproval: null,
  isLoading: false,
  error: null,
  unreadCount: 0,
  pagination: {
    total: 0,
    page: 1,
    page_size: 20,
  },

  fetchPending: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const response = await approvalsApi.listPending(params)
      set({
        pendingApprovals: response.items,
        unreadCount: response.items.length,
        pagination: {
          total: response.total,
          page: response.page,
          page_size: response.page_size,
        },
        isLoading: false,
      })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取待审批列表失败'
      set({ error: message, isLoading: false })
    }
  },

  fetchHistory: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const response = await approvalsApi.listHistory(params)
      set({
        historyApprovals: response.items,
        pagination: {
          total: response.total,
          page: response.page,
          page_size: response.page_size,
        },
        isLoading: false,
      })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取审批历史失败'
      set({ error: message, isLoading: false })
    }
  },

  fetchApproval: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const approval = await approvalsApi.get(id)
      set({ currentApproval: approval, isLoading: false })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取审批详情失败'
      set({ error: message, isLoading: false })
    }
  },

  submitDecision: async (
    id: string,
    decision: ApprovalDecision,
    reason?: string,
    userId?: string
  ) => {
    set({ isLoading: true, error: null })
    try {
      const data: ApprovalDecisionRequest = {
        decision,
        reason,
        user_id: userId || 'current-user',
      }

      const response = await approvalsApi.submitDecision(id, data)

      set((state) => ({
        pendingApprovals: state.pendingApprovals.filter((a) => a.id !== id),
        currentApproval:
          state.currentApproval?.id === id
            ? { ...state.currentApproval, status: response.status }
            : state.currentApproval,
        unreadCount: Math.max(0, state.unreadCount - 1),
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '提交审批决定失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  cancelApproval: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      await approvalsApi.cancel(id)
      set((state) => ({
        pendingApprovals: state.pendingApprovals.filter((a) => a.id !== id),
        currentApproval:
          state.currentApproval?.id === id ? null : state.currentApproval,
        unreadCount: Math.max(0, state.unreadCount - 1),
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '取消审批请求失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  setCurrentApproval: (approval) => {
    set({ currentApproval: approval })
  },

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      pendingApprovals: [],
      historyApprovals: [],
      currentApproval: null,
      isLoading: false,
      error: null,
      unreadCount: 0,
      pagination: {
        total: 0,
        page: 1,
        page_size: 20,
      },
    }),
}))
