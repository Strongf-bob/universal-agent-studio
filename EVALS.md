# Evaluation strategy

## 1. Principle

A visually correct workflow is not necessarily a behaviorally correct agent. Every blueprint and important asset must have measurable quality criteria.

## 2. Eval layers

### Deterministic

- schema validation;
- required fields;
- exact transformations;
- tool arguments;
- citation existence;
- permission checks;
- no forbidden values.

### Dataset-based

- expected outcome;
- acceptable variants;
- failure labels;
- language;
- difficulty;
- source data.

### Model-based

Used only where deterministic checks are insufficient:

- relevance;
- completeness;
- style;
- groundedness;
- instruction following.

A model judge is never the only release gate.

### Operational

- cost;
- latency;
- retries;
- tool error rate;
- timeout rate;
- token use.

### Security

- prompt injection;
- data leakage;
- excessive agency;
- unsafe tool selection;
- policy bypass.

## 3. EvalPack contract

Each EvalPack should define:

- purpose;
- compatible blueprint/capability;
- locales;
- dataset;
- evaluators;
- weights;
- hard constraints;
- thresholds;
- model-judge configuration;
- version;
- provenance.

## 4. Autoresearch data split

At minimum:

- research set;
- validation set;
- hidden holdout.

A candidate must not be selected solely on the data used to generate it.

## 5. Release gates

A candidate may become a version only if:

- hard security constraints pass;
- no known critical regression;
- schema/tool tests pass;
- quality improvement is meaningful or cost reduction preserves quality;
- evaluation artifacts are stored;
- a human approves the change.

## 6. Control benchmarks

The repository should contain small non-sensitive benchmark suites for:

- general tool-use agent;
- RAG;
- document generation;
- API automation;
- multilingual behavior;
- model switching;
- recovery from tool failure.
