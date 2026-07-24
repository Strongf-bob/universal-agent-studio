import { NextIntlClientProvider } from "next-intl";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import {
  getMessages,
  isLocale,
  locales,
} from "@/lib/i18n/routing";

export function generateStaticParams() {
  return locales.map((locale) => ({locale}));
}

export default async function LocaleLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{locale: string}>;
}>) {
  const {locale: candidate} = await params;
  if (!isLocale(candidate)) {
    notFound();
  }
  const messages = getMessages(candidate);
  return (
    <NextIntlClientProvider locale={candidate} messages={messages}>
      <div lang={candidate}>
        <AppShell
          locale={candidate}
          messages={{common: messages.common, nav: messages.nav}}
        >
          {children}
        </AppShell>
      </div>
    </NextIntlClientProvider>
  );
}
