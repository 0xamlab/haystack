// @ts-check
// Docusaurus configuration for Algenta developer docs

const { themes: prismThemes } = require('prism-react-renderer');

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Algenta',
  tagline: 'Monte Carlo simulation and data-query platform for smarter decisions',
  favicon: 'img/favicon.ico',

  url: 'https://docs.algenta.ai',
  baseUrl: '/',

  organizationName: 'algenta',
  projectName: 'decision-engine-docs',

  onBrokenLinks: 'warn',
  onBrokenMarkdownLinks: 'warn',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          routeBasePath: '/',
          editUrl: 'https://github.com/algenta/decision-engine/tree/main/apps/docs/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/social-card.png',
      colorMode: {
        defaultMode: 'dark',
        disableSwitch: false,
      },
      navbar: {
        title: 'Algenta',
        logo: {
          alt: 'Algenta Logo',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docsSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://algenta.ai/signup',
            label: 'Get API Key',
            position: 'right',
          },
          {
            href: 'https://github.com/algenta/decision-engine',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              { label: 'Quickstart', to: '/quickstart' },
              { label: 'API Reference', to: '/api-reference' },
              { label: 'Integrations', to: '/integrations/overview' },
            ],
          },
          {
            title: 'Community',
            items: [
              { label: 'GitHub', href: 'https://github.com/algenta/decision-engine' },
              { label: 'Support', href: 'https://algenta.ai/support' },
            ],
          },
          {
            title: 'Product',
            items: [
              { label: 'Pricing', href: 'https://algenta.ai/pricing' },
              { label: 'Status', href: 'https://algenta.ai/status' },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Algenta. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['bash', 'python', 'typescript', 'json', 'yaml'],
      },
    }),
};

module.exports = config;
