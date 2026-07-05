"use client";
import { useEffect, useRef, type CSSProperties } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { useTutorial, useI18n, useGuestMode } from "@/lib/providers";
import { getTour } from "@/components/features/tutorial/tutorial-registry";
import { useTutorialTarget } from "@/components/features/tutorial/use-tutorial-target";
import { useIsMobile } from "@/components/features/tutorial/use-is-mobile";

const HIGHLIGHT_PADDING = 6;

export function TutorialOverlay() {
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useI18n();
  const { isGuestMode } = useGuestMode();
  const {
    isTutorialOpen,
    activeTourId,
    tutorialStep,
    closeTutorial,
    nextTutorialStep,
    prevTutorialStep,
  } = useTutorial();

  const tour = activeTourId ? getTour(activeTourId) : undefined;
  const step = tour?.steps[tutorialStep];
  const isMobile = useIsMobile();
  const rect = useTutorialTarget(isTutorialOpen && !isMobile ? step?.targetId : undefined);

  // Anchor the description card to the live target rect via a stable virtual
  // ref (Radix Popper's `virtualRef`), so the ref identity never changes
  // while the rect it reports always reflects the latest measurement. Synced
  // in an effect (not during render) since mutating a ref is a side effect.
  const rectHolder = useRef<DOMRect | null>(null);
  useEffect(() => {
    rectHolder.current = rect;
  }, [rect]);
  const virtualAnchorRef = useRef({
    getBoundingClientRect: () => rectHolder.current ?? new DOMRect(),
  });

  // Navigates on Next/Back step changes *within* an already-open tour. The
  // initial navigation when a tour first opens is the caller's responsibility
  // (see enterGuestMode's and HelpCircle's own router.push) — calling
  // router.push from this effect on the same tick as another push racing to
  // the same destination was observed to leave the page stuck displaying the
  // pre-navigation route's content despite the URL updating.
  const wasOpenRef = useRef(false);
  useEffect(() => {
    const wasOpen = wasOpenRef.current;
    wasOpenRef.current = isTutorialOpen;
    if (!isTutorialOpen || !step || !wasOpen) return;
    if (step.route !== pathname) {
      router.push(step.route);
    }
  }, [isTutorialOpen, step, pathname, router]);

  if (!isTutorialOpen || !tour || !step) return null;

  const isLastStep = tutorialStep === tour.steps.length - 1;
  const isCtaStep = isLastStep && step.isCta === true && isGuestMode;
  const Icon = step.icon;
  const spotlightMode = rect !== null && !isMobile;
  const titleText = t(!isGuestMode && step.titleKeyMember ? step.titleKeyMember : step.titleKey);
  const descriptionText = t(
    !isGuestMode && step.descriptionKeyMember ? step.descriptionKeyMember : step.descriptionKey,
  );

  function goToLogin() {
    closeTutorial();
    router.push("/login");
  }

  function goToRegister() {
    closeTutorial();
    router.push("/register");
  }

  function handleOpenChange(open: boolean) {
    if (!open) closeTutorial();
  }

  const dots = (
    <div className="flex items-center gap-2">
      {tour.steps.map((s, index) => (
        <span
          key={s.id}
          data-testid="tutorial-dot"
          data-active={index === tutorialStep}
          className={`h-2 w-2 rounded-full transition-colors ${
            index === tutorialStep ? "bg-primary" : "bg-muted"
          }`}
        />
      ))}
    </div>
  );

  const progress = (
    <span className="text-xs text-muted-foreground">
      {t("tutorial.stepOf", { current: tutorialStep + 1, total: tour.steps.length })}
    </span>
  );

  const navRow = (
    <div className="flex items-center justify-between pt-2 w-full">
      <div>
        {tutorialStep > 0 && (
          <Button variant="ghost" size="sm" onClick={prevTutorialStep}>
            {t("tutorial.back")}
          </Button>
        )}
      </div>
      <div className="flex items-center gap-2">
        {!isLastStep && (
          <Button variant="link" size="sm" onClick={closeTutorial}>
            {t("tutorial.skip")}
          </Button>
        )}
        {!isLastStep ? (
          <Button size="sm" onClick={nextTutorialStep}>
            {t("tutorial.next")}
          </Button>
        ) : isCtaStep ? (
          <>
            <Button variant="outline" size="sm" onClick={goToRegister}>
              {t("tutorial.register")}
            </Button>
            <Button size="sm" onClick={goToLogin}>
              {t("tutorial.signIn")}
            </Button>
          </>
        ) : (
          <Button size="sm" onClick={closeTutorial}>
            {t("tutorial.done")}
          </Button>
        )}
      </div>
    </div>
  );

  if (spotlightMode && rect) {
    const holeX = rect.left - HIGHLIGHT_PADDING;
    const holeY = rect.top - HIGHLIGHT_PADDING;
    const holeWidth = rect.width + HIGHLIGHT_PADDING * 2;
    const holeHeight = rect.height + HIGHLIGHT_PADDING * 2;
    const ringStyle: CSSProperties = {
      top: holeY,
      left: holeX,
      width: holeWidth,
      height: holeHeight,
    };

    return (
      <>
        {/* Dims the whole viewport with a genuine cutout over the target via
            an SVG mask — a single element, so it isn't subject to the
            unreliable cross-element compositing seen with a `box-shadow:
            0 0 0 9999px` spread next to other `position: fixed` elements
            (e.g. the sticky NavBar) in some browsers. Also blocks all
            interaction while a tour is open; the highlighted target is
            visual-only and intentionally not clickable. */}
        <svg
          data-testid="tutorial-backdrop"
          className="fixed inset-0 z-[100] h-full w-full"
        >
          <defs>
            <mask id="tutorial-spotlight-mask">
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              <rect
                x={holeX}
                y={holeY}
                width={holeWidth}
                height={holeHeight}
                rx="8"
                fill="black"
              />
            </mask>
          </defs>
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            fill="rgba(0,0,0,0.6)"
            mask="url(#tutorial-spotlight-mask)"
          />
        </svg>
        <div
          data-testid="tutorial-highlight"
          className="fixed z-[101] rounded-lg ring-2 ring-white/70 transition-all duration-200 pointer-events-none"
          style={ringStyle}
        />
        <Popover open onOpenChange={handleOpenChange}>
          <PopoverAnchor virtualRef={virtualAnchorRef} />
          <PopoverContent
            className="z-[110] w-80"
            aria-labelledby="tutorial-card-title"
            aria-describedby="tutorial-card-description"
            onInteractOutside={(e) => e.preventDefault()}
          >
            <div className="flex flex-col items-center gap-3 text-center">
              {dots}
              {progress}
              <h2 id="tutorial-card-title" className="text-base font-semibold">
                {titleText}
              </h2>
              <p id="tutorial-card-description" className="text-sm text-muted-foreground">
                {descriptionText}
              </p>
              {navRow}
            </div>
          </PopoverContent>
        </Popover>
      </>
    );
  }

  return (
    <Dialog open onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <div className="flex flex-col items-center gap-4 pt-2 text-center">
          {dots}
          {progress}
          {Icon && (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Icon className="h-6 w-6" />
            </div>
          )}
          <DialogTitle className="text-lg font-semibold">{titleText}</DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            {descriptionText}
          </DialogDescription>
        </div>
        {navRow}
      </DialogContent>
    </Dialog>
  );
}
