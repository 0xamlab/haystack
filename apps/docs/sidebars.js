/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docsSidebar: [
    {
      type: 'doc',
      id: 'index',
      label: 'Overview',
    },
    {
      type: 'doc',
      id: 'quickstart',
      label: '🚀 Quickstart',
    },
    {
      type: 'category',
      label: 'API Reference',
      collapsed: false,
      items: [
        'api-reference/index',
        'api-reference/simulate',
        'api-reference/authentication',
        'api-reference/errors',
      ],
    },
    {
      type: 'category',
      label: 'Concepts',
      items: [
        'concepts/monte-carlo',
        'concepts/distributions',
        'concepts/decision-envelope',
        'concepts/auto-vs-expert',
      ],
    },
    {
      type: 'category',
      label: 'Integrations',
      items: [
        'integrations/overview',
        'integrations/chatgpt-actions',
        'integrations/claude-codex',
        'integrations/langgraph',
        'integrations/n8n',
        'integrations/azure-ai-studio',
        'integrations/local-runtime',
        'integrations/power-automate',
        'integrations/zapier',
        'integrations/make',
      ],
    },
    {
      type: 'category',
      label: 'SDKs',
      items: [
        'sdks/python',
        'sdks/typescript',
        'sdks/cli',
      ],
    },
    {
      type: 'doc',
      id: 'self-hosting',
      label: 'Self-Hosting',
    },
    {
      type: 'doc',
      id: 'changelog',
      label: 'Changelog',
    },
  ],
};

module.exports = sidebars;
