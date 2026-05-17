import { useQuery } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui'
import { Loader2, Server, CheckCircle, XCircle } from 'lucide-react'
import { integrationApi } from '@/lib/api'
import type { MCPServerInfo } from '@/types'

export function MCPPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: () => integrationApi.getMCPServers(),
  })

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8 flex items-center gap-2">
          <Server className="h-8 w-8 text-cyan-500" />
          MCP 服务器
        </h1>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <>
            <p className="text-muted-foreground mb-6">
              {data?.total || 0} 个已配置服务器
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              {data?.servers.map((srv: MCPServerInfo) => (
                <Card key={srv.name}>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Server className="h-5 w-5 text-cyan-500" />
                      {srv.name}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="px-2 py-1 bg-muted rounded text-xs">
                        {srv.type}
                      </span>
                      {srv.enabled ? (
                        <span className="flex items-center gap-1 text-green-600">
                          <CheckCircle className="h-4 w-4" /> 已启用
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400">
                          <XCircle className="h-4 w-4" /> 已禁用
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
