import { create } from 'zustand'
import type { Message, StreamChunk, Task, TaskEvent, TaskStatus } from '@/types'
import { chatApi } from '@/lib/api'

interface ChatState {
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  error: string | null
  streamingContent: string
  currentToolCall: StreamChunk | null

  // Task Runtime state
  currentTaskId: string | null
  currentTaskStatus: TaskStatus | null
  currentTaskProgress: number
  taskEvents: TaskEvent[]

  // Actions
  fetchHistory: (sessionId: string, limit?: number) => Promise<void>
  sendMessage: (sessionId: string, content: string) => Promise<void>
  streamMessage: (sessionId: string, content: string) => Promise<void>
  clearHistory: (sessionId: string) => Promise<void>
  addMessage: (message: Message) => void
  updateStreamingContent: (content: string) => void
  finishStreaming: () => void
  clearError: () => void
  reset: () => void

  // Task actions
  setCurrentTaskId: (taskId: string | null) => void
  setTaskStatus: (status: TaskStatus) => void
  setTaskProgress: (progress: number) => void
  addTaskEvent: (event: TaskEvent) => void
  clearTaskState: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  isStreaming: false,
  error: null,
  streamingContent: '',
  currentToolCall: null,

  // Task Runtime state
  currentTaskId: null,
  currentTaskStatus: null,
  currentTaskProgress: 0,
  taskEvents: [],

  fetchHistory: async (sessionId: string, limit = 50) => {
    set({ isLoading: true, error: null })
    try {
      const response = await chatApi.getHistory(sessionId, limit)
      const messages: Message[] = response.messages.map((msg) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        tool_calls: msg.tool_calls || undefined,
        created_at: msg.created_at,
      }))
      set({ messages, isLoading: false })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '获取聊天记录失败'
      set({ error: message, isLoading: false })
    }
  },

  sendMessage: async (sessionId: string, content: string) => {
    const { messages } = get()

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }

    set({
      messages: [...messages, userMessage],
      isLoading: true,
      error: null,
    })

    try {
      const response = await chatApi.sendMessage(sessionId, content)
      const assistantMessage: Message = {
        id: response.id,
        role: response.role,
        content: response.content,
        tool_calls: response.tool_calls || undefined,
        created_at: response.created_at,
      }

      set((state) => ({
        messages: [...state.messages, assistantMessage],
        isLoading: false,
      }))
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '发送消息失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  streamMessage: async (sessionId: string, content: string) => {
    const { messages } = get()

    // Add user message immediately
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }

    set({
      messages: [...messages, userMessage],
      isStreaming: true,
      streamingContent: '',
      currentToolCall: null,
      error: null,
    })

    return new Promise<void>((resolve, reject) => {
      const abortStream = chatApi.streamMessage(
        sessionId,
        content,
        (chunk: StreamChunk) => {
          switch (chunk.type) {
            case 'content':
              set((state) => ({
                streamingContent: state.streamingContent + (chunk.content || ''),
              }))
              break

            case 'tool_call':
              set({ currentToolCall: chunk })
              break

            case 'tool_result':
              set({ currentToolCall: null })
              break

            case 'error':
              set({
                error: chunk.error || '流式响应错误',
                isStreaming: false,
              })
              reject(new Error(chunk.error || '流式响应错误'))
              break

            case 'done':
              set((state) => {
                const assistantMessage: Message = {
                  id: `assistant-${Date.now()}`,
                  role: 'assistant',
                  content: state.streamingContent,
                  created_at: new Date().toISOString(),
                }
                return {
                  messages: [...state.messages, assistantMessage],
                  isStreaming: false,
                  streamingContent: '',
                  currentToolCall: null,
                }
              })
              resolve()
              break
          }
        },
        (error: Error) => {
          set({
            error: error.message,
            isStreaming: false,
          })
          reject(error)
        }
      )

      // Store abort function for cleanup
      set({
        // @ts-expect-error - storing abort function
        abortStream,
      })
    })
  },

  clearHistory: async (sessionId: string) => {
    set({ isLoading: true, error: null })
    try {
      await chatApi.clearHistory(sessionId)
      set({ messages: [], isLoading: false })
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '清空聊天记录失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  addMessage: (message: Message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }))
  },

  updateStreamingContent: (content: string) => {
    set({ streamingContent: content })
  },

  finishStreaming: () => {
    set((state) => {
      if (state.streamingContent) {
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: state.streamingContent,
          created_at: new Date().toISOString(),
        }
        return {
          messages: [...state.messages, assistantMessage],
          isStreaming: false,
          streamingContent: '',
          currentToolCall: null,
        }
      }
      return state
    })
  },

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      messages: [],
      isLoading: false,
      isStreaming: false,
      error: null,
      streamingContent: '',
      currentToolCall: null,
      currentTaskId: null,
      currentTaskStatus: null,
      currentTaskProgress: 0,
      taskEvents: [],
    }),

  // Task actions
  setCurrentTaskId: (taskId: string | null) => set({ currentTaskId: taskId }),

  setTaskStatus: (status: TaskStatus) => set({ currentTaskStatus: status }),

  setTaskProgress: (progress: number) =>
    set({ currentTaskProgress: Math.max(0, Math.min(100, progress)) }),

  addTaskEvent: (event: TaskEvent) =>
    set((state) => ({
      taskEvents: [...state.taskEvents, event],
    })),

  clearTaskState: () =>
    set({
      currentTaskId: null,
      currentTaskStatus: null,
      currentTaskProgress: 0,
      taskEvents: [],
    }),
}))
