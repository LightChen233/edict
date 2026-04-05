---
name: Governance as Algorithm — Nature级实验框架实现
overview: 在9种历史治理模型的可插拔架构基础上，构建完整的对比实验框架，支持4050次跨模型运行、方差分析、治理选择算法，目标发表Nature/Science级论文。
todos:
  - id: governance-base
    content: "创建 governance 包: base.py (GovernanceModel 抽象基类 + GovernanceType 枚举) + registry.py"
    status: done
  - id: governance-models
    content: "实现9种治理模型: san_sheng / cheng_xiang / nei_ge / yi_hui / jun_ji_chu / feng_jian / wei_yuan_hui / zong_tong / lian_bang"
    status: done
  - id: governance-models-extended
    content: "实现6种扩展历史模型: athenian / roman / venetian / kurultai / ritsuryo / shura"
    status: done
  - id: cross-cutting
    content: "实现3种跨制度机制: ke_ju (科举竞选) + yu_shi_tai (御史监察) + gong_guo_bu (功过簿绩效)"
    status: done
  - id: task-model-migration
    content: "Task模型新增 governance_type/governance_config/mechanisms 字段，state从Enum改为VARCHAR，Alembic迁移"
    status: done
  - id: service-refactor
    content: "TaskService + OrchestratorWorker 动态加载治理模型，替代硬编码 STATE_TRANSITIONS / STATE_AGENT_MAP"
    status: done
  - id: agent-souls
    content: "补充6个新Agent SOUL.md: 丞相/首辅/议长/军机大臣/天子/御史"
    status: done
  - id: experiment-infra
    content: "实验基础设施: task_generator.py (450任务×5层级) + runner.py (4050次运行) + evaluator.py + analysis.py"
    status: done
  - id: api-endpoints
    content: "governance API端点: GET /api/governance/ + GET /api/governance/{type} + TaskCreate支持governance_type"
    status: done
  - id: frontend-governance
    content: "前端GovernancePanel: 制度选择器 + 动态状态列 + 制度说明页"
    status: done
isProject: true
---

# Governance as Algorithm — 实现计划

## 核心论文假设（需实验验证）

1. **H1 治理主导性**: 治理模型解释 >40% 的质量方差，超过模型能力(~25%)和prompt工程(~15%)
2. **H2 速度-质量-自治三难**: 无单一模型在所有任务类型上同时最优
3. **H3 任务-治理适配**: 存在显著的任务层级×治理模型交互效应 (p<0.001)
4. **H4 机制正交性**: 三种跨制度机制叠加效果可加，无显著交互项
5. **H5 自适应改进**: 功过簿追踪下系统效率随任务数单调提升
6. **H6 选择可学习**: 基于任务元数据的分类器可达到 oracle 效率的 >85%

---

## Phase 1 — governance 包（硬依赖，优先实现）

### 1.1 `edict/backend/app/governance/base.py`

```python
class GovernanceType(str, Enum):
    SAN_SHENG    = "san_sheng"
    CHENG_XIANG  = "cheng_xiang"
    NEI_GE       = "nei_ge"
    YI_HUI       = "yi_hui"
    JUN_JI_CHU   = "jun_ji_chu"
    FENG_JIAN    = "feng_jian"
    WEI_YUAN_HUI = "wei_yuan_hui"
    ZONG_TONG    = "zong_tong"
    LIAN_BANG    = "lian_bang"

class GovernanceModel(ABC):
    type: GovernanceType
    name: str
    description: str
    dynasty: str          # 历史朝代/来源
    topology: str         # hub-and-spoke / pipeline / consensus / ...

    @abstractmethod
    def get_states(self) -> list[str]: ...
    @abstractmethod
    def get_initial_state(self) -> str: ...
    @abstractmethod
    def get_terminal_states(self) -> set[str]: ...
    @abstractmethod
    def get_transitions(self) -> dict[str, set[str]]: ...
    @abstractmethod
    def get_state_agent_map(self) -> dict[str, str]: ...
    @abstractmethod
    def get_permission_matrix(self) -> dict[str, set[str]]: ...

    def validate_transition(self, from_state: str, to_state: str) -> bool:
        return to_state in self.get_transitions().get(from_state, set())

    def get_next_agent(self, state: str, context: dict) -> str | None:
        return self.get_state_agent_map().get(state)
```

### 1.2 `edict/backend/app/governance/registry.py`

- 单例注册表，启动时自动注册所有9种模型
- `get_model(governance_type) -> GovernanceModel`
- `list_models() -> list[GovernanceModelInfo]`

### 1.3 九种治理模型状态机规格

| 模型 | 状态数 | 关键机制 | 预期适用层级 |
|------|--------|---------|------------|
| san_sheng | 8 | 门下省封驳（最多3轮） | T3–T5 |
| cheng_xiang | 6 | 丞相单点决策 | T1–T2 |
| nei_ge | 8 | 票拟+批红 | T4–T5 |
| yi_hui | 9 | 辩论+投票（多数阈值） | T4 |
| jun_ji_chu | 5 | 无审核层，直接执行 | T1紧急 |
| feng_jian | 4 | 诸侯自治，松耦合 | T3并行 |
| wei_yuan_hui | 7 | 轮值主席，纯共识 | T4创意 |
| zong_tong | 6 | 顾问咨询+总统拍板 | T2–T3 |
| lian_bang | 7 | 联邦协调+州自治 | T3–T4跨域 |

---

## 拓展实验
一、状态机形式化升级                          
   
  把每个模型的状态机从"状态列表+转移字典"升级为 
  带守卫条件的扩展状态机（Extended FSM）：    
                                                
  Transition = (from_state, to_state, guard,    
  action)                                       
  guard: Context → bool   # 转移条件
  action: Context → void  # 转移时副作用

  每个模型需要补充的具体内容

  三省六部（san_sheng）
  - 封驳计数器：context.rejection_count < 3
  才能再次封驳，第3次强制放行
  - 门下省转移守卫：质量评分 < 7 → 封驳；≥ 7 →
  准奏
  - 并发执行：尚书省派发后，六部并行执行（fork/j
  oin模式）

  内阁制（nei_ge）
  - 票拟子状态机：[首辅提议 → 阁臣1意见 →
  阁臣2意见 → 阁臣3意见 → 汇总] 并发收集
  - 批红守卫：司礼监（用户）可批红/留中/驳回，留
  中超时自动批红
  -
  阁臣数量可配置：governance_config.cabinet_size
   ∈ {2,3,4}

  议会制（yi_hui）
  - 投票守卫：yes_votes / total_votes >
  threshold，threshold
  可配置（简单多数/2/3/绝对多数）
  -
  修正案循环：否决后可提修正案重新一读，最多3轮
  -
  委员会审查并发：多个专项委员会同时审查不同方面

  军机处（jun_ji_chu）
  - 紧急度守卫：task.priority == "urgent"
  才能进入此模型
  - 超时强制推进：每个状态最长停留时间，超时自动
  转下一状态
  - 无封驳路径：一旦决策不可回退

  分封制（feng_jian）
  - 并发诸侯：fork(lord_1, lord_2, ..., lord_n)
  同时自治
  - 朝贡汇报：join
  等待所有诸侯完成，超时的诸侯标记为"失联"
  - 天子干预守卫：诸侯失联超过阈值 →
  天子直接接管

  委员会制（wei_yuan_hui）
  - 共识守卫：dissent_count ==
  0，有任何反对则继续讨论
  - 死锁检测：讨论轮次 > max_rounds →
  强制投票打破僵局
  - 轮值主席：每轮讨论主席轮换，防止单点主导

  联邦制（lian_bang）
  - 跨州协调守卫：检测任务是否涉及多个域，是则触
  发联邦协调状态
  - 州自治并发：各州独立执行，联邦只协调边界冲突
  - 补贴机制：联邦可向资源不足的州注入额外token
  预算

  丞相制（cheng_xiang）
  - 皇帝否决守卫：丞相决策后，用户可在N秒内否决
  ，超时自动确认
  - 属吏选择：丞相根据任务类型选择派发给哪个属吏
  （动态路由）

  总统制（zong_tong）
  - 顾问团并发：多个顾问同时提交建议，总统收到全
  部后拍板
  - 否决权：总统可否决内阁执行结果，要求重做

  ---
  二、历史模型扩充：新增6种

  扩充原则

  不是为了数量，每个新模型必须在状态机拓扑上与现
  有9种有本质区别：

  ┌──────────┬─────────────┬────────────────┐
  │  新模型  │ 核心拓扑创  │ 现有模型的区别 │
  │          │     新      │                │
  ├──────────┼─────────────┼────────────────┤
  │ 雅典民主 │ 抽签选官 +  │ 议会制是代议制 │
  │ （Atheni │ 公民大会    │ ，雅典是直接民 │
  │ an）     │             │ 主+随机选拔    │
  ├──────────┼─────────────┼────────────────┤
  │ 罗马元老 │ 咨询性质，  │ 总统制是单一强 │
  │ 院（Roma │ 执政官双头  │ 执行者，罗马是 │
  │ n）      │ 制+互相否决 │ 双执政官互相制 │
  │          │             │ 衡             │
  ├──────────┼─────────────┼────────────────┤
  │ 威尼斯共 │ 多层嵌套委  │ 委员会制是扁平 │
  │ 和国（Ve │ 员会，防止  │ ，威尼斯是刻意 │
  │ netian） │ 任何人集权  │ 复杂化以防独裁 │
  ├──────────┼─────────────┼────────────────┤
  │ 蒙古忽里 │ 军事首领大  │ 委员会制共识是 │
  │ 勒台（Ku │ 会，强制共  │ 协商，忽里勒台 │
  │ rultai） │ 识+武力背书 │ 共识是威慑     │
  ├──────────┼─────────────┼────────────────┤
  │ 日本令制 │ 三省六部的  │ 对照组：同源制 │
  │ （Ritsur │ 变形，太政  │ 度的不同演化路 │
  │ yo）     │ 官凌驾三省  │ 径             │
  ├──────────┼─────────────┼────────────────┤
  │ 伊斯兰舒 │ 协商义务但  │ 内阁制有否决权 │
  │ 拉（Shur │ 领袖有最终  │ ，舒拉是建议性 │
  │ a）      │ 权，宗教法  │ 协商+法律硬约  │
  │          │ 约束        │ 束             │
  └──────────┴─────────────┴────────────────┘

  各新模型状态机草案

  雅典民主（athenian）
  Pending → Sortition（抽签选执行者）→
  AgonProposal（公民大会提案）
  → Debate（辩论，任何公民可发言）→
  Ostracism?（陶片放逐异见者，可选）
  → DirectVote（直接投票，无代议）→ Executing →
  Euthyna（执行后审计）→ Done
  核心特征：执行者随机选拔（非能力选拔），决策权
  在全体而非精英

  罗马元老院（roman）
  Pending → SenateConsultation（元老院咨询）→
  ConsulDecision（执政官A决策）
  → ConsulVeto?（执政官B否决权，互相制衡）→
  [否决→重议 / 通过→Executing]
  → Executing → Triumph/Censure（凯旋/弹劾）→
  Done
  核心特征：双执政官互相否决，任期制（1年），独
  裁官紧急机制

  威尼斯共和国（venetian）
  Pending → GrandCouncil（大议会提名）→
  Balloting（多轮抽签+投票混合选举）
  → SmallCouncil（小议会审查）→
  TenCouncil（十人委员会安全审查）
  → DogeProposes（总督提案，但无实权）→
  Executing → Audit → Done
  核心特征：刻意设计的复杂性防止权力集中，总督是
  吉祥物

  蒙古忽里勒台（kurultai）
  Pending → Summons（召集各部落首领）→
  Kurultai（大会，强制出席）
  → Deliberation（协商，军事实力背书）→
  Consensus（强制共识，异见者承担后果）
  → Decree → MilitaryExecution（军事化执行）→
  TributeReport → Done
  核心特征：共识是威慑性的，不是协商性的；执行是
  军事化的

  日本令制（ritsuryo）
  Pending → Dajokan（太政官接收，凌驾三省）→
  Chunagon（中纳言规划，对应中书）
  → Sangi（参议审议，对应门下但权力更弱）→
  Benkan（弁官局派发，对应尚书）
  → Executing → Zuryo（国司执行，地方官）→ Done
  核心特征：与三省六部同源但太政官打破了三省制衡
  ，作为对照组验证制度变形的影响

  伊斯兰舒拉（shura）
  Pending → ShuraConvened（召集协商会议）→
  Consultation（各方建议，义务性）
  → FiqhCheck（伊斯兰法合规检查，硬约束）→ Leade
  rDecision（领袖最终决定，参考但不受制于舒拉）
  → Executing → Hisba（市场/道德监察）→ Done
  核心特征：宗教法是硬约束（不可绕过），协商是义
  务但非决策权

  ---
  三、更新后的完整模型矩阵（15种）

  #: 1
  模型: 三省六部
  来源: 唐
  拓扑类型: 线性流水线
  并发: fork(六部)
  回退: 封驳≤3
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 2
  模型: 丞相制
  来源: 秦汉
  拓扑类型: Hub-spoke
  并发: 否
  回退: 否
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 3
  模型: 内阁制
  来源: 明
  拓扑类型: 并发汇聚
  并发: fork(阁臣)
  回退: 驳回
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 4
  模型: 议会制
  来源: 现代
  拓扑类型: 辩论投票
  并发: fork(委员会)
  回退: 修正案≤3
  随机性: 否
  硬约束: 多数阈值
  ────────────────────────────────────────
  #: 5
  模型: 军机处
  来源: 清
  拓扑类型: 极简直路
  并发: 否
  回退: 否
  随机性: 否
  硬约束: 紧急度
  ────────────────────────────────────────
  #: 6
  模型: 分封制
  来源: 周
  拓扑类型: 并发自治
  并发: fork(诸侯)
  回退: 否
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 7
  模型: 委员会制
  来源: 现代
  拓扑类型: 扁平共识
  并发: 否
  回退: 死锁重议
  随机性: 否
  硬约束: 全员共识
  ────────────────────────────────────────
  #: 8
  模型: 总统制
  来源: 现代
  拓扑类型: 强执行+顾问
  并发: fork(顾问)
  回退: 否决重做
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 9
  模型: 联邦制
  来源: 现代
  拓扑类型: 多级并发
  并发: fork(州)
  回退: 否
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 10
  模型: 雅典民主
  来源: 古希腊
  拓扑类型: 直接民主
  并发: 否
  回退: 否
  随机性: 抽签
  硬约束: 否
  ────────────────────────────────────────
  #: 11
  模型: 罗马元老院
  来源: 古罗马
  拓扑类型: 双头制衡
  并发: 否
  回退: 互相否决
  随机性: 否
  硬约束: 任期制
  ────────────────────────────────────────
  #: 12
  模型: 威尼斯共和国
  来源: 中世纪
  拓扑类型: 嵌套委员会
  并发: fork(多层)
  回退: 多层审查
  随机性: 抽签+投票
  硬约束: 防集权
  ────────────────────────────────────────
  #: 13
  模型: 蒙古忽里勒台
  来源: 蒙古
  拓扑类型: 威慑共识
  并发: 否
  回退: 否
  随机性: 否
  硬约束: 强制出席
  ────────────────────────────────────────
  #: 14
  模型: 日本令制
  来源: 奈良
  拓扑类型: 变形三省
  并发: fork(国司)
  回退: 弱
  随机性: 否
  硬约束: 否
  ────────────────────────────────────────
  #: 15
  模型: 伊斯兰舒拉
  来源: 伊斯兰
  拓扑类型: 咨询+法约束
  并发: 否
  回退: 否
  随机性: 否
  硬约束: 宗教法

  ---

## Phase 2 — 数据库迁移

文件: `edict/migration/versions/002_add_governance.py`

```sql
ALTER TABLE tasks
  ADD COLUMN governance_type VARCHAR(32) NOT NULL DEFAULT 'san_sheng',
  ADD COLUMN governance_config JSONB NOT NULL DEFAULT '{}',
  ADD COLUMN mechanisms JSONB NOT NULL DEFAULT '[]';

-- state 从 Enum 改为 VARCHAR 支持动态状态名
ALTER TABLE tasks ALTER COLUMN state TYPE VARCHAR(64);
```

---

## Phase 3 — 服务层重构

### TaskService 改动
- `create_task(governance_type="san_sheng", mechanisms=[])`
- `transition_state()` → 从 registry 加载模型，调用 `model.validate_transition()`
- `get_governance_info(task_id)` → 返回当前任务的治理模型详情

### OrchestratorWorker 改动
- `_on_task_status()` → `registry.get_model(task.governance_type).get_next_agent(new_state, context)`
- 机制拦截点：dispatch 前检查 ke_ju，全程订阅 yu_shi_tai
- 向后兼容：`governance_type=None` 的旧任务默认走 san_sheng

---

## Phase 4 — 实验基础设施

### 目录结构
```
experiments/
  task_generator.py     # 生成450个标准化任务（5层级×90个）
  runner.py             # 实验运行器（4050次 = 450任务×9模型）
  evaluator.py          # 自动评分 + 人工评分接口
  analysis.py           # ANOVA + 交互效应 + 分类器训练
  schema.sql            # experiment_runs 表定义
  results/              # 实验结果存储
```

### `experiment_runs` 表
```sql
CREATE TABLE experiment_runs (
  id UUID PRIMARY KEY,
  task_id VARCHAR(64),
  task_tier INT,           -- T1-T5
  task_domain VARCHAR(64),
  governance_type VARCHAR(32),
  mechanisms JSONB,
  quality_score FLOAT,     -- 1-10，人工或自动评分
  completion_sec INT,
  token_cost INT,
  rejection_count INT,
  autonomy_score FLOAT,
  fault_recovered BOOL,
  agent_model VARCHAR(64),
  run_at TIMESTAMP
);
```

### 任务层级定义（T1–T5）

| 层级 | 名称 | 可分解 | 可验证 | 有争议 | 示例 |
|------|------|--------|--------|--------|------|
| T1 | Atomic | 否 | 是 | 否 | 修复语法错误 |
| T2 | Sequential | 是 | 是 | 否 | 写并测试REST接口 |
| T3 | Parallel | 是 | 部分 | 否 | 跨3数据源生成周报 |
| T4 | Deliberative | 是 | 部分 | 是 | PostgreSQL vs MongoDB选型 |
| T5 | Complex | 是 | 否 | 是 | 设计微服务架构 |

### 评估指标

**主要指标:**
- Quality Score (Q): 1–10，三位评审，Cohen's κ > 0.75
- Completion Time (T): 秒
- Token Cost (C): 总token数

**复合指标:**
- Efficiency Index (EI) = Q / (T × C^0.5)

**次要指标:**
- Rejection Rate: 触发至少一次封驳的任务比例
- Autonomy Score: 无人工干预的决策比例
- Fault Recovery Rate: 卡住任务的自动恢复比例

---

## Phase 5 — 前端 GovernancePanel

文件: `edict/frontend/src/components/GovernancePanel.tsx`

- 治理制度选择器（任务创建时下拉选择）
- 看板动态状态列（根据 governance_type 渲染对应状态）
- 制度说明页（状态机流程图 + 适用场景 + 历史背景）
- 机制叠加开关（科举/御史台/功过簿 checkbox）

---

## Phase 6 — Agent SOUL 文件

| 文件 | 角色 | 对应制度 |
|------|------|---------|
| `agents/chengxiang/SOUL.md` | 丞相 | 丞相制 |
| `agents/shoufu/SOUL.md` | 内阁首辅 | 内阁制 |
| `agents/yizhang/SOUL.md` | 议长 | 议会制 |
| `agents/junji_dachen/SOUL.md` | 军机大臣 | 军机处制 |
| `agents/tianzi/SOUL.md` | 天子/联邦协调者 | 分封制/联邦制 |
| `agents/yushi/SOUL.md` | 御史 | 御史台机制 |

---

## 执行顺序与依赖

```
Phase 1 (governance包)
    ↓
Phase 2 (DB迁移)
    ↓
Phase 3 (服务层)
    ↓
Phase 6 (SOUL文件)    Phase 4 (实验框架)    Phase 5 (前端)
    ↓                      ↓                    ↓
                    实验运行 (4050次)
                           ↓
                    统计分析 + 论文
```

Phase 1–3 是硬依赖，必须顺序完成。
Phase 4/5/6 可并行，Phase 4 是论文核心。

---

## 关键风险

1. **state字段迁移**: 从Enum→VARCHAR需要处理现有数据，迁移脚本需谨慎
2. **向后兼容**: 旧任务无 governance_type 字段，需默认 san_sheng
3. **实验规模**: 4050次LLM调用成本约 $200–500，需预算确认
4. **人工评分瓶颈**: T4/T5任务需人工评分，450×2层级=180个任务需人工处理
5. **委员会制死锁**: 纯共识模型可能产生双峰质量分布，需设置超时机制
