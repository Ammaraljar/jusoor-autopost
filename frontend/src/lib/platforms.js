// Display names of the social platforms (ids as used by the server and upload-post).
export const PLATFORM_LABELS = {
  instagram: 'Instagram', facebook: 'Facebook', linkedin: 'LinkedIn', tiktok: 'TikTok', x: 'X', threads: 'Threads',
  pinterest: 'Pinterest', bluesky: 'Bluesky', reddit: 'Reddit', google_business: 'Google Business',
  telegram: 'Telegram', discord: 'Discord', youtube: 'YouTube',
};
export const platformLabel = (p) => PLATFORM_LABELS[p] || p;

/** {platform: {provider, limit, period}} — older settings (one provider for all) read the same way. */
export function channelsOf(p) {
  if (p?.channels && Object.keys(p.channels).length) return p.channels;
  return Object.fromEntries((p?.default_platforms || []).map((x) => [x, { provider: p.default_provider, limit: 0, period: 'week' }]));
}
