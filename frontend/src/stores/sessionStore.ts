import { create } from 'zustand'
import type { Session, SessionListResponse } from '@/types'
import { sessionsApi } from '@/lib/api'

interface SessionState {
  sessions: Session[]
  currentSession: Session | null
  isLoading: boolean
  error: string | null
  pagination: {
    total: number
    page: number
    page_size: number
  }

  // Actions
  fetchSessions: (params?: {
    page?: number
    page_size?: number
    status?: string
  }) => Promise<void>
  fetchSession: (id: string) => Promise<void>
  createSession: (data: {
    name: string
    description?: string
    model?: string
    system_prompt?: string
  }) => Promise<Session>
  updateSession: (
    id: string,
    data: {
      name?: string
      description?: string
      status?: string
    }
  ) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  terminateSession: (id: string) => Promise<void>
  setCurrentSession: (session: Session | null) => void
  clearError: () => void
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  currentSession: null,
  isLoading: false,
  error: null,
  pagination: {
    total: 0,
    page: 1,
    page_size: 20,
  },

  fetchSessions: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const response: SessionListResponse = await sessionsApi.list(params)
      set({
        sessions: response.items,
        pagination: {
          total: response.total,
          page: response.page,
          page_size: response.page_size,
        },
        isLoading: false,
      })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取会话列表失败'
      set({ error: message, isLoading: false })
    }
  },

  fetchSession: async (id: string) => {
    set({ isLoading: true, error: null })
    try {
      const session = await sessionsApi.get(id)
      set({ currentSession: session, isLoading: false })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取会话失败'
      set({ error: message, isLoading: false })
    }
  },

  createSession: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const session = await sessionsApi.create(data)
      set((state) => ({
        sessions: [session, ...state.sessions],
        currentSession: session,
        isLoading: false,
      }))
      return session
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '创建会话失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  updateSession: async (id, data) => {
    set({ isLoading: true, error: null })
    try {
      const session = await sessionsApi.update(id, data)
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === id ? session : s)),
        currentSession:
          state.currentSession?.id === id ? session : state.currentSession,
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '更新会话失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  deleteSession: async (id) => {
    set({ isLoading: true, error: null })
    try {
      await sessionsApi.delete(id)
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== id),
        currentSession:
          state.currentSession?.id === id ? null : state.currentSession,
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '删除会话失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  terminateSession: async (id) => {
    set({ isLoading: true, error: null })
    try {
      const session = await sessionsApi.terminate(id)
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === id ? session : s)),
        currentSession:
          state.currentSession?.id === id ? session : state.currentSession,
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '终止会话失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  setCurrentSession: (session) => {
    set({ currentSession: session })
  },

  clearError: () => set({ error: null }),
}))
