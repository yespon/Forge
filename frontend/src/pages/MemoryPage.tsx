import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Header } from '@/components/layout/Header'
import { Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { Loader2, Search, Brain } from 'lucide-react'
import { integrationApi } from '@/lib/api'
import type { MemoryFact } from '@/types'

export function MemoryPage() {
  const [query, setQuery] = useState('')
  const { t, i18n } = useTranslation()

  const { data, isLoading } = useQuery({
    queryKey: ['memory', query],
    queryFn: () => integrationApi.getMemory(query || undefined),
  })

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-8 flex items-center gap-2">
          <Brain className="h-8 w-8 text-purple-500" />
          {t('memory.title')}
        </h1>

        <div className="relative mb-6 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            placeholder={t('memory.search')}
            className="pl-10"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <>
            <p className="text-muted-foreground mb-4">
              {t('memory.total', { count: data?.total || 0 })}
            </p>
            <div className="space-y-3">
              {data?.facts.map((fact: MemoryFact, i: number) => (
                <Card key={i}>
                  <CardContent className="pt-6">
                    <p className="text-sm mb-2">{fact.content}</p>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span>{t('memory.category')}: {fact.category}</span>
                      <span>{t('memory.confidence')}: {Math.round(fact.confidence * 100)}%</span>
                      <span>
                        {t('memory.time')}: {new Date(fact.timestamp * 1000).toLocaleString(i18n.language)}
                      </span>
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
