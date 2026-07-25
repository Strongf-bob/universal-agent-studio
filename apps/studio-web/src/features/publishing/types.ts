import type {
  ApiKeyCreateRequest,
  ApiKeyCreateView,
  ApiKeyView,
  PublicationState,
  WebhookCreateRequest,
  WebhookCreateView,
  WebhookView,
} from "@universal-agent-studio/contracts";

export interface PublishingApi {
  refresh(agentId: string): Promise<PublicationState>;
  publish(input: {
    agentId: string;
    expectedDraftRevision: number;
    expectedActiveVersionId: string | null;
  }): Promise<PublicationState>;
  rollback(input: {
    agentId: string;
    expectedActiveVersionId: string;
    targetVersionId: string;
  }): Promise<PublicationState>;
  createApiKey(input: {
    agentId: string;
    request: ApiKeyCreateRequest;
  }): Promise<ApiKeyCreateView>;
  revokeApiKey(input: {
    agentId: string;
    keyId: string;
  }): Promise<ApiKeyView>;
  createWebhook(input: {
    agentId: string;
    request: WebhookCreateRequest;
  }): Promise<WebhookCreateView>;
  revokeWebhook(input: {
    agentId: string;
    subscriptionId: string;
  }): Promise<WebhookView>;
}
