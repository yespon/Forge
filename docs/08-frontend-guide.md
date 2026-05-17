# 前端开发指南

## 产品界面定位

前端是企业任务工作台，不是 coding IDE。主界面应围绕 Skill/Plugin 选择、任务参数、执行进度、审批、通知、产物和历史展开。聊天区是任务发起与澄清的控制面，不是唯一入口。

## 技术栈

- **框架**: React 18 + TypeScript 5
- **构建**: Vite 5
- **样式**: TailwindCSS 3
- **状态管理**: Zustand 4
- **数据获取**: TanStack Query (React Query) 5
- **路由**: TanStack Router
- **UI 组件**: Radix UI + shadcn/ui
- **图表**: Recharts
- **测试**: Vitest + React Testing Library
- **代码规范**: ESLint + Prettier

---

## 项目结构

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── eslint.config.js
├── index.html
│
├── src/
│   ├── main.tsx              # 应用入口
│   ├── App.tsx               # 根组件
│   ├── routeTree.gen.ts      # 自动生成的路由
│   │
│   ├── components/           # 通用组件
│   │   ├── ui/              # shadcn 基础组件
│   │   │   ├── button.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── dropdown-menu.tsx
│   │   │   └── ...
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── PageLayout.tsx
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   ├── ToolCallCard.tsx
│   │   │   ├── StreamingText.tsx
│   │   │   └── InputArea.tsx
│   │   └── common/
│   │       ├── LoadingSpinner.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── EmptyState.tsx
│   │
│   ├── views/               # 页面级组件（核心视图）
│   │   ├── workspace/       # 任务工作台
│   │   │   ├── WorkspacePage.tsx
│   │   │   ├── SessionList.tsx
│   │   │   └── ChatPanel.tsx
│   │   ├── tasks/           # Task Runtime
│   │   │   ├── TaskList.tsx
│   │   │   ├── TaskTimeline.tsx
│   │   │   ├── TaskStream.tsx
│   │   │   └── ArtifactList.tsx
│   │   ├── sandbox/         # Sandbox 控制台（插件执行环境）
│   │   │   ├── SandboxPage.tsx
│   │   │   ├── SandboxList.tsx
│   │   │   ├── FileExplorer.tsx
│   │   │   └── EnvVarEditor.tsx
│   │   ├── skills/          # Skill/Plugin 市场
│   │   │   ├── SkillsPage.tsx
│   │   │   ├── SkillCard.tsx
│   │   │   └── SkillDetail.tsx
│   │   ├── approvals/       # 审批与通知中心
│   │   │   ├── ApprovalList.tsx
│   │   │   └── ApprovalDetail.tsx
│   │   └── admin/           # 管理后台
│   │       ├── AdminPage.tsx
│   │       ├── UserManagement.tsx
│   │       ├── AuditLogs.tsx
│   │       └── Dashboard.tsx
│   │
│   ├── hooks/               # 自定义 Hooks
│   │   ├── useAuth.ts
│   │   ├── useSession.ts
│   │   ├── useWebSocket.ts
│   │   ├── useStreaming.ts
│   │   └── useNotification.ts
│   │
│   ├── stores/              # Zustand 状态
│   │   ├── authStore.ts
│   │   ├── sessionStore.ts
│   │   ├── chatStore.ts
│   │   └── notificationStore.ts
│   │
│   ├── lib/                 # 工具函数
│   │   ├── api.ts           # API 客户端
│   │   ├── websocket.ts     # WebSocket 管理
│   │   ├── utils.ts         # 通用工具
│   │   └── constants.ts     # 常量
│   │
│   ├── types/               # TypeScript 类型
│   │   ├── api.ts
│   │   ├── models.ts
│   │   └── index.ts
│   │
│   └── styles/
│       └── globals.css
│
└── public/
    └── favicon.ico
```

---

## 核心组件设计

### 1. 状态管理 (Zustand)

**stores/authStore.ts**

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, LoginCredentials } from '@/types/models';
import { authApi } from '@/lib/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      
      login: async (credentials) => {
        set({ isLoading: true });
        try {
          const response = await authApi.login(credentials);
          set({
            user: response.user,
            accessToken: response.access_token,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false });
          throw error;
        }
      },
      
      logout: () => {
        set({
          user: null,
          accessToken: null,
          isAuthenticated: false,
        });
      },
      
      refreshToken: async () => {
        // 实现 token 刷新
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ accessToken: state.accessToken }),
    }
  )
);
```

**stores/sessionStore.ts**

```typescript
import { create } from 'zustand';
import { Session, SessionStatus } from '@/types/models';
import { sessionsApi } from '@/lib/api';

interface SessionState {
  sessions: Session[];
  activeSessionId: string | null;
  isLoading: boolean;
  
  // Actions
  fetchSessions: () => Promise<void>;
  createSession: (data: CreateSessionData) => Promise<Session>;
  setActiveSession: (id: string | null) => void;
  updateSessionStatus: (id: string, status: SessionStatus) => void;
  archiveSession: (id: string) => Promise<void>;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  isLoading: false,
  
  fetchSessions: async () => {
    set({ isLoading: true });
    const sessions = await sessionsApi.list();
    set({ sessions, isLoading: false });
  },
  
  createSession: async (data) => {
    const session = await sessionsApi.create(data);
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: session.id,
    }));
    return session;
  },
  
  setActiveSession: (id) => {
    set({ activeSessionId: id });
  },
  
  updateSessionStatus: (id, status) => {
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === id ? { ...s, status } : s
      ),
    }));
  },
  
  archiveSession: async (id) => {
    await sessionsApi.delete(id);
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      activeSessionId: state.activeSessionId === id ? null : state.activeSessionId,
    }));
  },
}));
```

**stores/chatStore.ts**

```typescript
import { create } from 'zustand';
import { Message, ToolCall, ApprovalRequest } from '@/types/models';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  pendingApproval: ApprovalRequest | null;
  
  // Actions
  addMessage: (message: Message) => void;
  addToolCall: (toolCall: ToolCall) => void;
  updateToolResult: (toolCallId: string, result: unknown) => void;
  setStreaming: (isStreaming: boolean) => void;
  setPendingApproval: (approval: ApprovalRequest | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  pendingApproval: null,
  
  addMessage: (message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },
  
  addToolCall: (toolCall) => {
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: toolCall.id,
          type: 'tool_call',
          tool: toolCall,
          timestamp: new Date(),
        },
      ],
    }));
  },
  
  updateToolResult: (toolCallId, result) => {
    set((state) => ({
      messages: state.messages.map((m) =>
        m.type === 'tool_call' && m.tool.id === toolCallId
          ? { ...m, tool: { ...m.tool, result, status: 'completed' } }
          : m
      ),
    }));
  },
  
  setStreaming: (isStreaming) => set({ isStreaming }),
  
  setPendingApproval: (approval) => set({ pendingApproval: approval }),
  
  clearMessages: () => set({ messages: [], pendingApproval: null }),
}));
```

---

### 2. WebSocket 管理

**lib/websocket.ts**

```typescript
import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useChatStore } from '@/stores/chatStore';

export type WebSocketMessage =
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; tool: string; input: unknown }
  | { type: 'tool_result'; tool: string; output: unknown }
  | { type: 'message'; content: string; artifacts?: unknown[] }
  | { type: 'approval_required'; approval: ApprovalRequest }
  | { type: 'done' }
  | { type: 'error'; message: string };

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageHandlers: Set<(msg: WebSocketMessage) => void> = new Set();
  private sessionId: string | null = null;
  
  connect(sessionId: string, token: string) {
    this.sessionId = sessionId;
    const wsUrl = `wss://api.agent-platform.com/v1/sessions/${sessionId}/stream?token=${token}`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.messageHandlers.forEach((handler) => handler(message));
    };
    
    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect(sessionId, token);
        }, this.reconnectDelay * this.reconnectAttempts);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }
  
  disconnect() {
    this.ws?.close();
    this.ws = null;
    this.sessionId = null;
  }
  
  send(message: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }
  
  onMessage(handler: (msg: WebSocketMessage) => void) {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }
}

// Singleton instance
export const wsManager = new WebSocketManager();

// React Hook
export function useWebSocket(sessionId: string | null) {
  const { accessToken } = useAuthStore();
  const { addMessage, addToolCall, updateToolResult, setStreaming, setPendingApproval } = useChatStore();
  
  useEffect(() => {
    if (!sessionId || !accessToken) return;
    
    wsManager.connect(sessionId, accessToken);
    
    const unsubscribe = wsManager.onMessage((msg) => {
      switch (msg.type) {
        case 'thinking':
          // 可显示在 UI 的思考过程
          break;
        case 'tool_call':
          addToolCall(msg);
          break;
        case 'tool_result':
          updateToolResult(msg.toolCallId, msg.result);
          break;
        case 'message':
          addMessage({
            id: crypto.randomUUID(),
            type: 'assistant',
            content: msg.content,
            timestamp: new Date(),
          });
          break;
        case 'approval_required':
          setPendingApproval(msg.approval);
          break;
        case 'done':
          setStreaming(false);
          break;
        case 'error':
          console.error(msg.message);
          setStreaming(false);
          break;
      }
    });
    
    return () => {
      unsubscribe();
      wsManager.disconnect();
    };
  }, [sessionId, accessToken]);
  
  const sendMessage = useCallback((content: string, attachments?: File[]) => {
    wsManager.send({
      type: 'message',
      content,
      attachments: attachments?.map((f) => ({ name: f.name })),
    });
    setStreaming(true);
  }, []);
  
  const sendApproval = useCallback((approvalId: string, decision: 'approved' | 'rejected', reason?: string) => {
    wsManager.send({
      type: 'approval_response',
      approval_id: approvalId,
      decision,
      reason,
    });
    setPendingApproval(null);
  }, []);
  
  return { sendMessage, sendApproval };
}
```

---

### 3. 核心页面组件

**views/workspace/ChatPanel.tsx**

```tsx
import { useRef, useEffect } from 'react';
import { useParams } from '@tanstack/react-router';
import { useChatStore } from '@/stores/chatStore';
import { useSessionStore } from '@/stores/sessionStore';
import { useWebSocket } from '@/lib/websocket';
import { MessageList } from '@/components/chat/MessageList';
import { InputArea } from '@/components/chat/InputArea';
import { ApprovalDialog } from '@/components/chat/ApprovalDialog';
import { ScrollArea } from '@/components/ui/scroll-area';

export function ChatPanel() {
  const { sessionId } = useParams({ from: '/workspace/$sessionId' });
  const scrollRef = useRef<HTMLDivElement>(null);
  
  const { messages, isStreaming, pendingApproval } = useChatStore();
  const { sendMessage, sendApproval } = useWebSocket(sessionId);
  
  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, isStreaming]);
  
  const handleSend = (content: string, attachments?: File[]) => {
    // 添加用户消息到列表
    useChatStore.getState().addMessage({
      id: crypto.randomUUID(),
      type: 'user',
      content,
      timestamp: new Date(),
      attachments: attachments?.map((f) => ({ name: f.name, size: f.size })),
    });
    
    sendMessage(content, attachments);
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 */}
      <ScrollArea ref={scrollRef} className="flex-1 p-4">
        <MessageList messages={messages} />
        {isStreaming && <StreamingIndicator />}
      </ScrollArea>
      
      {/* 输入区 */}
      <InputArea onSend={handleSend} disabled={isStreaming || !!pendingApproval} />
      
      {/* 审批弹窗 */}
      <ApprovalDialog
        approval={pendingApproval}
        onApprove={(reason) => sendApproval(pendingApproval!.id, 'approved', reason)}
        onReject={(reason) => sendApproval(pendingApproval!.id, 'rejected', reason)}
      />
    </div>
  );
}
```

**components/chat/MessageList.tsx**

```tsx
import { Message } from '@/types/models';
import { UserMessage } from './UserMessage';
import { AssistantMessage } from './AssistantMessage';
import { ToolCallCard } from './ToolCallCard';

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <div key={message.id} className="animate-in fade-in slide-in-from-bottom-2">
          {message.type === 'user' && <UserMessage message={message} />}
          {message.type === 'assistant' && <AssistantMessage message={message} />}
          {message.type === 'tool_call' && <ToolCallCard toolCall={message.tool} />}
        </div>
      ))}
    </div>
  );
}
```

**components/chat/ToolCallCard.tsx**

```tsx
import { useState } from 'react';
import { ToolCall } from '@/types/models';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp, Wrench, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const statusIcons = {
    pending: <Loader2 className="w-4 h-4 animate-spin text-yellow-500" />,
    running: <Loader2 className="w-4 h-4 animate-spin text-blue-500" />,
    completed: <CheckCircle className="w-4 h-4 text-green-500" />,
    failed: <XCircle className="w-4 h-4 text-red-500" />,
  };
  
  return (
    <Card className={cn(
      "ml-8 border-l-4",
      toolCall.status === 'completed' && "border-l-green-500",
      toolCall.status === 'failed' && "border-l-red-500",
      toolCall.status === 'pending' && "border-l-yellow-500",
    )}>
      <CardHeader className="py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wrench className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">{toolCall.tool}</span>
            {statusIcons[toolCall.status]}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>
        </div>
      </CardHeader>
      
      {isExpanded && (
        <CardContent className="pt-0">
          <div className="space-y-2">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Input</p>
              <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-auto">
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
            {toolCall.result && (
              <div>
                <p className="text-xs font-medium text-muted-foreground">Result</p>
                <pre className="mt-1 p-2 bg-muted rounded text-xs overflow-auto">
                  {JSON.stringify(toolCall.result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
```

---

## 路由配置

**src/routeTree.gen.ts** (自动生成)

**src/routes/__root.tsx**

```tsx
import { createRootRoute, Outlet } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 3,
    },
  },
});

export const Route = createRootRoute({
  component: () => (
    <QueryClientProvider client={queryClient}>
      <Outlet />
      <Toaster />
    </QueryClientProvider>
  ),
});
```

**src/routes/workspace/$sessionId.tsx**

```tsx
import { createFileRoute } from '@tanstack/react-router';
import { WorkspacePage } from '@/views/workspace/WorkspacePage';

export const Route = createFileRoute('/workspace/$sessionId')({
  component: WorkspacePage,
  loader: async ({ params }) => {
    // 预加载会话数据
    return { sessionId: params.sessionId };
  },
});
```

---

## 样式规范

**Tailwind 配置**

```javascript
// tailwind.config.js
module.exports = {
  darkMode: ['class'],
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

---

## 开发命令

```bash
# 安装依赖
npm install

# 开发服务器
npm run dev

# 类型检查
npm run type-check

# 代码规范
npm run lint
npm run format

# 测试
npm run test
npm run test:ui

# 构建
npm run build

# 预览生产构建
npm run preview
```

---

## Week 8 交付检查清单

- [ ] Vite + React + TypeScript 项目搭建
- [ ] TailwindCSS + shadcn/ui 配置
- [ ] Zustand 状态管理实现
- [ ] TanStack Router 路由配置
- [ ] 登录页面
- [ ] Agent 工作台基础布局
- [ ] 对话界面（流式输出）
- [ ] Session 列表侧边栏
- [ ] 审批弹窗
- [ ] WebSocket 连接管理
- [ ] 与后端 API 联调通过
