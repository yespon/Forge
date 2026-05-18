import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/en/',
    component: ComponentCreator('/en/', '6c2'),
    exact: true
  },
  {
    path: '/en/',
    component: ComponentCreator('/en/', '5eb'),
    routes: [
      {
        path: '/en/',
        component: ComponentCreator('/en/', 'f44'),
        routes: [
          {
            path: '/en/',
            component: ComponentCreator('/en/', '0e4'),
            routes: [
              {
                path: '/en/api/approvals',
                component: ComponentCreator('/en/api/approvals', 'f04'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/api/models',
                component: ComponentCreator('/en/api/models', '34e'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/api/overview',
                component: ComponentCreator('/en/api/overview', '8b0'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/api/tasks',
                component: ComponentCreator('/en/api/tasks', 'fd6'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/architecture',
                component: ComponentCreator('/en/architecture', '73b'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/channels',
                component: ComponentCreator('/en/channels', 'aaa'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/configuration',
                component: ComponentCreator('/en/configuration', 'cc9'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/deployment/docker',
                component: ComponentCreator('/en/deployment/docker', '040'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/mcp',
                component: ComponentCreator('/en/mcp', 'd58'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/memory',
                component: ComponentCreator('/en/memory', '566'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/middleware',
                component: ComponentCreator('/en/middleware', '8ae'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/model-configs',
                component: ComponentCreator('/en/model-configs', '2bd'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/quickstart',
                component: ComponentCreator('/en/quickstart', '10f'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/roadmap',
                component: ComponentCreator('/en/roadmap', '91d'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/skills',
                component: ComponentCreator('/en/skills', '2f7'),
                exact: true,
                sidebar: "docs"
              },
              {
                path: '/en/',
                component: ComponentCreator('/en/', 'fc8'),
                exact: true,
                sidebar: "docs"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
