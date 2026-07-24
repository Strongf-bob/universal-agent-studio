import Link from "next/link";
import { notFound } from "next/navigation";

import { LoginForm } from "@/features/auth/LoginForm";
import {
  getMessages,
  isLocale,
  localizedPath,
} from "@/lib/i18n/routing";

export default async function LoginPage({
  params,
}: {
  params: Promise<{locale: string}>;
}) {
  const {locale} = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const messages = getMessages(locale);
  return (
    <section className="authLayout authLayoutCompact">
      <div className="authIntro">
        <p className="eyebrow">{messages.auth.login.eyebrow}</p>
        <h1>{messages.auth.login.title}</h1>
        <p>{messages.auth.login.description}</p>
      </div>
      <div className="formCard">
        <LoginForm locale={locale} />
        <p className="formFooter">
          {messages.auth.login.setupLinkLead}{" "}
          <Link href={localizedPath(locale, "/setup")}>
            {messages.auth.login.setupLink}
          </Link>
        </p>
      </div>
    </section>
  );
}
