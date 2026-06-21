/**
 * Design tokens for the PlayerNation app.
 *
 * Color usage rules (worth stating explicitly, since the brand color is an
 * unusually high-luminance lime and easy to misuse):
 *   - `brand` (#CDFC00) is an ACCENT, never a body-text color on a light
 *     background -- lime text on white has almost no contrast and is
 *     genuinely hard to read. Use it as a fill (buttons, badges, active
 *     states, the winning score) or as a thin border/underline accent.
 *   - Black text on a `brand` fill reads very clearly (lime is high
 *     luminance), so that's the standard pairing for anything filled with
 *     the brand color -- never white-on-brand.
 *   - Everything else is white/near-black/gray, kept deliberately
 *     minimal: one accent color, one ink color, one gray scale.
 */

export const colors = {
  brand: '#CDFC00',
  brandPressed: '#B7E300',
  ink: '#11140F',
  inkMuted: '#6B7066',
  surface: '#FFFFFF',
  surfaceAlt: '#F5F7F1',
  border: '#E4E7DE',
  danger: '#D64545',
  white: '#FFFFFF',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const;

export const typography = {
  title: { fontSize: 28, fontWeight: '800' as const, color: colors.ink },
  heading: { fontSize: 18, fontWeight: '700' as const, color: colors.ink },
  body: { fontSize: 15, fontWeight: '400' as const, color: colors.ink, lineHeight: 22 },
  bodyMuted: { fontSize: 14, fontWeight: '400' as const, color: colors.inkMuted, lineHeight: 20 },
  label: { fontSize: 12, fontWeight: '700' as const, color: colors.inkMuted, letterSpacing: 0.5 },
  score: { fontSize: 36, fontWeight: '800' as const, color: colors.ink },
} as const;

export const theme = { colors, spacing, radius, typography } as const;

export type Theme = typeof theme;
