import { Bell, User, LogOut, Settings, Shield, ListTodo, MessageSquare, Package } from 'lucide-react'
import { Link } from '@tanstack/react-router'
import { useAuthStore, useApprovalStore } from '@/stores'
import {
  Button,
  Avatar,
  AvatarFallback,
  Badge,
  Tooltip,
} from '@/components/ui'
import { getInitials } from '@/lib/utils'

interface HeaderProps {
  onOpenApprovals?: () => void
}

export function Header({ onOpenApprovals }: HeaderProps) {
  const { user, logout } = useAuthStore()
  const { unreadCount } = useApprovalStore()

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center px-4 gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <Settings className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="font-semibold text-lg hidden sm:inline-block">
            Agent Platform
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-1 ml-4">
          <Link to="/">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <MessageSquare className="h-4 w-4" />
              <span className="hidden sm:inline">工作区</span>
            </Button>
          </Link>
          <Link to="/tasks">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <ListTodo className="h-4 w-4" />
              <span className="hidden sm:inline">任务</span>
            </Button>
          </Link>
          <Link to="/skills">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <Package className="h-4 w-4" />
              <span className="hidden sm:inline">技能</span>
            </Button>
          </Link>
          <Link to="/settings">
            <Button variant="ghost" size="sm" className="gap-1.5">
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">设置</span>
            </Button>
          </Link>
        </nav>

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Approval Notifications */}
          <Tooltip content={`${unreadCount} 个待审批请求`}>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              onClick={onOpenApprovals}
            >
              <Shield className="h-5 w-5" />
              {unreadCount > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
                >
                  {unreadCount > 99 ? '99+' : unreadCount}
                </Badge>
              )}
            </Button>
          </Tooltip>

          {/* Notifications */}
          <Tooltip content="通知">
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <Badge
                variant="secondary"
                className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
              >
                0
              </Badge>
            </Button>
          </Tooltip>

          {/* User Menu */}
          <div className="flex items-center gap-2 pl-2 border-l">
            <Avatar className="h-8 w-8">
              <AvatarFallback className="bg-primary/10 text-primary text-sm">
                {getInitials(user?.display_name || user?.email || 'U')}
              </AvatarFallback>
            </Avatar>
            <div className="hidden md:block">
              <p className="text-sm font-medium">
                {user?.display_name || user?.email?.split('@')[0]}
              </p>
              <p className="text-xs text-muted-foreground capitalize">
                {user?.role}
              </p>
            </div>
            <Tooltip content="退出登录">
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                className="ml-2"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </Tooltip>
          </div>
        </div>
      </div>
    </header>
  )
}
