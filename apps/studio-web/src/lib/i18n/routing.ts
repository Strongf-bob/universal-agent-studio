import enMessages from "@/messages/en-US.json";
import ruMessages from "@/messages/ru-RU.json";

export const locales = ["ru-RU", "en-US"] as const;
export type Locale = (typeof locales)[number];

export function isLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

export function getMessages(locale: Locale) {
  return locale === "ru-RU" ? ruMessages : enMessages;
}

export function alternateLocale(locale: Locale): Locale {
  return locale === "ru-RU" ? "en-US" : "ru-RU";
}

export function localizedPath(locale: Locale, path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `/${locale}${normalized}`;
}
