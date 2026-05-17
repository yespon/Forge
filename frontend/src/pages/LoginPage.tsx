import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuthStore } from '@/stores'
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  Input,
  Alert,
  AlertDescription,
} from '@/components/ui'
import { cn } from '@/lib/utils'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isRegister, setIsRegister] = useState(false)
  const [displayName, setDisplayName] = useState('')

  const { login, register, isLoading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()

    try {
      if (isRegister) {
        await register({
          email,
          password,
          display_name: displayName || undefined,
        })
      } else {
        await login({
          username: email,
          password,
        })
      }
      navigate({ to: '/' })
    } catch (err) {
      // Error is handled by store
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-muted/50 to-background p-4">
      <Card className="w-full max-w-md shadow-xl">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-4">
            <div className="h-12 w-12 rounded-xl bg-primary flex items-center justify-center">
              <Bot className="h-7 w-7 text-primary-foreground" />
            </div>
          </div>
          <CardTitle className="text-2xl text-center">
            {isRegister ? '创建账户' : '欢迎回来'}
          </CardTitle>
          <CardDescription className="text-center">
            {isRegister
              ? '填写以下信息创建新账户'
              : '登录到 Agent Runtime Platform'}
          </CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {isRegister && (
              <div className="space-y-2">
                <label className="text-sm font-medium">显示名称</label>
                <Input
                  placeholder="输入您的显示名称"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">邮箱</label>
              <Input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">密码</label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="输入您的密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  disabled={isLoading}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {isRegister && (
                <p className="text-xs text-muted-foreground">
                  密码至少需要 8 个字符
                </p>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {isRegister ? '创建中...' : '登录中...'}
                </>
              ) : isRegister ? (
                '创建账户'
              ) : (
                '登录'
              )}
            </Button>

            <div className="text-center text-sm">
              {isRegister ? (
                <>
                  已有账户？{' '}
                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(false)
                      clearError()
                    }}
                    className="text-primary hover:underline font-medium"
                  >
                    立即登录
                  </button>
                </>
              ) : (
                <>
                  还没有账户？{' '}
                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(true)
                      clearError()
                    }}
                    className="text-primary hover:underline font-medium"
                  >
                    立即注册
                  </button>
                </>
              )}
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
