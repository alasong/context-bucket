## 可行性结论

* 可行：以流程规范(PDL)为核心、RAG 为上 下文桥梁、证据驱动的门禁，能够在大项目中实现稳定的上下文注入与流程治理。

* 关键：为“生成的代码”建立标准化元数据与证据链，并与检索索引(语义+结构)打通；在 IDE/PR/CI 各环节无缝注入。

## 规模化方案总览

* 元数据层：Generation Manifest + 轻量代码内标记 + 外部证据工件，形成可追溯上下文。

* 索引层：语义向量索引(文档/代码块) + 结构索引(AST/符号/路径/所有权)，支持分片与增量更新。

* 注入层：IDE 插件、PR 机器人、CI 步骤生成上下文包；人机区分的提示模版。

* 编排层：工作流状态机据 PDL 驱动门禁与上下文注入；失败路径提供补救上下文。

## 生成代码的上下文注入机制

* Generation Manifest(仓库内文件)

  * 路径：`/gen-manifests/{module}/{date}/{artifact}.json`

  * 字段：`generatorId`、`model`、`promptHash`、`inputs{docIds,tags}`、`processSpecVersion`、`stage`、`owner`、`createdAt`、`artifactPaths[]`、`checks{lint,test,security}`、`riskNotes[]`。

  * 作用：将“生成来源、约束、所用规范版本、输入证据”绑定到生成物，供检索与审计。

* 代码内元数据通道(轻量且可选)

  * 统一格式：按语言允许的单行首部标记，示例：`// @gen: manifest=... hash=... stage=development`

  * 仅包含稳定短字段与指向 Manifest 的引用，避免冗长注释。

* 外部证据与链接

  * CI 产物：提示模板快照、检索结果摘要、门禁报告、覆盖率与风险清单，统一归档到对象存储并回写链接到 Manifest。

* 知识库摄取流程

  * 事件：生成完成→写 Manifest→触发摄取管道。

  * 摄取：解析 Manifest与代码块；AST 切块+语义嵌入；索引写入(向量+结构)并建立反向链接到 Manifest。

## 检索与注入算法

* 层级检索

  * 规范优先：按 `processSpecVersion` 与 `stage` 先取权威规范条目。

  * 结构约束：按 `module`、`path`、`symbol`、`owner` 过滤结构索引。

  * 语义补全：对相似代码块/示例进行 ANN 检索并重排。

* 混合嵌入

  * 文档嵌入：规范/指南/示例按切块嵌入。

  * 代码嵌入：函数/类/文件级嵌入，结合语言模型向量与符号特征。

* 权威加权与重排

  * 权重顺序：流程规范>项目指南>团队约定>历史示例>外部资料。

  * 重排信号：阶段匹配、语言匹配、所有权、最新度、证据质量。

## 注入集成点

* IDE 插件

  * 打开/选择代码块→读取路径与符号→查询索引→注入上下文卡片：规范清单、示例片段、风险提示、CI 要求。

  * 支持“应用修复”与“生成模板”，同时写入 Manifest 更新。

* PR 机器人

  * 监听差异→按文件/符号生成上下文包→评论区渲染清单与示例→链接到证据与规范条目。

  * 对生成代码检测 Manifest 缺失或不一致并给出修复建议。

* CI 步骤

  * `context-injection`：构建上下文包工件并附加到构建；失败门禁时生成“补救上下文”。

  * `indexing`：增量摄取与索引更新；生成后的代码块与 Manifest 一并入库。

* 发布管理

  * 发布说明自动汇总：变更映射到规范条目与证据；生成物来源可追溯。

## 大项目可扩展性

* 增量索引

  * 基于 Git 差异与路径分片的增量更新；优先索引活跃模块与变更文件。

* 分片与路由

  * 按项目/模块/语言/团队分片；查询路由到相关分片；冷数据降级存储。

* 事件驱动

  * 使用事件总线(如 Redis Streams/Kafka)分发“生成/提交/构建/门禁”事件，串联摄取与注入。

* 缓存策略

  * 上下文包短时缓存(TTL)；PR 会话级缓存；热门规范与示例预热。

* 监控与告警

  * 索引延迟、检索命中率、上下文采纳率、Manifest 缺失率、门禁失败率。

## 技术栈与实现细节

* 存储

  * PostgreSQL + pgvector：向量与元数据；对象存储(S3)保存上下文工件与报告。

  * 索引：结构表(SymbolIndex)：`symbolId, filePath, module, lang, owner, astSig, manifestRef`。

* 摄取管道

  * 解析语言(AST)：Tree-sitter/语言编译器 API；切块策略(函数/类/文件)。

  * 嵌入：文档与代码分别嵌入；写入向量与结构索引。

* 上下文构建伪代码

```pseudo
function buildContext(entity):
  spec = querySpec(entity.stage, entity.specVersion)
  structHits = queryStructure(entity.files, entity.symbols)
  semHits = queryVectors(entity.diffSnippets + entity.topic)
  ranked = rerank(spec.rules + semHits, weights)
  package = compose(spec.checklists, ranked.examples, ciRequirements(spec), links(entity))
  return package
```

* 生成清单示例

```json
{
  "generatorId": "svc.codegen",
  "model": "bge-m3",
  "promptHash": "sha256:...",
  "processSpecVersion": "1.0.0",
  "stage": "development",
  "inputs": {"docIds": ["spec:auth-v1"], "tags": ["backend","auth"]},
  "artifactPaths": ["services/auth/user_service.ts"],
  "checks": {"lint": "pass", "test": "pending"},
  "owner": "team-auth",
  "createdAt": "2025-12-13T08:00:00Z"
}
```

## 风险与缓解

* 元数据遗漏：在生成/提交/CI 三处设置校验；提供自动修复与回填工具。

* 检索偏移：权威加权、版本标签与离线评估；引入重排与示例增强。

* 性能瓶颈：分片索引+增量摄取+缓存预热；大规模时可迁移到 Qdrant/Milvus。

* 合规与隐私：上下文脱敏与访问控制(RBAC)；审计日志与证据留存。

## 下一步实施

* 定稿 PDL 与 Manifest 规范；实现最小化注入(IDE/PR/CI 三点)。

* 完成代码与文档摄取与索引；打通检索与上下文包生成。

* 上线门禁与证据存储；仪表盘度量与告警。

* 迭代优化重排与示例库；扩大到全项目分片与跨团队复用。

