import {
  Quote, Eye, TrendingUp, Award, Star, BarChart3, Users, ThumbsUp,
  Download, Share2, Bookmark, Heart, MessageSquare, Flame, Trophy, Hash,
  Percent, Clock, BookOpen, Network,
  type LucideIcon,
} from 'lucide-react'

/**
 * Whitelisted lookup for `metric_definitions.icon_name` — lucide-react has no supported way to
 * dynamically import a component from an arbitrary string, so the maintainer picks from this set
 * when adding a metric (same governance as the rest of the catalog entry, FR-036), and admins pick
 * from this same set when setting a metric's icon (FR-041). Keep in sync with the mirrored
 * `_ICON_WHITELIST` in backend/schemas/metric_definition.py — the backend validates against it too.
 */
export const METRIC_ICONS: Record<string, LucideIcon> = {
  quote: Quote,
  eye: Eye,
  'trending-up': TrendingUp,
  award: Award,
  star: Star,
  'bar-chart': BarChart3,
  users: Users,
  'thumbs-up': ThumbsUp,
  download: Download,
  'share-2': Share2,
  bookmark: Bookmark,
  heart: Heart,
  'message-square': MessageSquare,
  flame: Flame,
  trophy: Trophy,
  hash: Hash,
  percent: Percent,
  clock: Clock,
  'book-open': BookOpen,
  network: Network,
}

export const METRIC_ICON_NAMES: string[] = Object.keys(METRIC_ICONS)

export const DEFAULT_METRIC_ICON: LucideIcon = BarChart3

export function resolveMetricIcon(iconName: string | null | undefined): LucideIcon {
  if (!iconName) return DEFAULT_METRIC_ICON
  return METRIC_ICONS[iconName] ?? DEFAULT_METRIC_ICON
}
