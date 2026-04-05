-- 实验运行记录表
CREATE TABLE IF NOT EXISTS experiment_runs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     VARCHAR(64),
    task_tier   INT CHECK (task_tier BETWEEN 1 AND 5),
    task_domain VARCHAR(64),
    governance_type VARCHAR(32) NOT NULL,
    mechanisms  JSONB NOT NULL DEFAULT '[]',
    -- 主要指标
    quality_score   FLOAT CHECK (quality_score BETWEEN 1 AND 10),
    completion_sec  INT,
    token_cost      INT,
    -- 次要指标
    rejection_count INT DEFAULT 0,
    autonomy_score  FLOAT,
    fault_recovered BOOL DEFAULT FALSE,
    -- 元数据
    agent_model VARCHAR(64),
    run_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    context_snapshot JSONB DEFAULT '{}'  -- 记录关键 context 字段供事后分析
);

CREATE INDEX IF NOT EXISTS idx_runs_governance ON experiment_runs (governance_type);
CREATE INDEX IF NOT EXISTS idx_runs_tier       ON experiment_runs (task_tier);
CREATE INDEX IF NOT EXISTS idx_runs_domain     ON experiment_runs (task_domain);

-- 复合指标视图：EI = quality_score / (completion_sec * sqrt(token_cost))
CREATE OR REPLACE VIEW experiment_efficiency AS
SELECT
    id,
    governance_type,
    task_tier,
    task_domain,
    quality_score,
    completion_sec,
    token_cost,
    CASE
        WHEN completion_sec > 0 AND token_cost > 0
        THEN quality_score / (completion_sec * sqrt(token_cost::float))
        ELSE NULL
    END AS efficiency_index,
    rejection_count,
    autonomy_score,
    fault_recovered,
    run_at
FROM experiment_runs;
