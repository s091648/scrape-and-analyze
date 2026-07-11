import { test, expect } from "@playwright/test";
import { mockApiRoutes } from "./fixtures/api-handlers";

const availableLanguages = [
  { code: "en", name: "English", native_name: "English" },
  { code: "zh-TW", name: "Traditional Chinese", native_name: "繁體中文" },
];

async function mockLanguages(page: import("@playwright/test").Page, resolved = "en") {
  await page.route(
    (url) => url.pathname === "/api/proxy/languages",
    (route) => route.fulfill({ json: { available: availableLanguages, resolved } }),
  );
}

async function enterGuestMode(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: /continue as guest|以訪客身份繼續/i }).click();
  await page.waitForURL("/");
}

// The highlight box's position is derived from a value that settles shortly
// after the target element mounts (e.g. once an async-loaded article list
// finishes rendering), so a single boundingBox() snapshot can catch it
// mid-settle. Poll until it converges with the actual target instead of
// asserting on one immediate reading.
async function expectHighlightAligned(
  page: import("@playwright/test").Page,
  targetSelector: string,
) {
  await expect
    .poll(
      async () => {
        const highlightBox = await page.getByTestId("tutorial-highlight").boundingBox();
        const targetBox = await page.locator(targetSelector).boundingBox();
        if (!highlightBox || !targetBox) return null;
        return Math.abs(highlightBox.x - targetBox.x);
      },
      { timeout: 5000 },
    )
    .toBeLessThan(20);
}

test.describe("Guest Onboarding Tour", () => {
  test.describe("as guest", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page);
      await mockLanguages(page);
    });

    test('auto-appears as a centered card after clicking "Continue as Guest"', async ({ page }) => {
      await enterGuestMode(page);
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText(/welcome to guest mode|歡迎使用訪客模式/i)).toBeVisible();
    });

    test('"Next" navigates to /articles and highlights the Articles nav link', async ({ page }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^next|下一步$/i }).click();

      await page.waitForURL("/articles");
      await expect(page.getByText(/browse articles|瀏覽文章/i)).toBeVisible();
      await expect(page.getByTestId("tutorial-highlight")).toBeVisible();

      await expectHighlightAligned(page, "#tutorial-target-articles");
    });

    test('"Back" from the Graph step navigates back to /articles', async ({ page }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await page.waitForURL("/articles");
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await page.waitForURL("/graph");

      await page.getByRole("button", { name: /^back|上一步$/i }).click();
      await page.waitForURL("/articles");
      await expect(page.getByText(/browse articles|瀏覽文章/i)).toBeVisible();
    });

    test('"Next" from the Graph step navigates to /tags and highlights the Tags nav link', async ({
      page,
    }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await page.waitForURL("/articles");
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await page.waitForURL("/graph");
      await page.getByRole("button", { name: /^next|下一步$/i }).click();

      await page.waitForURL("/tags");
      await expect(page.getByText(/browse tags|瀏覽標籤/i)).toBeVisible();
      await expect(page.getByTestId("tutorial-highlight")).toBeVisible();
    });

    test("the language, theme, GitHub, Spec Docs, and Release Notes steps highlight their respective NavBar icons", async ({
      page,
    }) => {
      await enterGuestMode(page);
      for (const route of ["/articles", "/graph", "/tags", "/"]) {
        await page.getByRole("button", { name: /^next|下一步$/i }).click();
        await page.waitForURL(route);
      }

      await expect(page.getByText(/switch languages|切換語言/i)).toBeVisible();
      await expectHighlightAligned(page, "#tutorial-target-language");

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/light or dark mode|淺色／深色模式/i)).toBeVisible();
      await expectHighlightAligned(page, "#tutorial-target-theme");

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/explore the source code|探索原始碼/i)).toBeVisible();
      await expectHighlightAligned(page, "#tutorial-target-github");

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/read the specs|閱讀規格文件/i)).toBeVisible();
      await expectHighlightAligned(page, "#tutorial-target-docs");

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/stay updated|掌握最新動態/i)).toBeVisible();
      await expectHighlightAligned(page, "#tutorial-target-release-notes");
    });

    test('"Skip" closes the tour', async ({ page }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^skip|略過$/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();
      await expect(page.getByTestId("tutorial-highlight")).not.toBeVisible();
    });

    test("refreshing the page while still in guest mode reopens the tour", async ({ page }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^skip|略過$/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();

      await page.evaluate(() => sessionStorage.setItem("guest_mode", "true"));
      await page.reload();

      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText(/welcome to guest mode|歡迎使用訪客模式/i)).toBeVisible();
    });

    test("all 10 steps appear in order with correct titles, and the last step highlights the login button", async ({
      page,
    }) => {
      await enterGuestMode(page);

      const titles = [
        /welcome to guest mode|歡迎使用訪客模式/i,
        /browse articles|瀏覽文章/i,
        /explore the knowledge graph|探索知識圖譜/i,
        /browse tags|瀏覽標籤/i,
        /switch languages|切換語言/i,
        /light or dark mode|淺色／深色模式/i,
        /explore the source code|探索原始碼/i,
        /read the specs|閱讀規格文件/i,
        /stay updated|掌握最新動態/i,
        /get full access|取得完整存取權限/i,
      ];

      for (let i = 0; i < titles.length; i++) {
        await expect(page.getByText(titles[i])).toBeVisible();
        if (i < titles.length - 1) {
          await page.getByRole("button", { name: /^next|下一步$/i }).click();
        }
      }

      await expect(page.getByTestId("tutorial-highlight")).toBeVisible();
      await expect(page.getByRole("button", { name: /sign in|登入/i })).toBeVisible();
      await expect(page.getByRole("button", { name: /register|註冊/i })).toBeVisible();
    });

    test('clicking "Sign In" on the last step navigates to /login and closes the tour', async ({
      page,
    }) => {
      await enterGuestMode(page);
      // Articles/Graph/Tags each navigate to a new route; Language/Theme/
      // GitHub/Docs/Release Notes/CTA all stay on "/" since they highlight
      // persistent NavBar icons.
      const routeChangesInOrder = ["/articles", "/graph", "/tags", "/"];
      for (const route of routeChangesInOrder) {
        await page.getByRole("button", { name: /^next|下一步$/i }).click();
        await page.waitForURL(route);
      }
      await expect(page.getByText(/switch languages|切換語言/i)).toBeVisible();
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/light or dark mode|淺色／深色模式/i)).toBeVisible();
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/explore the source code|探索原始碼/i)).toBeVisible();
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/read the specs|閱讀規格文件/i)).toBeVisible();
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/stay updated|掌握最新動態/i)).toBeVisible();
      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/get full access|取得完整存取權限/i)).toBeVisible();

      await page.getByRole("button", { name: /sign in|登入/i }).click();
      await page.waitForURL("/login");
      await expect(page.getByTestId("tutorial-highlight")).not.toBeVisible();
    });

    test("clicking the HelpCircle icon in NavBar reopens the tour from step 1", async ({ page }) => {
      await enterGuestMode(page);
      await page.getByRole("button", { name: /^skip|略過$/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();

      await page.getByLabel(/reopen tutorial|重新開啟教學/i).click();

      await page.waitForURL("/");
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText(/welcome to guest mode|歡迎使用訪客模式/i)).toBeVisible();
    });

    test("tour content renders in Traditional Chinese when app locale is zh-TW", async ({ page }) => {
      await mockLanguages(page, "zh-TW");
      await page.goto("/login");
      await page.evaluate(() => localStorage.setItem("locale", "zh-TW"));
      await page.getByRole("button", { name: /continue as guest|以訪客身份繼續/i }).click();
      await page.waitForURL("/");

      await expect(page.getByText("歡迎使用訪客模式")).toBeVisible();
    });

    test("on a narrow mobile viewport, every step renders as a centered card with no highlight box", async ({
      page,
    }) => {
      await page.setViewportSize({ width: 375, height: 700 });
      await enterGuestMode(page);
      await expect(page.getByRole("dialog")).toBeVisible();

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await page.waitForURL("/articles");
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByTestId("tutorial-highlight")).not.toBeVisible();
    });
  });

  test.describe("as pure unauthenticated (paywall)", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page);
      await mockLanguages(page);
    });

    test("no tour auto-opens and the HelpCircle entry point is not visible", async ({ page }) => {
      await page.goto("/articles");
      await expect(page.getByRole("dialog")).not.toBeVisible();
      await expect(page.getByLabel(/reopen tutorial|重新開啟教學/i)).not.toBeVisible();
    });
  });

  test.describe("as authenticated member", () => {
    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page);
      await mockLanguages(page);
    });

    test("the guest onboarding tour does not auto-open, but HelpCircle reopens it", async ({ page }) => {
      // Mark the unrelated feature-chat spotlight tour as already seen so its
      // dialog doesn't interfere with this guest-onboarding-specific assertion.
      await page.addInitScript(() => {
        localStorage.setItem("tutorial_seen_tours", JSON.stringify(["feature-chat-2026-07"]));
      });
      await page.goto("/articles");
      await expect(page.getByRole("dialog")).not.toBeVisible();

      await page.getByLabel(/reopen tutorial|重新開啟教學/i).click();
      await page.waitForURL("/");
      await expect(page.getByRole("dialog")).toBeVisible();
      // Authenticated members see the member-variant welcome copy, not the
      // guest-facing "Welcome to Guest Mode" text (they're not a guest).
      await expect(page.getByText(/welcome back|歡迎回來/i)).toBeVisible();
    });
  });
});

test.describe("Feature Chat Spotlight Tour", () => {
  // Overrides the shared articleListFixture with an article that has
  // has_vectors: true, so the "pin to chat" sparkles button (and therefore
  // its tutorial-target-chat-pin id) actually renders.
  async function mockArticlesWithVectors(page: import("@playwright/test").Page) {
    await page.route(
      (url) => url.pathname.startsWith("/api/proxy/articles") && !url.pathname.includes("/articles/"),
      (route) =>
        route.fulfill({
          json: {
            items: [
              {
                id: "art-vec-001",
                title: "Digital Twin Innovation",
                source: "rss",
                content: "Digital twins are revolutionizing manufacturing.",
                published_at: "2026-01-15T10:00:00Z",
                scraped_at: "2026-01-16T00:00:00Z",
                url: "https://example.com/digital-twins",
                has_vectors: true,
              },
            ],
            total: 1,
            page: 1,
            size: 20,
          },
        }),
    );
  }

  test.describe("as authenticated member", () => {
    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page);
      await mockArticlesWithVectors(page);
      await mockLanguages(page);
    });

    test("auto-opens on first visit to /articles, highlighting the pin-to-chat sparkles icon", async ({
      page,
    }) => {
      await page.goto("/articles");
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText(/pin articles for context|釘選文章作為上下文/i)).toBeVisible();
      await expect(page.getByTestId("tutorial-highlight")).toBeVisible();

      await expectHighlightAligned(page, "#tutorial-target-chat-pin");
    });

    test('"Next" advances to the chat-toggle step, highlighting the floating chat button, and "Done" closes and persists it as seen', async ({
      page,
    }) => {
      await page.goto("/articles");
      await expect(page.getByText(/pin articles for context|釘選文章作為上下文/i)).toBeVisible();

      await page.getByRole("button", { name: /^next|下一步$/i }).click();
      await expect(page.getByText(/ask the ai assistant|詢問 AI 助理/i)).toBeVisible();

      await expectHighlightAligned(page, "#tutorial-target-chat-toggle");

      // Last step of a non-onboarding tour shows "Done", not Sign In/Register.
      await expect(page.getByRole("button", { name: /^done|完成$/i })).toBeVisible();
      await page.getByRole("button", { name: /^done|完成$/i }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();

      const seenTours = await page.evaluate(() => localStorage.getItem("tutorial_seen_tours"));
      expect(seenTours).toContain("feature-chat-2026-07");

      await page.reload();
      await expect(page.getByRole("dialog")).not.toBeVisible();
    });
  });

  test.describe("as pure unauthenticated (paywall)", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test.beforeEach(async ({ page }) => {
      await mockApiRoutes(page);
      await mockArticlesWithVectors(page);
      await mockLanguages(page);
    });

    test("does not auto-open for paywall users", async ({ page }) => {
      await page.goto("/articles");
      await expect(page.getByRole("dialog")).not.toBeVisible();
    });
  });
});
