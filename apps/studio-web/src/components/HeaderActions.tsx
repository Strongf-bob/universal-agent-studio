"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {useState} from "react";

import {logoutOwner} from "@/lib/api/client";
import {
  alternateLocale,
  type Locale,
  localizedPath,
} from "@/lib/i18n/routing";

type Props = {
  locale: Locale;
  languageLabel: string;
  russianLabel: string;
  englishLabel: string;
  signOutLabel: string;
};

export function HeaderActions({
  locale,
  languageLabel,
  russianLabel,
  englishLabel,
  signOutLabel,
}: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const otherLocale = alternateLocale(locale);
  const localePrefix = `/${locale}`;
  const localPath = pathname.startsWith(localePrefix)
    ? pathname.slice(localePrefix.length) || "/"
    : "/agents/calculator-agent";
  const authenticatedSurface =
    localPath.startsWith("/agents/") || localPath.startsWith("/runs/");

  async function signOut() {
    setSigningOut(true);
    try {
      await logoutOwner();
    } finally {
      router.replace(localizedPath(locale, "/login"));
      router.refresh();
    }
  }

  return (
    <div className="headerActions">
      <Link
        className="localeSwitch"
        href={localizedPath(otherLocale, localPath)}
        aria-label={languageLabel}
      >
        {otherLocale === "ru-RU" ? russianLabel : englishLabel}
      </Link>
      {authenticatedSurface ? (
        <button
          className="headerSignOut"
          type="button"
          disabled={signingOut}
          onClick={() => void signOut()}
        >
          {signOutLabel}
        </button>
      ) : null}
    </div>
  );
}
