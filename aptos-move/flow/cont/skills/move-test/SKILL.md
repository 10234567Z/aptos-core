---
name: move-test
description: Generate unit tests for Move functions. Use for test generation, writing tests, or improving coverage.
context: fork
agent: general-purpose
---

**Execute this workflow in a subagent, not inline.** Use the Task tool with `subagent_type: general-purpose` to run this autonomously.

Generate unit tests for Move smart contracts. Analyze target functions to identify behaviors that need testing, then create focused tests following the workflow and rules below.

{% include "templates/unit_test_ref.md" %}
{% include "templates/unit_test_workflow.md" %}
