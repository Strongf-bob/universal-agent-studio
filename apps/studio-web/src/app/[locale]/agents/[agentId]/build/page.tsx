import {headers} from "next/headers";
import {notFound, redirect} from "next/navigation";

import {DraftWorkspace} from "@/features/drafts/DraftWorkspace";
import {ApiClientError, getAgentDraftForServer} from "@/lib/api/client";
import {isLocale, localizedPath} from "@/lib/i18n/routing";

export default async function AgentBuildPage({
  params,
  searchParams,
}: {
  params: Promise<{locale: string; agentId: string}>;
  searchParams: Promise<{
    node?: string;
    panel?: string;
    run?: string;
  }>;
}) {
  const {locale, agentId} = await params;
  const restored = await searchParams;
  if (!isLocale(locale)) {
    notFound();
  }
  const cookieHeader = (await headers()).get("cookie") ?? "";
  let draft = null;
  try {
    draft = await getAgentDraftForServer(agentId, cookieHeader);
  } catch (error) {
    if (error instanceof ApiClientError) {
      if (error.code === "authentication_failed") {
        redirect(localizedPath(locale, "/login"));
      }
      if (error.code === "agent_version_not_active") {
        redirect(localizedPath(locale, "/agents/import"));
      }
      if (error.code !== "agent_draft_not_found") {
        throw error;
      }
    } else {
      throw error;
    }
  }
  return (
    <DraftWorkspace
      agentId={agentId}
      initialDraft={draft}
      locale={locale}
      restoredNodeId={restored.node}
      restoredPanel={restored.panel}
      restoredRunId={restored.run}
    />
  );
}
