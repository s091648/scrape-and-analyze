import { defineConfig } from 'vitepress'

// Spec markdown is plain GFM and may legitimately contain literal "{{ }}" (e.g. GitHub
// Actions expression syntax like ${{ vars.BACKEND_URL }}) inside inline code spans.
// VitePress compiles markdown output as a Vue SFC template; unlike fenced code blocks,
// inline code spans are NOT wrapped in v-pre, so a raw "{{ }}" there gets parsed as a
// real Vue mustache interpolation and crashes the build. Escape braces as HTML entities
// in the rendered <code> output instead of requiring spec authors to hand-write Vue
// escaping (<code v-pre>) in their markdown.
function escapeMustache(md) {
  const renderInlineCode = md.renderer.rules.code_inline
  md.renderer.rules.code_inline = (tokens, idx, options, env, self) => {
    return renderInlineCode(tokens, idx, options, env, self)
      .replace(/\{\{/g, '&#123;&#123;')
      .replace(/\}\}/g, '&#125;&#125;')
  }
}

export default defineConfig({
  title: 'Article Analyzer',
  description: 'Speckit SDD specification documentation',
  base: process.env.VITEPRESS_BASE || '/',
  ignoreDeadLinks: [/localhost/, /^\.?\/?research\/?$/],
  markdown: {
    config: escapeMustache,
  },
  themeConfig: {
    storybookUrl: process.env.STORYBOOK_URL || '',
    backendUrl: process.env.BACKEND_URL || '',
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
          { text: 'Deployment & Multi-Service Releases', link: '/guide/deployment' },
        ],
      },
      {
        text: 'Architecture',
        items: [
          { text: 'Pipeline', link: '/guide/architecture/uml' },
          { text: 'Frontend Dependencies', link: '/guide/architecture/deps' },
          { text: 'DB Schema', link: '/guide/architecture/db-schema' },
          { text: 'API Docs', link: '/guide/architecture/api-docs' },
          { text: 'Exceptions', link: '/guide/architecture/exceptions' },
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
          { text: 'Requirements', link: '/specs/004-translation/checklists/requirements' },
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
          { text: 'Requirements', link: '/specs/005-tag-management/checklists/requirements' },
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
          { text: 'Requirements', link: '/specs/006-observability/checklists/requirements' },
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
          { text: 'Requirements', link: '/specs/007-scheduler/checklists/requirements' },
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
          { text: 'Research', link: '/specs/011-semantic-scholar-scraper/research' },
          { text: 'Quick Start', link: '/specs/011-semantic-scholar-scraper/quickstart' },
          { text: 'Requirements', link: '/specs/011-semantic-scholar-scraper/checklists/requirements' },
          { text: 'Contract: Keyword Type Enum', link: '/specs/011-semantic-scholar-scraper/contracts/keyword-type-enum' },
          { text: 'Contract: Semantic Scholar API', link: '/specs/011-semantic-scholar-scraper/contracts/semantic-scholar-api' },
        ],
      },
      {
        text: '012 · Rag Chatbot Integration',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/012-rag-chatbot-integration/spec' },
          { text: 'Plan', link: '/specs/012-rag-chatbot-integration/plan' },
          { text: 'Data Model', link: '/specs/012-rag-chatbot-integration/data-model' },
          { text: 'Tasks', link: '/specs/012-rag-chatbot-integration/tasks' },
          { text: 'Research', link: '/specs/012-rag-chatbot-integration/research' },
          { text: 'Requirements', link: '/specs/012-rag-chatbot-integration/checklists/requirements' },
          { text: 'Contract: Chat API', link: '/specs/012-rag-chatbot-integration/contracts/chat-api' },
          { text: 'Contract: Rag Sdk', link: '/specs/012-rag-chatbot-integration/contracts/rag-sdk' },
        ],
      },
      {
        text: '013 · Dark Mode Toggle',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/013-dark-mode-toggle/spec' },
          { text: 'Plan', link: '/specs/013-dark-mode-toggle/plan' },
          { text: 'Tasks', link: '/specs/013-dark-mode-toggle/tasks' },
        ],
      },
      {
        text: '014 · Article Recommendation Weekly Report',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/014-article-recommendation-weekly-report/spec' },
          { text: 'Plan', link: '/specs/014-article-recommendation-weekly-report/plan' },
          { text: 'Data Model', link: '/specs/014-article-recommendation-weekly-report/data-model' },
          { text: 'Tasks', link: '/specs/014-article-recommendation-weekly-report/tasks' },
          { text: 'Research', link: '/specs/014-article-recommendation-weekly-report/research' },
          { text: 'Quick Start', link: '/specs/014-article-recommendation-weekly-report/quickstart' },
          { text: 'Requirements', link: '/specs/014-article-recommendation-weekly-report/checklists/requirements' },
          { text: 'Contract: API', link: '/specs/014-article-recommendation-weekly-report/contracts/api' },
        ],
      },
      {
        text: '015 · Guest Tutorial Mode',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/015-guest-tutorial-mode/spec' },
          { text: 'Plan', link: '/specs/015-guest-tutorial-mode/plan' },
          { text: 'Data Model', link: '/specs/015-guest-tutorial-mode/data-model' },
          { text: 'Tasks', link: '/specs/015-guest-tutorial-mode/tasks' },
          { text: 'Contract: Ui', link: '/specs/015-guest-tutorial-mode/contracts/ui-contract' },
        ],
      },
      {
        text: '016 · DB Schema Brushup',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/016-db-schema-brushup/spec' },
          { text: 'Plan', link: '/specs/016-db-schema-brushup/plan' },
          { text: 'Data Model', link: '/specs/016-db-schema-brushup/data-model' },
          { text: 'Tasks', link: '/specs/016-db-schema-brushup/tasks' },
          { text: 'Research', link: '/specs/016-db-schema-brushup/research' },
          { text: 'Quick Start', link: '/specs/016-db-schema-brushup/quickstart' },
          { text: 'Requirements', link: '/specs/016-db-schema-brushup/checklists/requirements' },
        ],
      },
      {
        text: '017 · Exception Handling Guideline',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/017-exception-handling-guideline/spec' },
          { text: 'Plan', link: '/specs/017-exception-handling-guideline/plan' },
          { text: 'Data Model', link: '/specs/017-exception-handling-guideline/data-model' },
          { text: 'Tasks', link: '/specs/017-exception-handling-guideline/tasks' },
          { text: 'Research', link: '/specs/017-exception-handling-guideline/research' },
          { text: 'Quick Start', link: '/specs/017-exception-handling-guideline/quickstart' },
          { text: 'Requirements', link: '/specs/017-exception-handling-guideline/checklists/requirements' },
          { text: 'Contract: Error Response', link: '/specs/017-exception-handling-guideline/contracts/error-response' },
        ],
      },
      {
        text: '018 · Public API Auth',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/018-public-api-auth/spec' },
          { text: 'Plan', link: '/specs/018-public-api-auth/plan' },
          { text: 'Data Model', link: '/specs/018-public-api-auth/data-model' },
          { text: 'Tasks', link: '/specs/018-public-api-auth/tasks' },
          { text: 'Research', link: '/specs/018-public-api-auth/research' },
          { text: 'Quick Start', link: '/specs/018-public-api-auth/quickstart' },
          { text: 'Requirements', link: '/specs/018-public-api-auth/checklists/requirements' },
          { text: 'Contract: Guest Token', link: '/specs/018-public-api-auth/contracts/guest-token' },
        ],
      },
      {
        text: '019 · Cicd Data Migrations',
        collapsed: true,
        items: [
          { text: 'Spec', link: '/specs/019-cicd-data-migrations/spec' },
          { text: 'Plan', link: '/specs/019-cicd-data-migrations/plan' },
          { text: 'Data Model', link: '/specs/019-cicd-data-migrations/data-model' },
          { text: 'Tasks', link: '/specs/019-cicd-data-migrations/tasks' },
          { text: 'Research', link: '/specs/019-cicd-data-migrations/research' },
          { text: 'Quick Start', link: '/specs/019-cicd-data-migrations/quickstart' },
          { text: 'Requirements', link: '/specs/019-cicd-data-migrations/checklists/requirements' },
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
