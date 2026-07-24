import Link from "next/link";
import { notFound } from "next/navigation";

import { OwnerSetupForm } from "@/features/auth/OwnerSetupForm";
import {
  getMessages,
  isLocale,
  localizedPath,
} from "@/lib/i18n/routing";

export default async function SetupPage({
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
    <section className="authLayout">
      <div className="authIntro">
        <p className="eyebrow">{messages.auth.setup.eyebrow}</p>
        <h1>{messages.auth.setup.title}</h1>
        <p>{messages.auth.setup.description}</p>
        <div className="securityCallout">
          <span className="securityGlyph" aria-hidden />
          <p>{messages.common.securityNote}</p>
        </div>
      </div>
      <div className="formCard">
        <OwnerSetupForm locale={locale} />
        <p className="formFooter">
          {messages.auth.setup.loginLinkLead}{" "}
          <Link href={localizedPath(locale, "/login")}>
            {messages.auth.setup.loginLink}
          </Link>
        </p>
      </div>
    </section>
  );
}
