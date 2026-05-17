import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { Loader2, Cpu, Eye, Brain } from 'lucide-react'
import { integrationApi } from '@/lib/api'
import type { ModelInfo, IntegrationStatus } from '@/types'

export function ModelsPage() {
  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ['models'],
    queryFn: () => integrationApi.listModels(),
  })

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['integration-status'],
    queryFn: () => integrationApi.getStatus(),
  })

  if (modelsLoading || statusLoading) {
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
        <h1 className="text-3xl font-bold mb-8">模型管理</h1>

        {/* Feature Status */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>平台功能状态</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {status && Object.entries(status.features).map(([key, enabled]) => (
                <div key={key} className="flex items-center gap-2 p-3 rounded-lg border">
                  <div className={`w-3 h-3 rounded-full ${enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className="text-sm capitalize">{key.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Models */}
        <h2 className="text-xl font-semibold mb-4">
          可用模型 ({models?.total || 0})
        </h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {models?.models.map((model: ModelInfo) => (
            <Card key={model.name} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-blue-500" />
                  {model.display_name || model.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <code className="px-2 py-1 bg-muted rounded text-xs">{model.name}</code>
                  </div>
                  <div className="flex gap-4 text-sm text-muted-foreground">
                    {model.supports_thinking && (
                      <span className="flex items-center gap-1">
                        <Brain className="h-4 w-4" /> 思考
                      </span>
                    )}
                    {model.supports_vision && (
                      <span className="flex items-center gap-1">
                        <Eye className="h-4 w-4" /> 视觉
                      </span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  )
}