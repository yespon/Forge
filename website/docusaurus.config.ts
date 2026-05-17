import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Forge',
  tagline: 'Enterprise Agent Runtime Platform',
  favicon: 'img/favicon.ico',
  url: 'https://forge.example.com',
  baseUrl: '/',
  organizationName: 'forge',
  projectName: 'forge-docs',
  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',
  i18n: {
    defaultLocale: 'zh-Hans',
    locales: ['zh-Hans', 'en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: '/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    navbar: {
      title: 'Forge',
      items: [
        {to: '/', label: 'Docs', position: 'left'},
        {to: '/architecture', label: 'Architecture', position: 'left'},
        {to: '/roadmap', label: 'Roadmap', position: 'left'},
        {href: 'https://github.com/your-org/forge', label: 'GitHub', position: 'right'},
      ],
    },
  } as Preset.ThemeConfig,
};

export default config;
