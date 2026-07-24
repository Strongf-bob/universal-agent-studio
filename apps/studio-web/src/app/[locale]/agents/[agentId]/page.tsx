import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { AgentRunner } from "@/features/agents/AgentRunner";
import { ApiClientError, getActiveAgentVersion } from "@/lib/api/client";
import {
  isLocale,
  localizedPath,
} from "@/lib/i18n/routing";

export default async function AgentPage({
  params,
}: {
  params: Promise<{locale: string; agentId: string}>;
}) {
  const {locale, agentId} = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const requestHeaders = await headers();
  let version;
  try {
    version = await getActiveAgentVersion(
      agentId,
      requestHeaders.get("cookie") ?? "",
    );
  } catch (error) {
    if (error instanceof ApiClientError) {
      redirect(
        localizedPath(
          locale,
          error.code === "authentication_failed" ? "/login" : "/agents/import",
        ),
      );
    }
    throw error;
  }
  return <AgentRunner version={version} locale={locale} />;
}
