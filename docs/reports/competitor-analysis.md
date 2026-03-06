# Xiaotie v2.0 Competitor Analysis: Top Coding CLI Agents (March 2026)

> Research conducted: 2026-03-06
> Purpose: Identify best architectures, patterns, and features for Xiaotie v2.0 design

---

## Executive Summary

The coding CLI agent landscape in early 2026 is rapidly maturing, with 12 major players spanning from terminal-native tools to full IDE integrations. Key trends include:

1. **Sub-agent architectures** are becoming standard (Claude Code, Cursor, Codex, Goose)
2. **MCP (Model Context Protocol)** is the de facto plugin standard
3. **Sandboxing** is now expected, not optional
4. **Multi-model support** is table stakes
5. **Context window management** (compaction, repo maps, sub-agent delegation) differentiates winners
6. **Skills/modes systems** enable extensible, role-based agent behavior

---

## Detailed Project Analysis

### 1. Claude Code (Anthropic)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~74.2K |
| **License** | Proprietary (closed source) |
| **Language** | TypeScript/Node.js |
| **Architecture Pattern** | ReAct + Sub-agent delegation (Explore/Plan/Task agents) |
| **Context Window** | 200K tokens; automatic compaction; sub-agents use Haiku for fast token processing |
| **Models** | Claude Opus 4.6, Sonnet 4.6, Haiku 4.5 |
| **Multi-model** | Anthropic models only |
| **Plugin System** | MCP servers, Skills (.md files with metadata), Hooks (lifecycle events), Custom agents |
| **Security** | OS-level sandboxing (macOS Seatbelt, Linux bubblewrap), filesystem + network isolation, permission-based approval, deny-rules priority. Sandboxing reduces prompts by 84%, attack surface by 95% |
| **Context Strategy** | Automatic conversation compaction, sub-agent context isolation, CLAUDE.md hierarchy, repo-aware context |
| **Key Features** | Sub-agents (Explore/Plan/Task), Skills system with progressive disclosure, Hooks for automation, Git integration, IDE extension, GitHub Actions agent |
| **Community** | Very active ecosystem (awesome-claude-code, skills repos, templates) |
| **Strengths** | Best reasoning quality, excellent security model, mature skills/hooks ecosystem, strong sub-agent architecture |
| **Weaknesses** | Vendor lock-in (Anthropic only), expensive ($200/mo Pro), closed source |

### 2. Codex CLI (OpenAI)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~62K |
| **License** | Open Source (Apache 2.0) |
| **Language** | Rust |
| **Architecture Pattern** | ReAct + Cloud sandbox + Local CLI dual-mode |
| **Context Window** | 400K tokens (GPT-5.3-Codex-Spark), 128K max output |
| **Models** | GPT-5.3-Codex-Spark, GPT-5.2, o3, o4-mini |
| **Multi-model** | OpenAI models only |
| **Plugin System** | MCP servers, Skills with progressive disclosure, plugin marketplace |
| **Security** | Three approval modes (Auto/Read-only/Full Access), cloud sandbox isolation, working directory scoping |
| **Context Strategy** | Massive 400K context, session resume with local transcripts, cloud task parallelism |
| **Key Features** | Cloud exec with best-of-N runs, voice input, sub-agent forking, session resume, MCP server mode, JetBrains/Xcode integration |
| **Community** | Strong (backed by OpenAI ecosystem) |
| **Strengths** | Fastest inference (1000+ tok/s on Cerebras), cloud task offloading, Rust performance, voice coding |
| **Weaknesses** | Vendor lock-in (OpenAI only), requires subscription plan |

### 3. Gemini CLI (Google)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~96K |
| **License** | Apache 2.0 |
| **Language** | TypeScript |
| **Architecture Pattern** | ReAct (CLI frontend + Core backend, modular tools) |
| **Context Window** | 1M tokens (Gemini 3 Pro) |
| **Models** | Gemini 3 Pro, Gemini 3 Flash |
| **Multi-model** | Google models only |
| **Plugin System** | MCP support, extensible tool system, GEMINI.md context files |
| **Security** | Multi-layer sandboxing (macOS Seatbelt, Docker/Podman, LXC), user approval system, network isolation. Recent security fix for whitelist bypass |
| **Context Strategy** | 1M token window, GEMINI.md hierarchical context, modular tool architecture |
| **Key Features** | Free tier (60 req/min, 1000/day), Google Search grounding, GitHub Actions integration, modular CLI/Core split |
| **Community** | Largest by stars (96K), 11.9K forks, very active |
| **Strengths** | Free tier, largest context window, massive community, clean modular architecture |
| **Weaknesses** | Google models only, less mature agentic features, recent security vulnerabilities |

### 4. Aider

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~41K |
| **License** | Apache 2.0 |
| **Language** | Python |
| **Architecture Pattern** | Repo Map + Edit Format (tree-sitter AST + PageRank graph ranking) |
| **Context Window** | Dynamic (adjusts repo map via --map-tokens, default 1K tokens for map) |
| **Models** | Any LLM (Claude, GPT-4, DeepSeek, Gemini, local models via Ollama) |
| **Multi-model** | Yes - truly model-agnostic |
| **Plugin System** | No formal plugin system; extensible via LLM provider configuration |
| **Security** | Minimal (runs with user permissions, no sandboxing) |
| **Context Strategy** | **Innovative**: Tree-sitter AST parsing -> NetworkX graph -> PageRank ranking -> token-budgeted repo map. Disk-cached tags, dynamic context sizing |
| **Key Features** | Repo map with 100+ language support, automatic git commits, linting/testing integration, voice coding, multi-modal input, IDE comments integration |
| **Community** | 5.1M installs, mature project |
| **Strengths** | Best repo map/context strategy, truly model-agnostic, proven at scale, excellent git integration |
| **Weaknesses** | No sandboxing, no plugin system, Python performance, simpler agent loop |

### 5. Continue.dev

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~26K |
| **License** | Apache 2.0 |
| **Language** | TypeScript |
| **Architecture Pattern** | CI/CD Agent (headless mode for PR checks, TUI for interactive) |
| **Context Window** | Model-dependent |
| **Models** | Any (OpenAI, Anthropic, Mistral, local via Ollama/LM Studio) |
| **Multi-model** | Yes |
| **Plugin System** | Rules-as-code (.continue/rules/), integrations (GitHub, Sentry, Snyk) |
| **Security** | CI/CD isolation via headless mode, configuration-as-code governance |
| **Context Strategy** | Codebase + documentation awareness, rule-based context injection |
| **Key Features** | AI checks on PRs (markdown-defined), Agent mode for multi-file ops, headless + TUI modes, GitHub/Sentry/Snyk integration |
| **Community** | Strong (YC S23, Hugging Face angel investors) |
| **Strengths** | Unique CI/CD-first approach, team collaboration focus, async PR automation |
| **Weaknesses** | Pivoted mid-2025 (less mature new direction), smaller community |

### 6. OpenCode

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~112K |
| **License** | MIT |
| **Language** | TypeScript (client/server), Go (CLI) |
| **Architecture Pattern** | Client/Server with TUI (Bubble Tea for Go TUI, Vercel AI SDK) |
| **Context Window** | Model-dependent |
| **Models** | 75+ providers (OpenAI, Anthropic, Gemini, Bedrock, Groq, Azure, local) |
| **Multi-model** | Yes - most providers of any tool |
| **Plugin System** | MCP support, ACP (Agent Client Protocol) for IDE integration |
| **Security** | Privacy-first (no code storage), standard permission model |
| **Context Strategy** | Session management with SQLite persistence, LSP integration for code intelligence |
| **Key Features** | TUI with Vim keybindings, 75+ providers, desktop app (Tauri), ACP for JetBrains/Zed/Neovim, session persistence, remote operation |
| **Community** | Largest community (112K stars, 700+ contributors, 2.5M monthly users) |
| **Strengths** | Maximum provider flexibility, beautiful TUI, desktop + CLI + IDE, remote operation |
| **Weaknesses** | Less sophisticated agentic features, no sandboxing, breadth over depth |

### 7. Cline

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~58K |
| **License** | Apache 2.0 |
| **Language** | TypeScript |
| **Architecture Pattern** | Plan-and-Act dual mode (Plan mode -> Act mode execution) |
| **Context Window** | Model-dependent |
| **Models** | OpenRouter, Anthropic, OpenAI, Gemini, Bedrock, Azure, local models |
| **Multi-model** | Yes |
| **Plugin System** | MCP for extensibility, VS Code extension architecture |
| **Security** | Human-in-the-loop GUI approval for every file change and command, cost tracking |
| **Context Strategy** | File structure + AST analysis, regex search, selective file reading |
| **Key Features** | Autonomous agent in VS Code, diff view editing, browser launching/screenshots, compiler error monitoring, iterative self-correction, enterprise features (SSO, audit trails) |
| **Community** | 5M+ installs, $32M funding (Emergence Capital) |
| **Strengths** | Best VS Code integration, human-in-the-loop safety, enterprise features, strong funding |
| **Weaknesses** | VS Code only, lower benchmark scores (especially backend), IDE-dependent |

### 8. Roo Code

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~22K |
| **License** | Apache 2.0 |
| **Language** | TypeScript |
| **Architecture Pattern** | Multi-mode agent (Code/Architect/Ask modes + Custom Modes) |
| **Context Window** | Model-dependent, partial-file analysis and summarization |
| **Models** | OpenRouter, Anthropic, OpenAI, Gemini, Bedrock, Azure, local |
| **Multi-model** | Yes |
| **Plugin System** | Custom Modes with scoped tool permissions, Mode Gallery for sharing |
| **Security** | Mode-based permission scoping, tool permission gating, SOC 2 Type 2 compliance |
| **Context Strategy** | Partial-file analysis, summarization, user-specified context |
| **Key Features** | 5 built-in modes, Custom Modes (security reviewer, test writer, architect), Cloud Agents, Mode Gallery, enterprise features |
| **Community** | 22K stars, 300 contributors, 1.2M VS Code installs |
| **Strengths** | Most flexible mode/persona system, reliable on large changes, enterprise-ready, good reputation for reliability |
| **Weaknesses** | Forked from Cline (differentiation challenge), VS Code-centric, smaller community |

### 9. Amp (Sourcegraph)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | Not publicly disclosed (closed source core) |
| **License** | Proprietary (examples repo is open) |
| **Language** | TypeScript |
| **Architecture Pattern** | Code Graph + Sub-agents (Oracle/Librarian sub-agents, composable tool system) |
| **Context Window** | Leverages Sourcegraph's global code graph for semantic context |
| **Models** | Claude Opus, Claude Sonnet, GPT-5 series (Deep mode uses GPT-5.2-Codex) |
| **Multi-model** | Yes (multiple providers) |
| **Plugin System** | Agent Skills, composable tools (Painter, code review agent, walkthrough skill) |
| **Security** | Sourcegraph's granular permission model, enterprise access controls |
| **Context Strategy** | **Unique**: Sourcegraph code graph for semantic understanding across repositories, real-time context aggregation, dependency tree analysis |
| **Key Features** | Deep mode (extended reasoning), Oracle/Librarian sub-agents, code review agent, cross-repo understanding, VS Code/JetBrains/Neovim support |
| **Community** | Sourcegraph enterprise community |
| **Strengths** | Best cross-repo understanding (code graph), Deep mode for complex tasks, no vendor lock-in on models |
| **Weaknesses** | Proprietary, depends on Sourcegraph infrastructure, less community visibility |

### 10. Goose (Block)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | ~27K |
| **License** | Apache 2.0 |
| **Language** | Rust |
| **Architecture Pattern** | MCP-native agent (tool calling via MCP, modular crate architecture) |
| **Context Window** | Model-dependent |
| **Models** | Claude, GPT-4, Gemini, DeepSeek, local models (Ollama, llama.cpp) |
| **Multi-model** | Yes |
| **Plugin System** | MCP-first extensibility, plug-and-play architecture |
| **Security** | Local-first operation, no cloud dependency, user permission model |
| **Context Strategy** | Sub-agent parallelism with isolated workspaces |
| **Key Features** | Subagents for parallel execution, local llama.cpp inference, desktop app (Electron), CLI + GUI, Telegram gateway, IDE integration (VS Code, Cursor, JetBrains via ACP) |
| **Community** | 27K stars, 362 contributors, 102 releases |
| **Strengths** | Free + local-first, Rust performance, MCP-native, model-agnostic, sub-agent parallelism |
| **Weaknesses** | Less polished than commercial tools, newer project |

### 11. Cursor (Agent Mode)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | N/A (proprietary product) |
| **License** | Proprietary |
| **Language** | TypeScript (VS Code fork) |
| **Architecture Pattern** | Async sub-agent tree + Cloud parallel agents (up to 8 VMs) |
| **Context Window** | Custom embedding model for codebase recall |
| **Models** | GPT-5.2, Claude Sonnet/Opus 4.5, Gemini 3 Pro, Grok Code |
| **Multi-model** | Yes |
| **Plugin System** | Agent Skills (SKILL.md), MCP integrations, Automations (trigger-based) |
| **Security** | Cloud VM isolation, enterprise controls |
| **Context Strategy** | Custom embedding model for recall, async sub-agent tree, cloud sandbox isolation |
| **Key Features** | Cloud agents (8 parallel VMs), Automations (schedule/event-triggered), long-running agents, subagent trees, JetBrains via ACP, Slack/GitHub/PagerDuty triggers, agent memory |
| **Community** | Dominant market share among AI IDEs |
| **Strengths** | Most advanced automation system, cloud parallel agents, long-running agent support, broadest IDE integration |
| **Weaknesses** | Proprietary, expensive, not a CLI tool (IDE-centric) |

### 12. Windsurf (Cognition AI, formerly Codeium)

| Attribute | Details |
|-----------|---------|
| **GitHub Stars** | N/A (proprietary product) |
| **License** | Proprietary |
| **Language** | TypeScript (VS Code fork) |
| **Architecture Pattern** | Cascade (proprietary agentic engine with memory layer) |
| **Context Window** | Full codebase comprehension via Cascade |
| **Models** | Multiple (details not fully disclosed) |
| **Multi-model** | Yes |
| **Plugin System** | Windsurf Plugins (VS Code compatible), MCP integrations (GitHub, Slack, Stripe, Figma) |
| **Security** | SOC 2 Type II, cloud/hybrid/self-hosted deployment, admin controls |
| **Context Strategy** | Cascade's persistent memory layer, full repo comprehension, multi-file reasoning |
| **Key Features** | Cascade AI engine, Tab/Supercomplete, Turbo Mode (autonomous execution), live previews, auto lint fix, persistent memory, Netlify deployment |
| **Community** | #1 LogRocket AI Dev Tool ranking (Feb 2026) |
| **Strengths** | Deepest IDE integration, Cascade memory/reasoning, live preview, backed by Cognition (Devin) |
| **Weaknesses** | Proprietary, stability issues (high CPU, crashes), acquired company (integration risks) |

---

## Comparison Matrix

### Stars & Community Health

| Project | Stars | License | Contributors | Language |
|---------|-------|---------|-------------|----------|
| OpenCode | 112K | MIT | 700+ | TS/Go |
| Gemini CLI | 96K | Apache 2.0 | Large | TypeScript |
| Claude Code | 74K | Proprietary | N/A | TypeScript |
| Codex CLI | 62K | Apache 2.0 | Active | Rust |
| Cline | 58K | Apache 2.0 | Active | TypeScript |
| Aider | 41K | Apache 2.0 | Active | Python |
| Goose | 27K | Apache 2.0 | 362 | Rust |
| Continue.dev | 26K | Apache 2.0 | Active | TypeScript |
| Roo Code | 22K | Apache 2.0 | 300 | TypeScript |
| Cursor | N/A | Proprietary | N/A | TypeScript |
| Windsurf | N/A | Proprietary | N/A | TypeScript |
| Amp | N/A | Proprietary | N/A | TypeScript |

### Architecture Patterns

| Project | Pattern | Sub-agents | Cloud Exec |
|---------|---------|------------|------------|
| Claude Code | ReAct + Sub-agent delegation | Yes (Explore/Plan/Task) | No |
| Codex CLI | ReAct + Cloud sandbox | Yes (thread forking) | Yes |
| Gemini CLI | ReAct (CLI/Core split) | No | No |
| Aider | Repo Map + Edit Format | No | No |
| Continue.dev | CI/CD Agent | No | Yes (headless) |
| OpenCode | Client/Server TUI | No | No |
| Cline | Plan-and-Act | No | No |
| Roo Code | Multi-mode Agent | No | Yes (Cloud Agents) |
| Amp | Code Graph + Sub-agents | Yes (Oracle/Librarian) | No |
| Goose | MCP-native Agent | Yes (subagents) | No |
| Cursor | Async Sub-agent Tree | Yes (recursive) | Yes (8 VMs) |
| Windsurf | Cascade Engine | Implicit | No |

### Security Models

| Project | Sandboxing | Permission Model | Enterprise |
|---------|-----------|-----------------|-----------|
| Claude Code | OS-level (Seatbelt/bubblewrap) | 4 modes, deny-rules priority | Yes |
| Codex CLI | Cloud sandbox + local | 3 modes (Auto/Read-only/Full) | Yes |
| Gemini CLI | Docker/Seatbelt/LXC | User approval system | Partial |
| Aider | None | User permissions | No |
| Continue.dev | CI/CD isolation | Config-as-code | Yes |
| OpenCode | None | Privacy-first | No |
| Cline | None (VS Code sandbox) | Human-in-the-loop GUI | Yes |
| Roo Code | None (VS Code sandbox) | Mode-based scoping, SOC 2 | Yes |
| Amp | Sourcegraph ACLs | Granular permissions | Yes |
| Goose | None | Local-first, user perms | No |
| Cursor | Cloud VM isolation | Enterprise controls | Yes |
| Windsurf | None (VS Code sandbox) | SOC 2 Type II | Yes |

### Context Window Management

| Project | Strategy | Innovation Level |
|---------|----------|-----------------|
| Claude Code | Auto-compaction + sub-agent context isolation | High |
| Codex CLI | 400K window + session resume | Medium |
| Gemini CLI | 1M token window | Medium (brute force) |
| Aider | Tree-sitter AST + PageRank repo map | **Highest** |
| Continue.dev | Rule-based context injection | Medium |
| OpenCode | Session persistence + LSP | Medium |
| Cline | AST + regex + selective reading | Medium |
| Roo Code | Partial-file analysis + summarization | Medium |
| Amp | Code graph semantic understanding | **Highest** |
| Goose | Sub-agent workspace isolation | Medium |
| Cursor | Custom embeddings + sub-agent tree | High |
| Windsurf | Cascade memory + repo comprehension | High |

### Plugin/Extension Systems

| Project | MCP | Skills | Custom Agents | Other |
|---------|-----|--------|---------------|-------|
| Claude Code | Yes | Yes (SKILL.md) | Yes (.claude/agents/) | Hooks |
| Codex CLI | Yes | Yes (SKILL.md) | Yes (thread fork) | Cloud marketplace |
| Gemini CLI | Yes | No | No | GEMINI.md context |
| Aider | No | No | No | LLM provider config |
| Continue.dev | No | No | No | Rules-as-code |
| OpenCode | Yes | No | No | ACP |
| Cline | Yes | No | No | VS Code extensions |
| Roo Code | No | Custom Modes | No | Mode Gallery |
| Amp | No | Agent Skills | Yes (Oracle/Librarian) | Sourcegraph graph |
| Goose | Yes (native) | No | Yes (subagents) | MCP-first |
| Cursor | Yes | Yes (SKILL.md) | Yes (Automations) | Triggers/webhooks |
| Windsurf | Yes | No | No | Plugins |

---

## TOP 3 Architectures for Xiaotie v2.0

Based on this analysis, the following three architectural approaches are most relevant for Xiaotie v2.0:

### 1. Claude Code's Sub-Agent + Skills + Hooks Architecture

**Why**: The most mature and well-designed agentic architecture in the CLI space.

**Key patterns to adopt**:
- **Sub-agent delegation**: Explore (fast, uses smaller model for breadth), Plan (architecture decisions), Task (execution). Each sub-agent has isolated context, preventing context pollution.
- **Skills system with progressive disclosure**: Skills defined as markdown files with metadata frontmatter. Agent loads only metadata until a skill is needed, then loads full instructions. This is highly token-efficient.
- **Hooks lifecycle**: Pre/post hooks on tool calls for enforcement (linting, formatting, security checks). Enables team-level policy without modifying agent core.
- **CLAUDE.md hierarchy**: Project-level, user-level, and directory-level instruction files create layered context that's always available.
- **OS-level sandboxing**: Seatbelt (macOS) and bubblewrap (Linux) provide real security without performance overhead (<15ms latency).

**Relevance to Xiaotie**: This is the gold standard for terminal-native agentic architecture. The sub-agent pattern solves context window management elegantly while the skills/hooks system provides extensibility without code changes.

### 2. Aider's Repo Map + Tree-Sitter Context Strategy

**Why**: The most innovative approach to the fundamental problem of giving LLMs codebase understanding within limited context windows.

**Key patterns to adopt**:
- **Tree-sitter AST extraction**: Parse source files into ASTs to extract function/class/variable definitions and references. Supports 100+ languages automatically.
- **NetworkX graph construction**: Build a dependency graph where files are nodes and cross-file references are edges.
- **PageRank-based ranking**: Use PageRank with personalization to identify the most important symbols in the codebase relative to the current task.
- **Dynamic token budgeting**: Automatically adjust repo map size based on conversation state and remaining context budget.
- **Disk-cached tags**: Persistent cache keyed by file path + mtime for fast incremental updates.

**Relevance to Xiaotie**: This solves the hardest problem in coding agents - efficiently representing a large codebase within a limited context window. The PageRank approach is elegant and proven at scale. Xiaotie should implement this as its core context engine, potentially combining it with Claude Code's sub-agent delegation for even better results.

### 3. Cursor's Async Sub-Agent Tree + Automations Architecture

**Why**: The most forward-looking architecture, pointing toward "self-driving codebases."

**Key patterns to adopt**:
- **Async sub-agent trees**: Sub-agents run asynchronously and can spawn their own sub-agents, creating a tree of coordinated work. The parent continues working while children execute.
- **Cloud parallel execution**: Up to 8 isolated VMs running simultaneously, each with full development environment. Produces merge-ready PRs with artifacts.
- **Automations (trigger-based agents)**: Agents triggered by events from Slack, Linear, GitHub, PagerDuty, webhooks. Agents spin up cloud sandboxes and follow instructions with configured MCPs and models.
- **Agent memory**: Agents learn from past runs and improve with repetition.
- **Long-running agent support**: Agents that plan first, then execute over longer horizons for complex tasks.
- **Custom embedding model**: Purpose-built embeddings for codebase recall, not generic embeddings.

**Relevance to Xiaotie**: This represents the future direction. While Xiaotie v2.0 may not implement cloud VMs immediately, the async sub-agent tree pattern and automation triggers are highly valuable. The agent memory concept (learning from past runs) is a significant differentiator.

---

## Recommended Hybrid Architecture for Xiaotie v2.0

Combining the best of all three approaches:

```
┌─────────────────────────────────────────────────────┐
│                    Xiaotie v2.0                      │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Skills/Hooks │  │ XIAOTIE.md   │  │ Automations│ │
│  │ (Claude Code)│  │ (Hierarchy)  │  │ (Cursor)   │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                │                  │        │
│  ┌──────▼──────────────────────────────────▼──────┐ │
│  │           Agent Orchestrator (Core)             │ │
│  │  - ReAct loop with Plan-and-Act modes           │ │
│  │  - Async sub-agent tree (Cursor pattern)        │ │
│  │  - Agent memory (learning from past runs)       │ │
│  └──────┬──────────────────────────────────────────┘ │
│         │                                            │
│  ┌──────▼──────────────────────────────────────────┐ │
│  │         Context Engine                           │ │
│  │  - Tree-sitter repo map (Aider pattern)         │ │
│  │  - PageRank graph ranking                       │ │
│  │  - Dynamic token budgeting                      │ │
│  │  - Auto-compaction (Claude Code pattern)        │ │
│  └──────┬──────────────────────────────────────────┘ │
│         │                                            │
│  ┌──────▼──────────────────────────────────────────┐ │
│  │         Security Layer                           │ │
│  │  - OS-level sandboxing (Seatbelt/bubblewrap)    │ │
│  │  - Mode-based permission scoping (Roo Code)     │ │
│  │  - Network isolation with domain allowlist      │ │
│  └──────┬──────────────────────────────────────────┘ │
│         │                                            │
│  ┌──────▼──────────────────────────────────────────┐ │
│  │         Provider Layer                           │ │
│  │  - Multi-model support (OpenCode pattern)       │ │
│  │  - MCP for tool extensibility                   │ │
│  │  - ACP for IDE integration                      │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  Language: Rust (core) + TypeScript (TUI/UI)         │
│  License: Apache 2.0                                 │
└─────────────────────────────────────────────────────┘
```

### Priority Implementation Order

1. **Phase 1**: Context Engine (tree-sitter repo map + compaction) + Basic ReAct loop
2. **Phase 2**: Skills/Hooks system + OS-level sandboxing + Multi-model provider layer
3. **Phase 3**: Sub-agent architecture + MCP/ACP integration
4. **Phase 4**: Automations + Agent memory + Cloud execution

### Technology Recommendations

| Component | Recommendation | Rationale |
|-----------|---------------|-----------|
| Core language | **Rust** | Performance (Codex, Goose prove this), memory safety, async runtime |
| TUI | **Ratatui** (Rust) | Native Rust TUI, proven in OpenCode's Go equivalent (Bubble Tea) |
| AST parsing | **tree-sitter** | Industry standard, 100+ languages, proven by Aider |
| Graph analysis | **petgraph** (Rust) | Rust equivalent of NetworkX for PageRank |
| Database | **SQLite** | Session persistence, tag caching (proven by Aider, OpenCode) |
| Plugin protocol | **MCP** | Industry standard, maximum ecosystem compatibility |
| IDE protocol | **ACP** | Emerging standard (Cursor, OpenCode, Goose all adopt) |
| Sandboxing | **landlock** (Linux) + **Seatbelt** (macOS) | OS-native, minimal overhead |

---

## Key Takeaways

1. **Context management is the #1 differentiator** - Not model choice, not UI. Aider's tree-sitter + PageRank approach is the most innovative solution.

2. **Sub-agents are the future** - Claude Code, Cursor, and Goose all converge on sub-agent delegation for complex tasks. This pattern solves context pollution and enables parallelism.

3. **MCP is the plugin standard** - Every major tool except Aider supports MCP. Not supporting it is a competitive disadvantage.

4. **Sandboxing is now expected** - Claude Code and Gemini CLI both offer OS-level sandboxing. Users increasingly expect this.

5. **Skills/Modes enable extensibility** - Claude Code's Skills, Roo Code's Custom Modes, and Cursor's Agent Skills all solve the same problem: making the agent adaptable without code changes.

6. **Rust is the performance choice** - Both Codex CLI and Goose chose Rust. For a CLI tool where startup time and responsiveness matter, Rust is increasingly the right choice for the core.

7. **Model-agnostic is table stakes** - OpenCode (112K stars) proves that provider flexibility is what developers want. Being locked to one provider is a significant weakness.

---

*Report generated for Xiaotie v2.0 architecture planning. All data current as of March 6, 2026.*
