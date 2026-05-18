import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Bot, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation()

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
            {isRegister ? t('login.create_account') : t('login.welcome')}
          </CardTitle>
          <CardDescription className="text-center">
            {isRegister
              ? t('login.fill_info')
              : t('login.login_to')}
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
                <label className="text-sm font-medium">{t('login.display_name')}</label>
                <Input
                  placeholder={t('login.display_name_placeholder')}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-medium">{t('login.email')}</label>
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
              <label className="text-sm font-medium">{t('login.password')}</label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder={t('login.password_placeholder')}
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
                  {t('login.password_hint')}
                </p>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {isRegister ? t('login.creating') : t('login.logging_in')}
                </>
              ) : isRegister ? (
                t('login.register')
              ) : (
                t('login.login')
              )}
            </Button>

            <div className="text-center text-sm">
              {isRegister ? (
                <>
                  {t('login.has_account')}{' '}
                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(false)
                      clearError()
                    }}
                    className="text-primary hover:underline font-medium"
                  >
                    {t('login.login_now')}
                  </button>
                </>
              ) : (
                <>
                  {t('login.no_account')}{' '}
                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(true)
                      clearError()
                    }}
                    className="text-primary hover:underline font-medium"
                  >
                    {t('login.register_now')}
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
