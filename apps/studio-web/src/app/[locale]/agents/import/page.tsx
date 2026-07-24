import {notFound} from "next/navigation";

import {AgentImportForm} from "@/features/agents/AgentImportForm";
import {getMessages, isLocale} from "@/lib/i18n/routing";

export default async function AgentImportPage({
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
        <p className="eyebrow">{messages.agentImport.eyebrow}</p>
        <h1>{messages.agentImport.title}</h1>
        <p>{messages.agentImport.description}</p>
        <div className="securityCallout">
          <span className="securityGlyph" aria-hidden />
          <p>{messages.agentImport.security}</p>
        </div>
      </div>
      <div className="formCard">
        <AgentImportForm locale={locale} />
      </div>
    </section>
  );
}
