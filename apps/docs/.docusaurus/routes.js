import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/',
    component: ComponentCreator('/', '611'),
    routes: [
      {
        path: '/',
        component: ComponentCreator('/', '470'),
        routes: [
          {
            path: '/',
            component: ComponentCreator('/', 'bc0'),
            routes: [
              {
                path: '/api-reference/',
                component: ComponentCreator('/api-reference/', '223'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/api-reference/authentication',
                component: ComponentCreator('/api-reference/authentication', '1da'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/api-reference/errors',
                component: ComponentCreator('/api-reference/errors', '726'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/api-reference/simulate',
                component: ComponentCreator('/api-reference/simulate', '8aa'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/changelog',
                component: ComponentCreator('/changelog', '02c'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/concepts/auto-vs-expert',
                component: ComponentCreator('/concepts/auto-vs-expert', 'e67'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/concepts/decision-envelope',
                component: ComponentCreator('/concepts/decision-envelope', 'be2'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/concepts/distributions',
                component: ComponentCreator('/concepts/distributions', '4ee'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/concepts/monte-carlo',
                component: ComponentCreator('/concepts/monte-carlo', '5f3'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/chatgpt-actions',
                component: ComponentCreator('/integrations/chatgpt-actions', '29c'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/langgraph',
                component: ComponentCreator('/integrations/langgraph', '50a'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/make',
                component: ComponentCreator('/integrations/make', '979'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/n8n',
                component: ComponentCreator('/integrations/n8n', 'd70'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/overview',
                component: ComponentCreator('/integrations/overview', '9d2'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/power-automate',
                component: ComponentCreator('/integrations/power-automate', '2a1'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/integrations/zapier',
                component: ComponentCreator('/integrations/zapier', 'd59'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/quickstart',
                component: ComponentCreator('/quickstart', 'cee'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/sdks/cli',
                component: ComponentCreator('/sdks/cli', '482'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/sdks/python',
                component: ComponentCreator('/sdks/python', 'f19'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/sdks/typescript',
                component: ComponentCreator('/sdks/typescript', 'bc4'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/self-hosting',
                component: ComponentCreator('/self-hosting', '30d'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/',
                component: ComponentCreator('/', '682'),
                exact: true,
                sidebar: "docsSidebar"
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
