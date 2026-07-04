import { Sparkles, Newspaper, GitBranch, LogIn, type LucideIcon } from "lucide-react";

export interface TutorialStep {
  id: string;
  titleKey: string;
  descriptionKey: string;
  icon?: LucideIcon;
  /** DOM id of the element to highlight; undefined = centered card, no highlight. */
  targetId?: string;
  /** Page path this step belongs to; navigated to on step activation if not already there. */
  route: string;
}

export interface TutorialTour {
  id: string;
  kind: "onboarding" | "spotlight";
  /** "spotlight" tours must have every step share the same route. */
  steps: TutorialStep[];
}

export const TUTORIAL_TOURS: TutorialTour[] = [
  {
    id: "guest-onboarding",
    kind: "onboarding",
    steps: [
      {
        id: "welcome",
        route: "/",
        titleKey: "tutorial.step1.title",
        descriptionKey: "tutorial.step1.description",
        icon: Sparkles,
      },
      {
        id: "articles",
        route: "/articles",
        titleKey: "tutorial.step2.title",
        descriptionKey: "tutorial.step2.description",
        icon: Newspaper,
        targetId: "tutorial-target-articles",
      },
      {
        id: "graph",
        route: "/graph",
        titleKey: "tutorial.step3.title",
        descriptionKey: "tutorial.step3.description",
        icon: GitBranch,
        targetId: "tutorial-target-graph",
      },
      {
        id: "cta",
        route: "/",
        titleKey: "tutorial.step4.title",
        descriptionKey: "tutorial.step4.description",
        icon: LogIn,
        targetId: "tutorial-target-login",
      },
    ],
  },
  // Future Feature Spotlight tours are appended here, e.g.:
  // {
  //   id: "feature-chat-2026-07",
  //   kind: "spotlight",
  //   steps: [{ id: "chat", route: "/articles", targetId: "tutorial-target-chat", titleKey: "...", descriptionKey: "..." }],
  // },
];

export function getTour(tourId: string): TutorialTour | undefined {
  return TUTORIAL_TOURS.find((tour) => tour.id === tourId);
}

export function getSpotlightTours(): TutorialTour[] {
  return TUTORIAL_TOURS.filter((tour) => tour.kind === "spotlight");
}
