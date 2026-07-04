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

      const highlightBox = await page.getByTestId("tutorial-highlight").boundingBox();
      const linkBox = await page.locator("#tutorial-target-articles").boundingBox();
      expect(highlightBox).not.toBeNull();
      expect(linkBox).not.toBeNull();
      // Highlight should roughly overlap the highlighted nav link (padding tolerance).
      expect(Math.abs((highlightBox!.x) - (linkBox!.x))).toBeLessThan(20);
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

    test("all 4 steps appear in order with correct titles, and the last step highlights the login button", async ({
      page,
    }) => {
      await enterGuestMode(page);

      const titles = [
        /welcome to guest mode|歡迎使用訪客模式/i,
        /browse articles|瀏覽文章/i,
        /explore the knowledge graph|探索知識圖譜/i,
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
      for (let i = 0; i < 3; i++) {
        await page.getByRole("button", { name: /^next|下一步$/i }).click();
      }
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
      await page.goto("/articles");
      await expect(page.getByRole("dialog")).not.toBeVisible();

      await page.getByLabel(/reopen tutorial|重新開啟教學/i).click();
      await page.waitForURL("/");
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByText(/welcome to guest mode|歡迎使用訪客模式/i)).toBeVisible();
    });
  });
});
