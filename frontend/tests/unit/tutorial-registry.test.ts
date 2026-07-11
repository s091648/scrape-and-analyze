import { describe, it, expect } from "vitest";
import {
  TUTORIAL_TOURS,
  getTour,
  getSpotlightTours,
} from "@/components/features/tutorial/tutorial-registry";

describe("tutorial-registry", () => {
  describe("getTour", () => {
    it("returns the tour matching the given id", () => {
      const tour = getTour("guest-onboarding");
      expect(tour).toBeDefined();
      expect(tour?.kind).toBe("onboarding");
      expect(tour?.steps.length).toBeGreaterThan(0);
    });

    it("returns undefined for an unknown tour id", () => {
      expect(getTour("does-not-exist")).toBeUndefined();
    });
  });

  describe("getSpotlightTours", () => {
    it("returns only tours whose kind is spotlight", () => {
      const spotlightTours = getSpotlightTours();
      expect(spotlightTours.length).toBeGreaterThan(0);
      expect(spotlightTours.every((tour) => tour.kind === "spotlight")).toBe(true);
    });

    it("does not include the onboarding tour", () => {
      const spotlightTours = getSpotlightTours();
      expect(spotlightTours.find((tour) => tour.id === "guest-onboarding")).toBeUndefined();
    });

    it("every spotlight tour's steps share the same route", () => {
      for (const tour of getSpotlightTours()) {
        const routes = new Set(tour.steps.map((step) => step.route));
        expect(routes.size).toBe(1);
      }
    });
  });

  describe("guest-onboarding tour", () => {
    const tour = getTour("guest-onboarding")!;

    it("only the last step is marked as the CTA step", () => {
      const ctaSteps = tour.steps.filter((step) => step.isCta);
      expect(ctaSteps).toHaveLength(1);
      expect(ctaSteps[0].id).toBe(tour.steps[tour.steps.length - 1].id);
    });

    it("the welcome and CTA steps provide member-variant copy", () => {
      const welcomeStep = tour.steps.find((step) => step.id === "welcome");
      const ctaStep = tour.steps.find((step) => step.isCta);
      expect(welcomeStep?.titleKeyMember).toBeTruthy();
      expect(welcomeStep?.descriptionKeyMember).toBeTruthy();
      expect(ctaStep?.titleKeyMember).toBeTruthy();
      expect(ctaStep?.descriptionKeyMember).toBeTruthy();
    });

    it("every step has a non-empty titleKey, descriptionKey, and route", () => {
      for (const step of tour.steps) {
        expect(step.titleKey).toBeTruthy();
        expect(step.descriptionKey).toBeTruthy();
        expect(step.route).toBeTruthy();
      }
    });
  });

  it("every tour in the registry has a unique id", () => {
    const ids = TUTORIAL_TOURS.map((tour) => tour.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
