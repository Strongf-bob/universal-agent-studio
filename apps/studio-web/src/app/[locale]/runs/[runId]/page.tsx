import {headers} from "next/headers";
import {notFound, redirect} from "next/navigation";

import {RunWorkspace} from "@/features/runs/RunWorkspace";
import {
  ApiClientError,
  getAgentVersionForServer,
  getRunForServer,
} from "@/lib/api/client";
import {isLocale, localizedPath} from "@/lib/i18n/routing";

export default async function RunPage({
  params,
}: {
  params: Promise<{locale: string; runId: string}>;
}) {
  const {locale, runId} = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const cookieHeader = (await headers()).get("cookie") ?? "";
  let run;
  let version;
  try {
    run = await getRunForServer(runId, cookieHeader);
    version = await getAgentVersionForServer(
      run.agent_version_id,
      cookieHeader,
    );
  } catch (error) {
    if (
      error instanceof ApiClientError &&
      error.code === "authentication_required"
    ) {
      redirect(localizedPath(locale, "/login"));
    }
    notFound();
  }
  return <RunWorkspace initialRun={run} version={version} locale={locale} />;
}
