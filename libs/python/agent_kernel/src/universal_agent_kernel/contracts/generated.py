# Generated from Universal Agent Studio JSON Schema v0.1.0.
# Do not edit manually; run `pnpm generate:contracts`.

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    constr,
)


class DefaultLocale(Enum):
    ru_RU = 'ru-RU'
    en_US = 'en-US'


class Locale(Enum):
    ru_RU = 'ru-RU'
    en_US = 'en-US'


class Mode(Enum):
    form = 'form'
    chat = 'chat'
    hybrid = 'hybrid'


class RequiredCapability(Enum):
    text = 'text'
    structured_output = 'structured_output'
    tool_calling = 'tool_calling'
    vision = 'vision'
    embeddings = 'embeddings'


class Kind(Enum):
    input = 'input'
    model = 'model'
    tool = 'tool'
    output = 'output'


class ErrorCode(Enum):
    invocation_unavailable = 'invocation_unavailable'
    run_cancelled = 'run_cancelled'


class Type(Enum):
    run_started = 'run.started'
    node_started = 'node.started'
    model_requested = 'model.requested'
    model_completed = 'model.completed'
    tool_requested = 'tool.requested'
    tool_completed = 'tool.completed'
    approval_required = 'approval.required'
    approval_resolved = 'approval.resolved'
    node_failed = 'node.failed'
    node_completed = 'node.completed'
    run_completed = 'run.completed'
    run_failed = 'run.failed'
    run_cancelled = 'run.cancelled'


class Status(Enum):
    completed = 'completed'
    failed = 'failed'
    cancelled = 'cancelled'


class Type1(Enum):
    builtin = 'builtin'
    http = 'http'
    openapi = 'openapi'
    mcp = 'mcp'
    sandbox = 'sandbox'


class Adapter(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    ref: str = Field(..., max_length=256, min_length=1)
    type: Type1


class ApprovalPolicy(Enum):
    never = 'never'
    configurable = 'configurable'
    required = 'required'


class KeyStrategy(Enum):
    not_applicable = 'not-applicable'
    run_and_node = 'run-and-node'
    caller_provided = 'caller-provided'


class Idempotency(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    key_strategy: KeyStrategy
    required: bool


class Permission(RootModel[str]):
    root: str = Field(..., pattern='^[a-z][a-z0-9.-]+:[a-z][a-z0-9.-]+$')


class SideEffect(Enum):
    none = 'none'
    read = 'read'
    write = 'write'
    destructive = 'destructive'


class Extensions(
    RootModel[dict[constr(pattern=r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$'), dict[str, Any]]]
):
    root: dict[constr(pattern=r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$'), dict[str, Any]]


class Identifier(RootModel[str]):
    root: str = Field(..., pattern='^[a-z][a-z0-9_-]{2,63}$')


class LocalizedText(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    en_US: str = Field(..., alias='en-US', min_length=1)
    ru_RU: str = Field(..., alias='ru-RU', min_length=1)


class DataClassification(Enum):
    public = 'public'
    internal = 'internal'
    confidential = 'confidential'
    restricted = 'restricted'


class PolicySet(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    data_classification: DataClassification
    redaction_policy_id: Identifier
    retention_policy_id: Identifier


class Semver(RootModel[str]):
    root: str = Field(
        ..., pattern='^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$'
    )


class Sha256(RootModel[str]):
    root: str = Field(..., pattern='^[a-f0-9]{64}$')


class Uuid(RootModel[str]):
    root: str = Field(
        ...,
        pattern='^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    )


class Kind1(Enum):
    model_adapter = 'model_adapter'
    tool = 'tool'
    asset = 'asset'
    capability_pack = 'capability_pack'


class Dependency(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    digest: Sha256
    id: Identifier
    kind: Kind1
    version: Semver


class Signature(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    algorithm: Literal['ed25519']
    key_id: Identifier
    value: str = Field(..., min_length=32)


class InputField(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: Identifier
    label: LocalizedText
    required: bool
    schema_: dict[str, Any] = Field(..., alias='schema')


class Region(RootModel[str]):
    root: str = Field(..., pattern='^[A-Z]{2}$')


class RetentionPolicy(Enum):
    none = 'none'
    provider_default = 'provider-default'
    contractual_zero_retention = 'contractual-zero-retention'


class DataPolicy(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    external_allowed: bool
    regions: list[Region]
    retention_policy: RetentionPolicy
    sensitive_data_allowed: bool


class Parameters(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    max_output_tokens: int = Field(..., ge=1, le=1048576)
    temperature: float = Field(..., ge=0.0, le=2.0)


class Route(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    adapter: str = Field(..., pattern='^[a-z][a-z0-9-]{1,63}$')
    credential_ref: Identifier | None = None
    model: str = Field(..., max_length=128, min_length=1)


class Port(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: Identifier
    schema_: dict[str, Any] = Field(..., alias='schema')


class Backoff(Enum):
    none = 'none'
    fixed = 'fixed'
    exponential = 'exponential'


class RetryPolicy(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    backoff: Backoff
    max_attempts: int = Field(..., ge=1, le=10)


class PublicLocale(Enum):
    ru_RU = 'ru-RU'
    en_US = 'en-US'


class PublicRunCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    input: dict[str, Any]
    locale: PublicLocale


class Type2(Enum):
    run_queued = 'run.queued'
    run_started = 'run.started'
    run_progress = 'run.progress'
    run_completed = 'run.completed'
    run_failed = 'run.failed'
    run_cancelled = 'run.cancelled'


class PublicRunStatus(Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
    cancelled = 'cancelled'


class EventType(Enum):
    publish = 'publish'
    rollback = 'rollback'


class PublicationEventView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    created_at: AwareDatetime
    event_id: Uuid
    event_type: EventType
    previous_version_id: Identifier | None
    selected_version_digest: Sha256
    selected_version_id: Identifier


class PublishRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    expected_active_version_id: Identifier | None
    expected_draft_revision: int = Field(..., ge=1)


class PublishedVersionView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    created_at: AwareDatetime
    digest: Sha256
    version_id: Identifier
    version_number: int = Field(..., ge=1)


class RollbackRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    expected_active_version_id: Identifier
    target_version_id: Identifier


class Cost(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    amount: float = Field(..., ge=0.0)
    currency: str = Field(..., pattern='^[A-Z]{3}$')


class Metrics(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    cost: Cost
    duration_ms: int = Field(..., ge=0)
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    tool_calls: int = Field(..., ge=0)


class Position(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    node_id: Identifier
    x: float = Field(..., ge=-100000.0, le=100000.0)
    y: float = Field(..., ge=-100000.0, le=100000.0)


class Viewport(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    x: float = Field(..., ge=-100000.0, le=100000.0)
    y: float = Field(..., ge=-100000.0, le=100000.0)
    zoom: float = Field(..., ge=0.1, le=4.0)


class Endpoint(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    node_id: Identifier
    port_id: Identifier


class ApiKeyScope(Enum):
    runs_create = 'runs:create'
    runs_read = 'runs:read'
    events_read = 'events:read'


class WebhookEventType(Enum):
    run_completed = 'run.completed'
    run_failed = 'run.failed'
    run_cancelled = 'run.cancelled'


class ModelResolution(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    adapter: str = Field(..., min_length=2)
    model: str = Field(..., min_length=1)
    parameters: dict[str, Any]
    profile_id: Identifier
    prompt_digest: Sha256


class ToolResolution(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    digest: Sha256
    tool_id: Identifier
    version: Semver


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    code: str = Field(..., pattern='^[a-z][a-z0-9_]{2,63}$')
    details: dict[str, Any]
    message_key: str = Field(..., pattern='^[a-z][a-z0-9_.]{2,127}$')
    node_id: Identifier | None = None
    retryable: bool


class InterfaceSchema(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    default_locale: DefaultLocale
    input_fields: list[InputField]
    locales: list[Locale] = Field(..., min_length=2)
    mode: Mode
    result_schema: dict[str, Any]


class PublicRunView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_id: Identifier
    agent_version_digest: Sha256
    agent_version_id: Identifier
    error_code: ErrorCode | None
    events_url: str = Field(
        ...,
        pattern='^/public/v1/agents/[a-z][a-z0-9_-]{2,63}/runs/[0-9a-f-]{36}/events$',
    )
    locale: PublicLocale
    output: dict[str, Any] | None
    run_capability: str | None = Field(None, max_length=1024, min_length=32)
    run_id: Uuid
    schema_version: Literal['0.1.0']
    status: PublicRunStatus
    status_url: str = Field(
        ..., pattern='^/public/v1/agents/[a-z][a-z0-9_-]{2,63}/runs/[0-9a-f-]{36}$'
    )


class RunEvent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    causation_id: Uuid
    correlation_id: Uuid
    error: ErrorEnvelope | None = None
    event_id: Uuid
    node_id: Identifier | None = None
    occurred_at: AwareDatetime
    payload: dict[str, Any]
    redaction_policy_id: Identifier
    run_id: Uuid
    schema_version: Literal['0.1.0']
    sequence: int = Field(..., ge=1)
    type: Type


class RunRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_version_digest: Sha256
    agent_version_id: Identifier
    idempotency_key: str = Field(..., pattern='^[A-Za-z0-9._:-]{16,128}$')
    input: dict[str, Any]
    locale: Locale
    request_id: Uuid
    schema_version: Literal['0.1.0']
    session_id: Uuid | None = None


class CredentialReference(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    credential_ref: Identifier


class LocalizedMetadata(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    description: LocalizedText
    name: LocalizedText


class Layout(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    nodes: list[Position] = Field(..., max_length=256)
    viewport: Viewport


class Edge(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: Identifier
    source: Endpoint
    target: Endpoint


class PublicRunEvent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    error_code: ErrorCode | None
    occurred_at: AwareDatetime
    output: dict[str, Any] | None
    schema_version: Literal['0.1.0']
    sequence: int = Field(..., ge=1)
    status: PublicRunStatus
    type: Type2


class ApiKeyCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    expires_at: AwareDatetime | None
    label: str = Field(..., max_length=120, min_length=1)
    scopes: list[ApiKeyScope] = Field(..., min_length=1)


class ApiKeyView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    created_at: AwareDatetime
    expires_at: AwareDatetime | None
    key_id: Uuid
    label: str
    last_used_at: AwareDatetime | None
    prefix: str = Field(..., pattern='^[a-f0-9]{16}$')
    revoked_at: AwareDatetime | None
    scopes: list[ApiKeyScope] = Field(..., min_length=1)


class WebhookCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    events: list[WebhookEventType] = Field(..., min_length=1)
    label: str = Field(..., max_length=120, min_length=1)
    target_url: AnyUrl


class WebhookView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    created_at: AwareDatetime
    events: list[WebhookEventType] = Field(..., min_length=1)
    label: str
    revoked_at: AwareDatetime | None
    subscription_id: Uuid
    target_url: AnyUrl


class NodeExecution(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attempt: int = Field(..., ge=1)
    completed_at: AwareDatetime
    duration_ms: int = Field(..., ge=0)
    error: ErrorEnvelope | None = None
    input: dict[str, Any]
    node_id: Identifier
    output: dict[str, Any]
    started_at: AwareDatetime
    status: Status


class Provenance(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    model_resolutions: list[ModelResolution]
    redaction_policy_id: Identifier
    tool_resolutions: list[ToolResolution]


class ModelProfile(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    data_policy: DataPolicy
    extensions: Extensions
    id: Identifier
    localized_metadata: LocalizedMetadata
    parameters: Parameters
    required_capabilities: list[RequiredCapability]
    routes: list[Route] = Field(..., min_length=1)


class NodeSpec(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    config: dict[str, Any]
    extensions: Extensions
    id: Identifier
    input_ports: list[Port]
    kind: Kind
    localized_metadata: LocalizedMetadata
    model_profile_ref: Identifier | None = None
    output_ports: list[Port]
    retry_policy: RetryPolicy
    timeout_ms: int = Field(..., ge=1, le=3600000)
    tool_ref: Identifier | None = None
    type: str = Field(..., pattern='^[a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*$')
    version: Semver


class PublicAgentView(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_id: Identifier
    agent_version_digest: Sha256
    agent_version_id: Identifier
    interface: InterfaceSchema
    localized_metadata: LocalizedMetadata
    schema_version: Literal['0.1.0']


class PublicationState(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    active_version_id: Identifier | None
    agent_id: Identifier
    api_keys: list[ApiKeyView]
    draft_digest: Sha256
    draft_revision: int = Field(..., ge=1)
    events: list[PublicationEventView]
    schema_version: Literal['0.1.0']
    versions: list[PublishedVersionView]
    webhooks: list[WebhookView]


class RunTrace(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_version_digest: Sha256
    agent_version_id: Identifier
    completed_at: AwareDatetime
    error: ErrorEnvelope | None = None
    events: list[RunEvent] = Field(..., min_length=2)
    input: dict[str, Any]
    metrics: Metrics
    node_executions: list[NodeExecution]
    output: dict[str, Any]
    provenance: Provenance
    request_id: Uuid
    run_id: Uuid
    schema_version: Literal['0.1.0']
    started_at: AwareDatetime
    status: Status


class ToolManifest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    adapter: Adapter
    approval_policy: ApprovalPolicy
    credential_refs: list[CredentialReference]
    extensions: Extensions
    id: Identifier
    idempotency: Idempotency
    input_schema: dict[str, Any]
    localized_metadata: LocalizedMetadata
    output_schema: dict[str, Any]
    permissions: list[Permission]
    side_effect: SideEffect
    version: Semver


class ApiKeyCreateView(ApiKeyView):
    secret: str = Field(..., pattern='^uas_live_[a-f0-9]{16}_[A-Za-z0-9_-]{43}$')


class WebhookCreateView(WebhookView):
    secret: str = Field(..., pattern='^whsec_[A-Za-z0-9_-]{43}$')


class AgentSpec(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_id: Identifier
    edges: list[Edge]
    extensions: Extensions
    interface: InterfaceSchema
    localized_metadata: LocalizedMetadata
    model_profiles: list[ModelProfile]
    nodes: list[NodeSpec] = Field(..., min_length=1)
    policies: PolicySet
    revision: int = Field(..., ge=1)
    schema_version: Literal['0.1.0']
    tools: list[ToolManifest]


class AgentVersion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_id: Identifier
    agent_spec: AgentSpec
    agent_spec_digest: Sha256
    created_at: AwareDatetime
    dependency_lock: list[Dependency]
    schema_version: Literal['0.1.0']
    signature: Signature | None = None
    status: Literal['published']
    version_id: Identifier
    version_number: int = Field(..., ge=1)


class AgentDraft(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_id: Identifier
    agent_spec: AgentSpec
    base_version_id: Identifier
    digest: Sha256
    draft_id: Identifier
    layout: Layout
    revision: int = Field(..., ge=1)
    schema_version: Literal['0.1.0']
    updated_at: AwareDatetime


class ContractBundle(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    agent_draft: AgentDraft | None = None
    agent_spec: AgentSpec | None = None
    agent_version: AgentVersion | None = None
    api_key_create_request: ApiKeyCreateRequest | None = None
    api_key_create_view: ApiKeyCreateView | None = None
    error_envelope: ErrorEnvelope | None = None
    interface_schema: InterfaceSchema | None = None
    model_profile: ModelProfile | None = None
    node_spec: NodeSpec | None = None
    public_agent: PublicAgentView | None = None
    public_run: PublicRunView | None = None
    public_run_create_request: PublicRunCreateRequest | None = None
    public_run_event: PublicRunEvent | None = None
    publication: PublicationState | None = None
    publish_request: PublishRequest | None = None
    rollback_request: RollbackRequest | None = None
    run_event: RunEvent | None = None
    run_request: RunRequest | None = None
    run_trace: RunTrace | None = None
    tool_manifest: ToolManifest | None = None
    webhook_create_request: WebhookCreateRequest | None = None
    webhook_create_view: WebhookCreateView | None = None
