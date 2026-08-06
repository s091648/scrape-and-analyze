"use client";
import { usePathname } from "next/navigation";
import { NavBar } from "@/components/features/navigation/nav-bar";
import { ErrorBoundary } from "@/components/common/error-boundary";
import { FloatingChatbotWrapper } from "@/components/features/chat/FloatingChatbotWrapper";
import { TutorialOverlay } from "@/components/features/tutorial/tutorial-overlay";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isStandalone = pathname.startsWith("/articles/");
  const isFullBleed = pathname === '/'
  const isChatPath = ["/articles", "/graph", "/tags"].includes(pathname);

  const mainClassName = isStandalone
    ? 'min-h-screen flex items-center justify-center p-6'
    : isFullBleed
      ? 'relative mt-16 h-[calc(100vh-4rem)]'
      : 'container mx-auto px-6 py-8 pt-24'

  return (
    <ErrorBoundary>
      {!isStandalone && <NavBar />}
      <TutorialOverlay />
      <main className={mainClassName}>
        {children}
      </main>
      {isChatPath && <FloatingChatbotWrapper />}
    </ErrorBoundary>
  );
}
