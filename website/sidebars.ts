import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    'index',
    'quickstart',
    'configuration',
    'architecture',
    'roadmap',
    'model-configs',
    {
      type: 'category',
      label: 'Core Concepts',
      items: ['middleware', 'skills', 'memory', 'mcp', 'channels'],
    },
    {
      type: 'category',
      label: 'Deployment',
      items: ['deployment/docker'],
    },
    {
      type: 'category',
      label: 'API',
      items: ['api/overview', 'api/models', 'api/approvals', 'api/tasks'],
    },
  ],
};

export default sidebars;
