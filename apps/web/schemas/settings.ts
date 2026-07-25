import { z } from "zod";

export const themeModeSchema = z.enum(["light", "dark"]);

export const siteSettingsThemeSchema = z.object({
  publicTheme: themeModeSchema,
});

export type ThemeModeInput = z.infer<typeof themeModeSchema>;
