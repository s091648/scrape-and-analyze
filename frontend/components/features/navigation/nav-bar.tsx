"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { useEffect, useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Rss,
  Settings,
  ChevronDown,
  Globe,
  BookOpen,
  Sun,
  Moon,
  Monitor,
  HelpCircle,
  Menu,
  X,
} from "lucide-react";
import { GitHubLogoIcon } from "@radix-ui/react-icons";
import { ReleaseNotesPopover } from "@/components/features/navigation/release-notes-popover";
import { fetchMe } from "@/lib/api/auth";
import { Skeleton } from "@/components/ui/skeleton";
import { useTopic, useI18n, useTheme, useGuestMode, useTutorial } from "@/lib/providers";

function initials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function NavBar() {
  const { data: session } = useSession();
  const userName =
    session?.user?.name ?? (session?.user as any)?.username ?? session?.user?.email ?? "";
  const [userIcon, setUserIcon] = useState<string | null>(null);
  const [iconLoading, setIconLoading] = useState(false);
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const langDropdownRef = useRef<HTMLDivElement>(null);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const token = (session as any)?.accessToken;
  const { topics, selectedTopic, setSelectedTopicId, isLoading: topicsLoading } = useTopic();
  const { locale, setLocale, availableLanguages, t, isLoading: i18nLoading } = useI18n();
  const { mode, cycleMode } = useTheme();
  const { isGuestMode } = useGuestMode();
  const { openTutorial } = useTutorial();
  const ThemeIcon = mode === "light" ? Sun : mode === "dark" ? Moon : Monitor;
  const themeLabel =
    mode === "light" ? t("theme.light") : mode === "dark" ? t("theme.dark") : t("theme.auto");

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target as Node)) {
        setLangDropdownOpen(false);
      }
      if (
        mobileMenuRef.current &&
        !mobileMenuRef.current.contains(event.target as Node) &&
        !(event.target as Element)?.closest?.("[data-mobile-menu-toggle]")
      ) {
        setMobileMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close the mobile menu on route change — adjusted during render (not in
  // an effect) per React's "adjusting state when a prop changes" pattern.
  const pathname = usePathname();
  const [prevPathname, setPrevPathname] = useState(pathname);
  if (pathname !== prevPathname) {
    setPrevPathname(pathname);
    if (mobileMenuOpen) setMobileMenuOpen(false);
  }

  useEffect(() => {
    if (!token) {
      setUserIcon(null);
      return;
    }
    setIconLoading(true);
    fetchMe(token)
      .then((profile) => setUserIcon(profile?.icon ?? null))
      .finally(() => setIconLoading(false));
  }, [token]);

  const router = useRouter();
  const currentLang = availableLanguages.find((l) => l.code === locale);
  const topicParam = selectedTopic ? `?topic=${selectedTopic.id}` : "";

  return (
    <header className="fixed left-0 top-0 right-0 z-50 w-full border-b border-border bg-background">
      <nav className="container mx-auto px-6 h-16 flex items-center gap-4 md:gap-12 relative">
        <Link href="/" className="flex items-center gap-2 font-bold text-base shrink-0">
          <Rss className="h-4 w-4 text-primary" />
          Scrape Analyzer
        </Link>

        {/* Topic dropdown — desktop only */}
        <div className="relative group hidden md:block">
          <button
            type="button"
            className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted transition-colors"
          >
            {topicsLoading ? (
              <Skeleton className="h-4 w-20" />
            ) : (
              <>
                {selectedTopic?.color_hex && (
                  <span
                    className="inline-block h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: selectedTopic.color_hex }}
                  />
                )}
                <span className="max-w-[120px] truncate">
                  {selectedTopic?.display_name ?? t("nav.selectTopic")}
                </span>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </>
            )}
          </button>
          {!topicsLoading && topics.length > 0 && (
            <div className="absolute left-0 top-full mt-1 w-48 rounded-lg border border-border bg-background shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
              {topics.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelectedTopicId(t.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg ${
                    t.id === selectedTopic?.id ? "font-semibold" : ""
                  }`}
                >
                  {t.color_hex && (
                    <span
                      className="inline-block h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: t.color_hex }}
                    />
                  )}
                  {t.display_name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Left nav — desktop only */}
        <div className="hidden md:flex items-center gap-1">
          <Link
            id="tutorial-target-articles"
            href={`/articles${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === "/articles"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            {t("nav.articles")}
          </Link>
          <Link
            id="tutorial-target-graph"
            href={`/graph${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === "/graph"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            {t("nav.knowledgeGraph")}
          </Link>
          <Link
            id="tutorial-target-tags"
            href={`/tags${topicParam}`}
            className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors duration-200 ${
              pathname === "/tags"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            {t("tags.title")}
          </Link>
        </div>

        {/* Env indicator — only shown in non-production environments */}
        {process.env.APP_ENV !== "production" && (
          <span className="absolute left-1/2 -translate-x-1/2 text-lg font-semibold font-mono text-red-500 select-none pointer-events-none hidden md:inline">
            {process.env.APP_ENV}
          </span>
        )}

        {/* Right nav — desktop only */}
        <div className="ml-auto hidden md:flex items-center gap-4 shrink-0">
          {/* Language dropdown */}
          <div className="relative" ref={langDropdownRef}>
            <button
              id="tutorial-target-language"
              type="button"
              onClick={() => setLangDropdownOpen(!langDropdownOpen)}
              className="flex items-center gap-1.5 text-sm font-medium px-2 py-1.5 rounded-lg border border-border bg-background hover:bg-muted transition-colors"
            >
              <Globe className="h-4 w-4 text-muted-foreground" />
              <span>{i18nLoading ? "..." : currentLang?.native_name || locale}</span>
            </button>
            {langDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-40 rounded-lg border border-border bg-background shadow-lg z-50">
                {availableLanguages.map((lang) => (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => {
                      setLocale(lang.code);
                      setLangDropdownOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted transition-colors first:rounded-t-lg last:rounded-b-lg ${
                      lang.code === locale ? "font-semibold bg-muted/50" : ""
                    }`}
                  >
                    <span>{lang.native_name}</span>
                    {lang.code === locale && <span>✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          <TooltipProvider>
            {(isGuestMode || !!session) && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => { openTutorial(); router.push("/"); }}
                    className="cursor-pointer text-muted-foreground hover:text-foreground transition-colors duration-200"
                    aria-label={t("tutorial.reopenLabel")}
                  >
                    <HelpCircle className="h-5 w-5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent>{t("tutorial.reopenLabel")}</TooltipContent>
              </Tooltip>
            )}

            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  id="tutorial-target-theme"
                  type="button"
                  onClick={cycleMode}
                  className="cursor-pointer text-muted-foreground hover:text-foreground transition-colors duration-200"
                  aria-label={`Theme: ${themeLabel}`}
                >
                  <ThemeIcon className="h-5 w-5" />
                </button>
              </TooltipTrigger>
              <TooltipContent>{themeLabel}</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <a
                  id="tutorial-target-github"
                  href="https://github.com/s091648/scrape-and-analyze"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-foreground transition-colors duration-200"
                >
                  <GitHubLogoIcon className="h-5 w-5" />
                </a>
              </TooltipTrigger>
              <TooltipContent>{t("nav.github")}</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <a
                  id="tutorial-target-docs"
                  href="https://s091648.github.io/scrape-and-analyze"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-foreground transition-colors duration-200"
                >
                  <BookOpen className="h-5 w-5" />
                </a>
              </TooltipTrigger>
              <TooltipContent>{t("nav.specDocs")}</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <ReleaseNotesPopover />

          <TooltipProvider>
            {session && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link
                    href="/settings"
                    className="text-muted-foreground hover:text-foreground transition-colors duration-200"
                  >
                    <Settings size={20} />
                  </Link>
                </TooltipTrigger>
                <TooltipContent>Settings</TooltipContent>
              </Tooltip>
            )}
          </TooltipProvider>

          {session ? (
            <>
              <div className="flex items-center gap-2.5">
                {iconLoading ? (
                  <Skeleton className="h-7 w-7 rounded-full" />
                ) : userIcon ? (
                  <img src={userIcon} className="h-7 w-7 rounded-full object-cover" alt="" />
                ) : (
                  <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold select-none">
                    {initials(userName)}
                  </div>
                )}
                <span className="text-sm font-medium max-w-[120px] truncate">{userName}</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => signOut()}
                className="rounded-full h-8 px-4 text-sm font-medium"
              >
                {t("nav.logout")}
              </Button>
            </>
          ) : (
            <Button asChild size="sm" className="rounded-full h-8 px-4 text-sm font-medium">
              <Link id="tutorial-target-login" href="/login">
                {t("nav.login")}
              </Link>
            </Button>
          )}
        </div>

        {/* Hamburger toggle — mobile only */}
        <button
          type="button"
          data-mobile-menu-toggle
          onClick={() => setMobileMenuOpen((open) => !open)}
          className="ml-auto md:hidden p-2 -mr-2 text-muted-foreground hover:text-foreground transition-colors duration-200"
          aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileMenuOpen}
        >
          {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {/* Mobile menu panel */}
      {mobileMenuOpen && (
        <div
          ref={mobileMenuRef}
          className="md:hidden border-t border-border bg-background max-h-[calc(100vh-4rem)] overflow-y-auto"
        >
          <div className="container mx-auto px-6 py-4 flex flex-col gap-4">
            {!topicsLoading && topics.length > 0 && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  {selectedTopic?.display_name ?? t("nav.selectTopic")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {topics.map((topic) => (
                    <button
                      key={topic.id}
                      type="button"
                      onClick={() => setSelectedTopicId(topic.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-sm transition-colors ${
                        topic.id === selectedTopic?.id ? "bg-muted font-semibold" : "hover:bg-muted"
                      }`}
                    >
                      {topic.color_hex && (
                        <span
                          className="inline-block h-2 w-2 rounded-full shrink-0"
                          style={{ backgroundColor: topic.color_hex }}
                        />
                      )}
                      {topic.display_name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-col gap-1 -mx-2">
              <Link
                href={`/articles${topicParam}`}
                className={`px-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                  pathname === "/articles" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"
                }`}
              >
                {t("nav.articles")}
              </Link>
              <Link
                href={`/graph${topicParam}`}
                className={`px-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                  pathname === "/graph" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"
                }`}
              >
                {t("nav.knowledgeGraph")}
              </Link>
              <Link
                href={`/tags${topicParam}`}
                className={`px-2 py-2 rounded-lg text-sm font-medium transition-colors ${
                  pathname === "/tags" ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/50"
                }`}
              >
                {t("tags.title")}
              </Link>
            </div>

            <div className="h-px bg-border" />

            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2">
                {i18nLoading ? "..." : currentLang?.native_name || locale}
              </p>
              <div className="flex flex-wrap gap-2">
                {availableLanguages.map((lang) => (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => setLocale(lang.code)}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-sm transition-colors ${
                      lang.code === locale ? "bg-muted font-semibold" : "hover:bg-muted"
                    }`}
                  >
                    {lang.native_name}
                    {lang.code === locale && <span>✓</span>}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={cycleMode}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ThemeIcon className="h-4 w-4" />
              {themeLabel}
            </button>

            {(isGuestMode || !!session) && (
              <button
                type="button"
                onClick={() => {
                  openTutorial();
                  router.push("/");
                  setMobileMenuOpen(false);
                }}
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <HelpCircle className="h-4 w-4" />
                {t("tutorial.reopenLabel")}
              </button>
            )}

            <a
              href="https://github.com/s091648/scrape-and-analyze"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <GitHubLogoIcon className="h-4 w-4" />
              {t("nav.github")}
            </a>
            <a
              href="https://s091648.github.io/scrape-and-analyze"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen className="h-4 w-4" />
              {t("nav.specDocs")}
            </a>

            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <ReleaseNotesPopover disableTutorialTargetId />
              {t("nav.releaseNotes")}
            </div>

            <div className="h-px bg-border" />

            {session && (
              <Link
                href="/settings"
                className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <Settings className="h-4 w-4" />
                {t("nav.settings")}
              </Link>
            )}

            {session ? (
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  {iconLoading ? (
                    <Skeleton className="h-7 w-7 rounded-full shrink-0" />
                  ) : userIcon ? (
                    <img src={userIcon} className="h-7 w-7 rounded-full object-cover shrink-0" alt="" />
                  ) : (
                    <div className="h-7 w-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold select-none shrink-0">
                      {initials(userName)}
                    </div>
                  )}
                  <span className="text-sm font-medium truncate">{userName}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => signOut()}
                  className="rounded-full h-8 px-4 text-sm font-medium shrink-0"
                >
                  {t("nav.logout")}
                </Button>
              </div>
            ) : (
              <Button asChild size="sm" className="rounded-full h-8 px-4 text-sm font-medium w-full">
                <Link href="/login">{t("nav.login")}</Link>
              </Button>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
