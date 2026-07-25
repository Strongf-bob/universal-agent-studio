import type {Metadata} from "next";
import {notFound} from "next/navigation";

import {PublicAgentApp} from "@/components/PublicAgentApp";
import {getPublicAgent, PublicApiError} from "@/lib/api";
import {isLocale} from "@/lib/i18n";

interface PageProps {
  params: Promise<{agentId: string; locale: string}>;
}

async function loadAgent(agentId: string) {
  try {
    return await getPublicAgent(agentId);
  } catch (error) {
    if (error instanceof PublicApiError && error.status === 404) {
      notFound();
    }
    throw error;
  }
}

export async function generateMetadata({params}: PageProps): Promise<Metadata> {
  const {agentId, locale} = await params;
  if (!isLocale(locale)) {
    return {};
  }
  const agent = await loadAgent(agentId);
  return {
    title: `${agent.localized_metadata.name[locale]} · Universal Agent Studio`,
    description: agent.localized_metadata.description[locale],
  };
}

export default async function PublishedAgentPage({params}: PageProps) {
  const {agentId, locale} = await params;
  if (!isLocale(locale)) {
    notFound();
  }
  const agent = await loadAgent(agentId);
  if (!agent.interface.locales.includes(locale)) {
    notFound();
  }
  return <PublicAgentApp agent={agent} locale={locale} />;
}
