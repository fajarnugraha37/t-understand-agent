# OpenAPI and AsyncAPI extraction resilience

## Problem

A valid OpenAPI 3 document can declare `servers` as a list of objects:

```yaml
servers:
  - url: https://api.example.test/v1
    description: production
```

The previous extractor iterated the list and passed each mapping directly to a string-slicing helper. That raised `KeyError: slice(None, 500, None)` and aborted repository-wide documentation generation.

## Correct behavior

`t-understand` 1.1.1 normalizes server evidence by contract family:

- OpenAPI 3 list entries use `url` as the server name and preserve description or protocol as detail.
- AsyncAPI named maps retain the logical server name and summarize URL, host, protocol, protocol version, and description.
- Swagger 2 retains host, base path, and schemes.
- Unexpected scalar or structured values are rendered as deterministic bounded text rather than crashing extraction.

## Repository-wide failure isolation

Each file is an evidence source, not a single point of failure. An unexpected adapter exception now creates a `PARTIAL` extraction result with an explicit limitation. Downstream documentation can therefore disclose the affected file and evidence gap while continuing to analyze the rest of the repository.

For this failure class, the exception is contained inside the adapter registry, so the agent no longer receives the raw Python traceback shown in the original report. A different failure outside extraction still follows the existing runtime error behavior and should be reported separately.

## Host invocation contract

OpenCode instructions require prompts to be passed with the named `--prompt` option for both `agent-plan` and `agent-document`. Private retries and investigation details are not part of the final response.

## Regression coverage

The automated suite covers:

- OpenAPI 3 server-object lists;
- AsyncAPI named server maps;
- non-string adapter values;
- unexpected adapter exceptions converted to `PARTIAL` evidence;
- exact `--prompt` command syntax in host instructions;
- traceback and progress-leakage prohibitions in host instructions.
