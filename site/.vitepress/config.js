import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Scrape Analyzer',
  description: 'Speckit SDD specification documentation',
  base: process.env.VITEPRESS_BASE || '/',
  ignoreDeadLinks: [/localhost/, /\/research\//],
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Speckit Guide', link: '/guide/speckit' },
      { text: 'Codespaces', link: '/guide/codespaces' },
      { text: 'Constitution', link: '/constitution' },
      { text: 'Specs', link: '/specs/001-article-collection/spec' },
    ],
    sidebar: [
      {
        text: 'Project',
        items: [
          { text: 'Speckit SDD Guide', link: '/guide/speckit' },
          { text: 'Codespaces 開發環境', link: '/guide/codespaces' },
          { text: 'Constitution', link: '/constitution' },
        ],
      },
      {
        text: '001 · Article Collection',
        collapsed: false,
        items: [
          { text: 'Spec', link: '/specs/001-article-collection/spec' },
          { text: 'Plan', link: '/specs/001-article-collection/plan' },
          { text: 'Data Model', link: '/specs/001-article-collection/data-model' },
          { text: 'Requirements', link: '/specs/001-article-collection/checklists/requirements' },
        ],
      },
      {
        text: '002 · Article Processing',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/002-article-processing/spec' },
          { text: 'Plan', link: '/specs/002-article-processing/plan' },
          { text: 'Data Model', link: '/specs/002-article-processing/data-model' },
          { text: 'Tasks', link: '/specs/002-article-processing/tasks' },
          { text: 'Research', link: '/specs/002-article-processing/research' },
          { text: 'Requirements', link: '/specs/002-article-processing/checklists/requirements' },
        ],
      },
      {
        text: '003 · LLM Analysis',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/003-llm-analysis/spec' },
          { text: 'Plan', link: '/specs/003-llm-analysis/plan' },
          { text: 'Data Model', link: '/specs/003-llm-analysis/data-model' },
          { text: 'Tasks', link: '/specs/003-llm-analysis/tasks' },
          { text: 'Research', link: '/specs/003-llm-analysis/research' },
          { text: 'Quick Start', link: '/specs/003-llm-analysis/quickstart' },
          { text: 'Requirements', link: '/specs/003-llm-analysis/checklists/requirements' },
          { text: 'Contract: LLM Service', link: '/specs/003-llm-analysis/contracts/llm-service' },
        ],
      },
      {
        text: '004 · Translation',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/004-translation/spec' },
          { text: 'Plan', link: '/specs/004-translation/plan' },
          { text: 'Data Model', link: '/specs/004-translation/data-model' },
          { text: 'Contract: LLM Translate', link: '/specs/004-translation/contracts/llm-service-translate' },
          { text: 'Contract: Translation Repo', link: '/specs/004-translation/contracts/translation-repository' },
        ],
      },
      {
        text: '005 · Tag Management',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/005-tag-management/spec' },
          { text: 'Plan', link: '/specs/005-tag-management/plan' },
          { text: 'Data Model', link: '/specs/005-tag-management/data-model' },
          { text: 'Contract: API', link: '/specs/005-tag-management/contracts/api' },
        ],
      },
      {
        text: '006 · Observability',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/006-observability/spec' },
          { text: 'Plan', link: '/specs/006-observability/plan' },
          { text: 'Data Model', link: '/specs/006-observability/data-model' },
          { text: 'Contract: Logging', link: '/specs/006-observability/contracts/logging-contract' },
        ],
      },
      {
        text: '007 · Scheduler',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/007-scheduler/spec' },
          { text: 'Plan', link: '/specs/007-scheduler/plan' },
          { text: 'Data Model', link: '/specs/007-scheduler/data-model' },
          { text: 'Contract: Entry Point', link: '/specs/007-scheduler/contracts/entry-point-contract' },
        ],
      },
      {
        text: '008 · Article Sharing',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/008-article-sharing/spec' },
          { text: 'Plan', link: '/specs/008-article-sharing/plan' },
          { text: 'Tasks', link: '/specs/008-article-sharing/tasks' },
          { text: 'Research', link: '/specs/008-article-sharing/research' },
          { text: 'Contract: URL Schema', link: '/specs/008-article-sharing/contracts/url-schema' },
          { text: 'Requirements', link: '/specs/008-article-sharing/checklists/requirements' },
        ],
      },
      {
        text: '009 · Guest Mode',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/009-guest-mode/spec' },
          { text: 'Plan', link: '/specs/009-guest-mode/plan' },
          { text: 'Tasks', link: '/specs/009-guest-mode/tasks' },
          { text: 'Research', link: '/specs/009-guest-mode/research' },
          { text: 'Requirements', link: '/specs/009-guest-mode/checklists/requirements' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/s091648/scrape-and-analyze' },
    ],
    search: {
      provider: 'local',
    },
    outline: {
      level: [2, 3],
    },
  },
})
