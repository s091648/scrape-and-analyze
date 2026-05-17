import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import {
  ArticleCardSkeleton,
  ArticleDetailSkeleton,
} from "../components/features/articles/article-card-skeleton";

const meta: Meta = {
  title: "Features/Articles/Skeletons",
  parameters: { layout: "padded" },
};

export default meta;

export const CardSkeleton: StoryObj = {
  render: () => (
    <div className="max-w-sm">
      <ArticleCardSkeleton />
    </div>
  ),
};

export const CardSkeletonGrid: StoryObj = {
  render: () => (
    <div className="grid grid-cols-2 gap-4 max-w-2xl">
      {Array.from({ length: 4 }, (_, i) => (
        <ArticleCardSkeleton key={i} />
      ))}
    </div>
  ),
};

export const DetailSkeleton: StoryObj = {
  render: () => (
    <div className="max-w-2xl border border-border rounded-xl p-6">
      <ArticleDetailSkeleton />
    </div>
  ),
};
