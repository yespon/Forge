import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { Loader2, BookOpen, CheckCircle, XCircle } from 'lucide-react'
import { integrationApi } from '@/lib/api'
import type { SkillInfo } from '@/types'

export function SkillsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['skills'],
    queryFn: () => integrationApi.listSkills(),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8">技能市场</h1>
        <p className="text-muted-foreground mb-6">
          已加载 {data?.total || 0} 个技能
        </p>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.skills.map((skill: SkillInfo) => (
            <Card key={skill.name} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-indigo-500" />
                  {skill.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-3">
                  {skill.description || '无描述'}
                </p>
                <div className="flex items-center gap-2 text-sm">
                  {skill.is_active ? (
                    <span className="flex items-center gap-1 text-green-600">
                      <CheckCircle className="h-4 w-4" /> 已激活
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-gray-400">
                      <XCircle className="h-4 w-4" /> 未激活
                    </span>
                  )}
                  {skill.has_instructions && (
                    <span className="text-xs px-2 py-1 bg-blue-100 text-blue-800 rounded">
                      含指令
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  )
}
