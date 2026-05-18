import { useTranslation } from 'react-i18next'
import { Globe } from 'lucide-react'
import { supportedLanguages } from '@/i18n'

export function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <div className="relative inline-flex items-center gap-1.5">
      <Globe className="h-4 w-4 text-muted-foreground" />
      <select
        value={i18n.language}
        onChange={(e) => i18n.changeLanguage(e.target.value)}
        className="appearance-none bg-transparent text-sm text-muted-foreground hover:text-foreground cursor-pointer focus:outline-none pr-4"
      >
        {supportedLanguages.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  )
}
