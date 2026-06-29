# Data Model: Guest Tutorial Mode

**Feature**: 015-guest-tutorial-mode  
**Date**: 2026-06-29

---

## Entities

### TutorialStep (Static Config — not persisted to DB)

純前端靜態設定，定義 tutorial 的每個步驟。

```typescript
// frontend/components/features/tutorial/tutorial-steps.ts

interface TutorialStep {
  id: string               // Unique step ID (e.g., "welcome", "articles", "graph", "cta")
  titleKey: string         // i18n key for step title
  descriptionKey: string   // i18n key for step description
  icon?: LucideIcon        // Optional Lucide icon component
}

const TUTORIAL_STEPS: TutorialStep[] = [
  {
    id: 'welcome',
    titleKey: 'tutorial.step1.title',
    descriptionKey: 'tutorial.step1.description',
    icon: Sparkles,
  },
  {
    id: 'articles',
    titleKey: 'tutorial.step2.title',
    descriptionKey: 'tutorial.step2.description',
    icon: Newspaper,
  },
  {
    id: 'graph',
    titleKey: 'tutorial.step3.title',
    descriptionKey: 'tutorial.step3.description',
    icon: GitBranch,
  },
  {
    id: 'cta',
    titleKey: 'tutorial.step4.title',
    descriptionKey: 'tutorial.step4.description',
    icon: LogIn,
  },
]
```

### TutorialState (Runtime — in GuestModeContext)

```typescript
// Additions to GuestModeContext (lib/providers/guest-mode-provider.tsx)

interface TutorialState {
  isTutorialOpen: boolean   // Whether Modal is currently visible
  tutorialStep: number      // Current step index (0-based); total = TUTORIAL_STEPS.length
}
```

---

## Storage Schema

### SessionStorage (existing, unchanged)

| Key | Type | Value | Lifetime |
|-----|------|-------|----------|
| `guest_mode` | string | `"true"` | Session (tab) — existing key, not modified |

### LocalStorage (new for this feature)

| Key | Type | Value | Lifetime | Used by |
|-----|------|-------|----------|---------|
| `tutorial_seen_pages` | string | JSON `string[]` e.g. `'["home","graph"]'` | Persistent | Future per-page tutorials |

**Auto-trigger rules (by role)**:

| Role | Auto-show tutorial? | localStorage check? |
|------|--------------------|--------------------|
| 純未登入（paywall） | ❌ Never | ❌ N/A |
| Guest mode | ✅ **Always** (每次進入 guest mode 都顯示) | ❌ No check — unconditional |
| Member (authenticated) | ❌ Never auto-shows | ❌ N/A |

**Write conditions**:
- `tutorial_seen_pages` is appended with a page id (e.g. `"graph"`) when a future page-specific tutorial is completed (MVP: not yet used — reserved for page-level tutorials)

**Read conditions** (future page-specific tutorials):
- A page component reads `tutorial_seen_pages` to decide whether to show its local tutorial step
- The global tutorial modal does NOT check any localStorage key before showing for guests

**Why localStorage (not sessionStorage) for seen_pages**:
- Page-specific tutorial preferences should persist across sessions (e.g. "don't show me the graph tutorial again")
- Members may want to reset: clearing `tutorial_seen_pages` from localStorage re-enables page tutorials

---

## i18n Keys

### New keys to add in `frontend/lib/providers/locales/en.json` and `zh-TW.json`

```json
{
  "tutorial": {
    "stepOf": "Step {{current}} of {{total}}",
    "skip": "Skip",
    "back": "Back",
    "next": "Next",
    "getStarted": "Get Started",
    "signIn": "Sign In",
    "register": "Register",
    "step1": {
      "title": "Welcome to Guest Mode",
      "description": "You're browsing as a guest. Explore our curated AI research articles and knowledge graph — no account needed for this preview."
    },
    "step2": {
      "title": "Browse Articles",
      "description": "The home page shows the latest AI research articles. Use the topic filter to focus on what interests you. As a guest, you can view the first page."
    },
    "step3": {
      "title": "Explore the Knowledge Graph",
      "description": "The Graph page visualizes connections between articles and topics. As a guest, you'll see a preview with the first page of articles."
    },
    "step4": {
      "title": "Get Full Access",
      "description": "Sign in or create a free account to unlock full pagination, personalized settings, and the complete knowledge graph."
    }
  }
}
```

```json
{
  "tutorial": {
    "stepOf": "第 {{current}} 步，共 {{total}} 步",
    "skip": "略過",
    "back": "上一步",
    "next": "下一步",
    "getStarted": "開始探索",
    "signIn": "登入",
    "register": "註冊",
    "step1": {
      "title": "歡迎使用訪客模式",
      "description": "您正以訪客身份瀏覽。探索精選 AI 研究文章與知識圖譜，無需帳號即可預覽。"
    },
    "step2": {
      "title": "瀏覽文章",
      "description": "首頁顯示最新 AI 研究文章。使用主題篩選器聚焦感興趣的領域。訪客可查看第一頁內容。"
    },
    "step3": {
      "title": "探索知識圖譜",
      "description": "圖譜頁面以視覺化方式呈現文章與主題之間的關聯。訪客可預覽第一頁文章的圖譜範圍。"
    },
    "step4": {
      "title": "取得完整存取權限",
      "description": "登入或建立免費帳號，解鎖完整分頁功能、個人化設定，以及完整知識圖譜。"
    }
  }
}
```

---

## State Transitions

```
[User clicks "Continue as Guest"]
        │
        ▼
enterGuestMode()
        │
        └─ ALWAYS → isTutorialOpen=true, tutorialStep=0  (no storage check)

[User logs in (member)]
        │
        └─ tutorial stays closed (isTutorialOpen remains false)
           Member can open manually via HelpCircle

        ▼
[Tutorial Modal Open — Step 0]
        │
        ├─ User clicks "Next" → tutorialStep++
        ├─ User clicks "Back" → tutorialStep--
        ├─ User clicks "Skip" or "X"
        │       → isTutorialOpen=false
        ├─ User reaches last step, clicks "Get Started"
        │       → isTutorialOpen=false
        └─ Guest mode exits (user logs in)
                → exitGuestMode() → isTutorialOpen=false (reset)

[Tutorial Closed — NavBar HelpCircle icon visible for guest OR member]
        │
        └─ User clicks HelpCircle
                → openTutorial() → isTutorialOpen=true, tutorialStep=0
```

---

## Component Tree

```
GuestModeProvider (lib/providers/guest-mode-provider.tsx)  ← state lives here
└─ [existing provider chain ...]
   └─ NavBar (components/features/navigation/nav-bar.tsx)
      └─ HelpCircle icon (guest-only)  ← calls openTutorial()
   └─ TutorialModal (components/features/tutorial/tutorial-modal.tsx)
      └─ Dialog (components/ui/dialog.tsx)
         ├─ TutorialStepDots (inline, dot progress indicator)
         ├─ TutorialStepContent (title + description + icon)
         └─ TutorialNavigation (Back / Next / Skip / CTA buttons)
```

---

## Files to Create / Modify

### New Files
| File | Purpose |
|------|---------|
| `frontend/components/features/tutorial/tutorial-modal.tsx` | Main Tutorial Modal component |
| `frontend/components/features/tutorial/tutorial-steps.ts` | Static step definitions |

### Modified Files
| File | Change |
|------|--------|
| `frontend/lib/providers/guest-mode-provider.tsx` | Add tutorial state + actions |
| `frontend/components/features/navigation/nav-bar.tsx` | Add HelpCircle icon (guest-only) |
| `frontend/lib/providers/locales/en.json` | Add `tutorial.*` keys |
| `frontend/lib/providers/locales/zh-TW.json` | Add `tutorial.*` keys (zh-TW) |

### New Test Files
| File | Purpose |
|------|---------|
| `frontend/tests/unit/tutorial-modal.test.tsx` | Unit tests for TutorialModal + state |
| `frontend/tests/integration/guest-tutorial.spec.ts` | Playwright E2E for tutorial flow |
