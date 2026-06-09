import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Scrape Analyzer',
  description: 'Speckit SDD specification documentation',
  base: process.env.VITEPRESS_BASE || '/',
  ignoreDeadLinks: [/localhost/, /^\.?\/?research\/?$/],
  themeConfig: {
    storybookUrl: process.env.STORYBOOK_URL || '',
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Speckit Guide', link: '/guide/speckit' },
      { text: 'Codespaces', link: '/guide/codespaces' },
      { text: 'Constitution', link: '/constitution' },
      { text: 'Specs', link: '/specs/001-article-collection/spec' },
      { text: 'Architecture', link: '/guide/architecture/uml' },
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
        text: 'Architecture',
        items: [
          { text: 'Pipeline', link: '/guide/architecture/uml' },
          { text: 'Frontend Dependencies', link: '/guide/architecture/deps' },
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
          { text: 'Tasks', link: '/specs/004-translation/tasks' },
          { text: 'Contract: LLM Service Translate', link: '/specs/004-translation/contracts/llm-service-translate' },
          { text: 'Contract: Translation Repository', link: '/specs/004-translation/contracts/translation-repository' },
        ],
      },
      {
        text: '005 · Tag Management',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/005-tag-management/spec' },
          { text: 'Plan', link: '/specs/005-tag-management/plan' },
          { text: 'Data Model', link: '/specs/005-tag-management/data-model' },
          { text: 'Tasks', link: '/specs/005-tag-management/tasks' },
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
          { text: 'Tasks', link: '/specs/006-observability/tasks' },
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
          { text: 'Tasks', link: '/specs/007-scheduler/tasks' },
          { text: 'Contract: Entry Point', link: '/specs/007-scheduler/contracts/entry-point-contract' },
        ],
      },
      {
        text: '008 · Article Sharing',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/008-article-sharing/spec' },
          { text: 'Plan', link: '/specs/008-article-sharing/plan' },
          { text: 'Requirements', link: '/specs/008-article-sharing/checklists/requirements' },
          { text: 'Contract: URL Schema', link: '/specs/008-article-sharing/contracts/url-schema' },
        ],
      },
      {
        text: '009 · Guest Mode',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/009-guest-mode/spec' },
          { text: 'Plan', link: '/specs/009-guest-mode/plan' },
          { text: 'Requirements', link: '/specs/009-guest-mode/checklists/requirements' },
        ],
      },
      {
        text: '010 · Grafana Tracing Charts',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/010-grafana-tracing-charts/spec' },
          { text: 'Plan', link: '/specs/010-grafana-tracing-charts/plan' },
          { text: 'Data Model', link: '/specs/010-grafana-tracing-charts/data-model' },
          { text: 'Requirements', link: '/specs/010-grafana-tracing-charts/checklists/requirements' },
          { text: 'Contract: Grafana Proxy API', link: '/specs/010-grafana-tracing-charts/contracts/grafana-proxy-api' },
        ],
      },
      {
        text: '011 · Semantic Scholar Scraper',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/011-semantic-scholar-scraper/spec' },
          { text: 'Plan', link: '/specs/011-semantic-scholar-scraper/plan' },
          { text: 'Data Model', link: '/specs/011-semantic-scholar-scraper/data-model' },
          { text: 'Tasks', link: '/specs/011-semantic-scholar-scraper/tasks' },
          { text: 'Requirements', link: '/specs/011-semantic-scholar-scraper/checklists/requirements' },
          { text: 'Contract: Keyword Type Enum', link: '/specs/011-semantic-scholar-scraper/contracts/keyword-type-enum' },
          { text: 'Contract: Semantic Scholar API', link: '/specs/011-semantic-scholar-scraper/contracts/semantic-scholar-api' },
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
