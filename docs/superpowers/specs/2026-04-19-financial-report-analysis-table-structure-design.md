# 财报分析表格结构抽取与对齐设计

## 1. 目的

本文档定义 Phase-2 的第一个子阶段：为 `financial-report-analysis` 建立稳定的表格结构抽取与对齐能力。

这一阶段的重点不是多抽字段，而是为后续利润表深度抽取和三大报表核心字段扩展提供稳定底座。

## 2. 目标

构建一个可被独立 analysis service 复用的 table-structure layer，使系统能够：

- 识别财务主表与摘要表
- 提取表头中的期间、比较列、单位、币种等语义
- 处理跨页表和续表
- 建立稳定的行列绑定
- 产出可供 candidate fact builder 消费的结构化 table model

## 3. 范围

### 3.1 市场范围

只覆盖：

- A 股中文财报
- 港股英文财报

### 3.2 表格范围

#### P0

- 利润表
- 资产负债表
- 现金流量表

#### P1

- 主要财务数据表

P1 纳入结构识别与列语义解析，但不要求与 P0 同等级收口。

## 4. 非目标

本阶段不负责：

- 一次性完成所有核心字段抽取
- 完整 metric taxonomy 扩展
- 大模型主导的 PDF 数字抽取
- 替换 `report/` 旧 extractor 的全部能力
- 修改 `report/` 的旧业务主链路

## 5. 问题定义

当前独立 ingestion path 的主要问题，不在于“缺少字段列表”，而在于：

- period 判断经常依赖全文级脆弱匹配
- unit / currency 会被无关上下文污染
- 表头列语义没有稳定建模
- 续表与跨页主表没有独立抽象
- 行标签和数值列绑定过于临时

如果这些问题不先解决，后续字段扩张会持续放大误抽。

## 6. 设计原则

### 6.1 局部上下文优先

单位、币种、期间、比较列语义优先来自：

- 表标题
- 表头
- 当前表附近上下文
- 当前行附近上下文

而不是全文扫描。

### 6.2 结构先于字段

先确定：

- 这是不是目标表
- 哪些列对应哪些期间
- 哪些列是当前期 / 上年同期 / 年初至报告期末
- 当前表的单位和币种是什么

再进入字段抽取。

### 6.3 主表与摘要表分层

三大主表是主账本来源。摘要表属于高价值补充信息，但不能反向主导结构建模。

### 6.4 可追溯

table model 中间结果必须保留足够证据，便于后续：

- 构建 candidate facts
- 做冲突裁决
- 回放与 debug

## 7. 目标中间对象

建议在这一阶段引入明确的结构化中间对象。

### 7.1 ParsedTable

建议字段：

- `table_id`
- `document_id`
- `page_range`
- `table_kind`
- `title_text`
- `header_rows`
- `body_rows`
- `table_unit`
- `table_currency`
- `period_columns`
- `comparison_columns`
- `source_blocks`

### 7.2 ParsedColumn

建议字段：

- `column_id`
- `column_index`
- `header_text`
- `period_id`
- `period_scope`
- `comparison_axis`
- `is_current`
- `is_comparison`

### 7.3 ParsedRow

建议字段：

- `row_id`
- `row_index`
- `label_raw`
- `normalized_label_hint`
- `value_cells`
- `indent_level`
- `is_subtotal`
- `is_total`

### 7.4 ParsedCell

建议字段：

- `row_index`
- `column_index`
- `text_raw`
- `numeric_value`
- `bbox`
- `page_index`

## 8. 核心能力拆分

### 8.1 主表识别

能力目标：

- 根据标题、表头、邻近文本识别表格类型
- 区分三大主表与“主要财务数据表”

最低输出：

- `table_kind in {income_statement, balance_sheet, cash_flow_statement, key_metrics, unknown}`

### 8.2 表头语义解析

能力目标：

- 识别期间列
- 识别比较列
- 识别累计值 / 单季度 / 时点值
- 识别单位与币种

关键难点：

- 中英双语表头
- 多层表头
- “本报告期 / 上年同期 / 年初至报告期末 / 上年同期”组合列

### 8.3 跨页续表拼接

能力目标：

- 判断两页表格是否属于同一张主表
- 合并重复表头
- 保留连续的 row/column 语义

### 8.4 行标签与数值绑定

能力目标：

- 稳定识别 label cell
- 绑定对应期间列数值
- 处理缩进、分组、合计、小计

### 8.5 局部单位与币种优先级

建议优先级：

1. 当前表表头明确声明
2. 当前表标题或表附近说明
3. 当前行附近说明
4. 文档级 fallback

禁止直接把全文首次命中的币种 / 单位当作主判断依据。

## 9. 与 candidate fact builder 的边界

这一阶段只负责产出结构化表格中间结果，不要求完整实现字段级 candidate fact 覆盖。

对后续 fact builder 的最小交付应该是：

- 可识别表类型
- 可识别期间列
- 可识别单位 / 币种
- 可稳定给出行标签和对应 value cell

这样后续利润表深度抽取只需要在 table model 上做字段映射，而不是重新处理 PDF 结构问题。

## 10. 测试策略

### 10.1 单元测试

建议覆盖：

- 中英文表标题识别
- 表头期间解析
- 单位 / 币种局部优先级
- 续表拼接逻辑
- 行列绑定逻辑

### 10.2 真实样本回归

至少覆盖：

- A 股年报
- A 股季报
- 港股英文季报

最低断言：

- 能识别主表
- 能识别 period columns
- 能识别单位 / 币种
- 能稳定定位 revenue / total assets / operating cash flow 所在行列

### 10.3 验收标准

此阶段完成时，至少应满足：

- 真实样本上的 P0 主表可稳定识别
- 主表列期间不再依赖脆弱全文级规则
- unit / currency 的误判明显下降
- 后续利润表子 spec 不需要再重新定义主表结构层

## 11. 风险与缓解

### 11.1 风险：摘要表复杂度拖累设计

缓解：

- 将“主要财务数据表”降为 P1
- 允许其结构支持先于事实主链路接入

### 11.2 风险：过早扩字段导致返工

缓解：

- 本阶段严格聚焦 table model
- 不把字段覆盖率作为唯一目标

### 11.3 风险：继续滑回全文 regex 方案

缓解：

- 所有新增判断必须优先依赖表级和局部上下文
- 真实回归测试必须覆盖误判样本

## 12. 结论

这一子阶段的核心不是“抽更多”，而是“抽得可扩展”。

只有把三大主表和摘要表的结构层做稳，后续利润表深度抽取和三大报表核心字段扩展才能在不反复返工的前提下推进。
