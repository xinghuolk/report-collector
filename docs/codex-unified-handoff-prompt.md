# Codex Unified Handoff Prompt

把下面整段直接发给新的 Codex，即可让它在不依赖某一轮具体进度的前提下接手这个项目。

---

你现在接手的是 `report-collector` 仓库里的持续演进项目。不要假设当前停留在某个固定 task、某个固定 spec，或者某个固定阶段。你的职责不是“继续上一条显式待办”，而是先识别当前真实状态，再从最新的 spec / plan / 代码进度继续推进。

## 工作区

- Repo: `F:\source\git\report-collector`
- 常用分支: `feature/financial-report-analysis`
- Shell: `powershell`
- 时区: `Asia/Shanghai`

## 你应该如何开始

接手后先做“状态发现”，不要直接编码。

按这个顺序执行：

1. 检查当前 git 状态
   - `git status --short --branch`
   - `git log --oneline --decorate -15`
   - 如有需要，再看 `git diff --stat`

2. 识别当前活跃工作区
   - 优先看 `financial-report-analysis/`
   - 除非最新 spec / plan 明确要求，否则不要主动把新逻辑耦合进 `report/`

3. 识别当前最新文档
   - 先查看 `docs/superpowers/specs/active/`
   - 再查看 `docs/superpowers/plans/active/`
   - 如需仍有效的路线/架构背景，再进入 `docs/superpowers/specs/reference/` 或 `docs/superpowers/plans/reference/`
   - 如需历史执行细节，再进入 `docs/superpowers/specs/archived/` 或 `docs/superpowers/plans/archived/`
   - 以“最新日期、且与当前分支改动最相关”的 spec / plan 为主
   - 不要默认只看一个文档；如果有“总纲 + 当前阶段 plan”，要一起读

4. 校对代码与文档是否一致
   - 当前代码到底进行到哪个 task
   - 有没有已实现但未 review 闭环的提交
   - 有没有已写 plan 但尚未落代码的阶段

5. 再决定下一步
   - 如果当前 task 正在进行中，先 review / 收口当前 task
   - 如果当前阶段已经完成，再进入下一阶段
   - 如果发现 spec / plan 已经过时，先提出并修正文档，再编码

## 长期目标

这个仓库里与当前工作最相关的是 `financial-report-analysis/`。它的长期方向是：

- 建立独立的财报分析能力
- 从 PDF / 表格 / 附注中抽取稳定、可验证、可消费的结构化事实
- 逐步形成：
  - structure recovery
  - semantic normalization
  - metric mapping / registry
  - candidate facts
  - canonical facts
  - validation / derivation

目标不是为了单个样本打补丁，也不是为了过测试加公司特例，而是建立能持续扩展到更多财报家族的统一框架。

## 关键边界

### 1. 不要只盯单个 plan / spec

每次接手都要重新确认：

- 当前最新 spec 是哪份
- 当前最新 implementation plan 是哪份
- 当前代码是否已经超前于文档，或落后于文档

不要机械地继续旧任务编号。

### 2. 优先做结构化主路径

默认优先顺序应是：

- deterministic structure / table / note path
- deterministic semantic normalization
- gated fallback

不要一上来就把问题推给大模型。

### 3. 大模型只能做受限兜底

如果当前阶段涉及 Ollama / semantic fallback，默认边界是：

- 可以做语义判别、行标签归一化、table kind / disclosure locator
- 必须有 gated trigger
- 必须有 budget
- 必须有 provenance

不要让模型：

- 直接自由抽数
- 自由做单位传播
- 直接产 canonical facts

### 4. 不做 issuer-specific 特例分支

如果某份真实财报暴露了问题，优先抽象成：

- 一类表结构问题
- 一类 row label / column semantic 问题
- 一类 note/disclosure 补充路径问题

不要给单个公司写硬编码分支，除非 spec 明确允许。

### 5. 缺失语义必须清楚

如果某阶段涉及“存在 / 不存在 / 未稳定露出”的区别，不要只靠 candidate omission 糊过去。要看当前 contract 是否已经定义了类似：

- `absent`
- `not_surfaced`
- `unknown`

并保持代码、测试、文档一致。

## 文档读取顺序

每次接手建议按这个顺序读：

1. [AGENTS.md](F:/source/git/report-collector/AGENTS.md)
2. 本文件 [codex-unified-handoff-prompt.md](F:/source/git/report-collector/docs/codex-unified-handoff-prompt.md)
3. `docs/superpowers/specs/active/` 中最新且与当前代码最相关的 spec
4. `docs/superpowers/plans/active/` 中与该 spec 配套的最新 plan
5. 如存在“总纲 / master plan”，再补读总纲
6. 最后回到 `git log` 和代码本身确认进度

当前文档生命周期约定：

- active 目录只保留仍指导下一步工作的 spec / plan。
- reference 目录保存仍有路线、架构、字段或方法约束参考价值，但不应直接执行的文档。
- archived 目录保存已完成、已被取代或不再承担当前决策职责的历史文档。
- 如果 active plan 为空，不要从 archived plan 里机械恢复任务；先依据 active roadmap 与代码实际状态判断是否需要写新的 spec / plan。

## 推荐执行方式

如果当前工作仍然是多 task 的连续实现，优先延续已经在本项目里反复使用过的工作方式：

- Subagent-Driven Development
- 一次只推进一个 task
- 每个 task 都尽量走完整闭环：
  - implement
  - focused verification
  - spec compliance review
  - code quality review
  - 必要时回修

如果当前只是 review / 收口 / 回归验证，也要先确认是不是应该先补文档或先修 contract。

## 默认验证策略

不要把“全量真实 PDF + 全量 Ollama”当成每次收口默认动作。

优先顺序：

1. unit tests
2. mocked / narrow integration tests
3. focused real-PDF tests
4. live Ollama smoke
5. 必要时才跑更大的 real-PDF matrix

注意：

- real-PDF 和 live Ollama 验证默认串行，不要盲目并发
- 如果回归变慢，先看 fallback gating / 调用次数，而不是先加 timeout
- 如果只是局部功能变动，只跑最小相关真实样本

## 当你不确定下一步时

用下面这套判断：

1. 当前最新 spec / plan 是否已经清楚定义了下一步
2. 当前代码是否已经完成了文档里的这一步
3. 如果代码已完成但未 review，先 review
4. 如果 review 发现文档和实现不一致，先修文档或修实现
5. 只有在当前阶段闭环后，才进入下一阶段

## 常见错误，避免重复

- 只根据上一条对话继续，而不重新核对当前 git / docs 状态
- 把旧 plan 当成唯一真相
- 为了过样本测试写公司特例
- 用 Ollama 替代结构化主路径
- 直接跑昂贵的全量真实 PDF 矩阵
- 没有区分“已实现”“已验证”“已 review”“已收口”

## 对外汇报时的简写方法

如果你要汇报当前项目状态，请用这种结构，而不是直接报 task 编号：

- 当前活跃 spec / plan 是什么
- 当前代码实际完成到哪里
- 当前阶段还有哪些 review / verification 缺口
- 下一步最合理的收口动作是什么

## 你接手后的第一句话应该落实为行动

从这里开始：

> 先用 `git status --short --branch`、`git log --oneline --decorate -15`、以及最新 spec / plan 识别当前真实进度，再决定是继续当前 task、先做 review，还是先修正文档。

---

如果你需要一句更短的工作原则，可以概括为：

> 不依赖上一轮记忆，不写死当前阶段；每次接手都先重新发现真实状态，再沿着最新 spec / plan 和代码实际进度继续推进。
