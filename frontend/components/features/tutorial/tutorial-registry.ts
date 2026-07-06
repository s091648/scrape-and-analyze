import {
  Sparkles,
  Newspaper,
  GitBranch,
  Tags,
  Globe,
  SunMoon,
  Github,
  BookOpen,
  ScrollText,
  LogIn,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";

export interface TutorialStep {
  id: string;
  titleKey: string;
  descriptionKey: string;
  icon?: LucideIcon;
  /** DOM id of the element to highlight; undefined = centered card, no highlight. */
  targetId?: string;
  /** Page path this step belongs to; navigated to on step activation if not already there. */
  route: string;
  /**
   * Marks this as the sign-up call-to-action step: renders Sign In/Register
   * buttons instead of Next, regardless of whether it's the tour's last
   * step. Only the guest onboarding tour's final step should set this —
   * a Feature Spotlight tour's last step should just close normally. Never
   * applies when the tour is reopened by an already-authenticated member
   * (see `titleKeyMember`/`descriptionKeyMember`).
   */
  isCta?: boolean;
  /**
   * Overrides `titleKey`/`descriptionKey` when the tour is viewed by an
   * already-authenticated member rather than a guest (e.g. reopened via
   * NavBar's HelpCircle). Falls back to `titleKey`/`descriptionKey` when unset.
   */
  titleKeyMember?: string;
  descriptionKeyMember?: string;
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
        titleKeyMember: "tutorial.step1Member.title",
        descriptionKeyMember: "tutorial.step1Member.description",
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
        id: "tags",
        route: "/tags",
        titleKey: "tutorial.step4.title",
        descriptionKey: "tutorial.step4.description",
        icon: Tags,
        targetId: "tutorial-target-tags",
      },
      {
        id: "language",
        route: "/",
        titleKey: "tutorial.step5.title",
        descriptionKey: "tutorial.step5.description",
        icon: Globe,
        targetId: "tutorial-target-language",
      },
      {
        id: "theme",
        route: "/",
        titleKey: "tutorial.step6.title",
        descriptionKey: "tutorial.step6.description",
        icon: SunMoon,
        targetId: "tutorial-target-theme",
      },
      {
        id: "github",
        route: "/",
        titleKey: "tutorial.step7.title",
        descriptionKey: "tutorial.step7.description",
        icon: Github,
        targetId: "tutorial-target-github",
      },
      {
        id: "docs",
        route: "/",
        titleKey: "tutorial.step8.title",
        descriptionKey: "tutorial.step8.description",
        icon: BookOpen,
        targetId: "tutorial-target-docs",
      },
      {
        id: "release-notes",
        route: "/",
        titleKey: "tutorial.step9.title",
        descriptionKey: "tutorial.step9.description",
        icon: ScrollText,
        targetId: "tutorial-target-release-notes",
      },
      {
        id: "cta",
        route: "/",
        titleKey: "tutorial.step10.title",
        descriptionKey: "tutorial.step10.description",
        titleKeyMember: "tutorial.step10Member.title",
        descriptionKeyMember: "tutorial.step10Member.description",
        icon: LogIn,
        targetId: "tutorial-target-login",
        isCta: true,
      },
    ],
  },
  {
    id: "feature-chat-2026-07",
    kind: "spotlight",
    steps: [
      {
        id: "chat-pin",
        route: "/articles",
        titleKey: "tutorial.chatPin.title",
        descriptionKey: "tutorial.chatPin.description",
        icon: Sparkles,
        targetId: "tutorial-target-chat-pin",
      },
      {
        id: "chat-toggle",
        route: "/articles",
        titleKey: "tutorial.chatToggle.title",
        descriptionKey: "tutorial.chatToggle.description",
        icon: MessageSquare,
        targetId: "tutorial-target-chat-toggle",
      },
    ],
  },
];

export function getTour(tourId: string): TutorialTour | undefined {
  return TUTORIAL_TOURS.find((tour) => tour.id === tourId);
}

export function getSpotlightTours(): TutorialTour[] {
  return TUTORIAL_TOURS.filter((tour) => tour.kind === "spotlight");
}
