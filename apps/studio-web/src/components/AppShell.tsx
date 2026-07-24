import { Activity, Bot, CircleCheck } from "lucide-react";
import Link from "next/link";

import {HeaderActions} from "@/components/HeaderActions";
import {type Locale, localizedPath} from "@/lib/i18n/routing";

type Props = {
  children: React.ReactNode;
  locale: Locale;
  messages: {
    common: {
      brand: string;
      brandShort: string;
      language: string;
      skipToContent: string;
      russian: string;
      english: string;
      localWorkspace: string;
      signOut: string;
    };
    nav: {
      agent: string;
      runs: string;
      statusReady: string;
    };
  };
};

export function AppShell({children, locale, messages}: Props) {
  return (
    <>
      <a className="skipLink" href="#main-content">
        {messages.common.skipToContent}
      </a>
      <header className="appHeader">
        <Link
          className="brandLink"
          href={localizedPath(locale, "/agents/calculator-agent")}
        >
          <span className="brandMark" aria-hidden>
            <span />
            <span />
            <span />
          </span>
          <span>
            <strong>{messages.common.brand}</strong>
            <small>{messages.common.localWorkspace}</small>
          </span>
        </Link>
        <nav className="primaryNav" aria-label={messages.common.brand}>
          <Link href={localizedPath(locale, "/agents/calculator-agent")}>
            <Bot aria-hidden />
            {messages.nav.agent}
          </Link>
          <span aria-disabled="true">
            <Activity aria-hidden />
            {messages.nav.runs}
          </span>
        </nav>
        <div className="headerTools">
          <span className="runtimeStatus">
            <CircleCheck aria-hidden />
            {messages.nav.statusReady}
          </span>
          <HeaderActions
            locale={locale}
            languageLabel={messages.common.language}
            russianLabel={messages.common.russian}
            englishLabel={messages.common.english}
            signOutLabel={messages.common.signOut}
          />
        </div>
      </header>
      <main className="appMain" id="main-content" tabIndex={-1}>
        {children}
      </main>
    </>
  );
}
