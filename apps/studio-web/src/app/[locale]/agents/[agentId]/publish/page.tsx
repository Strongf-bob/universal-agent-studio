import {headers} from "next/headers";
import {notFound, redirect} from "next/navigation";

import {PublishWorkspace} from "@/features/publishing/PublishWorkspace";
import {
  ApiClientError,
  getPublishingStateForServer,
} from "@/lib/api/client";
import {isLocale, localizedPath} from "@/lib/i18n/routing";

export default async function AgentPublishPage({
  params,
}: {
  params: Promise<{locale: string; agentId: string}>;
}) {
  const {locale, agentId} = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const cookieHeader = (await headers()).get("cookie") ?? "";
  let state;
  try {
    state = await getPublishingStateForServer(agentId, cookieHeader);
  } catch (error) {
    if (error instanceof ApiClientError) {
      if (error.code === "authentication_failed") {
        redirect(localizedPath(locale, "/login"));
      }
      if (
        error.code === "agent_draft_not_found" ||
        error.code === "agent_version_not_active"
      ) {
        redirect(localizedPath(locale, `/agents/${agentId}/build`));
      }
    }
    throw error;
  }
  return (
    <PublishWorkspace
      agentId={agentId}
      initialState={state}
      locale={locale}
    />
  );
}
