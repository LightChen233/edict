/**
 * GovernancePanel — 治理制度选择器 + 状态机说明
 */

import { useEffect, useState } from 'react';
import { api, type GovernanceModelInfo } from '../api';

const TOPOLOGY_LABEL: Record<string, string> = {
  'hub-and-spoke': '中枢辐射',
  'pipeline':      '流水线',
  'consensus':     '共识制',
  'parallel':      '并发自治',
  'deliberative':  '辩论投票',
  'nested':        '嵌套委员会',
};

const DYNASTY_COLOR: Record<string, string> = {
  '唐': '#e8a040', '秦汉': '#ff9a6a', '明': '#a07aff', '清': '#ff5270',
  '周': '#6aef9a', '现代': '#6a9eff', '古希腊': '#f5c842', '古罗马': '#cc8844',
  '中世纪': '#9b59b6', '蒙古': '#44aaff', '奈良': '#ff6b9d', '伊斯兰': '#2ecc8a',
};

export default function GovernancePanel() {
  const [models, setModels] = useState<GovernanceModelInfo[]>([]);
  const [selected, setSelected] = useState<GovernanceModelInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api.governanceList()
      .then((r) => {
        setModels(r.models);
        if (r.models.length > 0) setSelected(r.models[0]);
      })
      .catch(() => setError('无法加载治理模型，请确认后端已启动'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ padding: 32, color: 'var(--muted)' }}>加载治理模型…</div>;
  if (error)   return <div style={{ padding: 32, color: '#ff5270' }}>{error}</div>;

  return (
    <div style={{ display: 'flex', gap: 16, padding: 16, height: '100%', overflow: 'hidden' }}>
      {/* 左侧：模型列表 */}
      <div style={{ width: 220, flexShrink: 0, overflowY: 'auto' }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 1 }}>
          {models.length} 种治理制度
        </div>
        {models.map((m) => (
          <div
            key={m.type}
            onClick={() => setSelected(m)}
            style={{
              padding: '8px 12px',
              marginBottom: 4,
              borderRadius: 6,
              cursor: 'pointer',
              background: selected?.type === m.type ? 'var(--accent-dim, #1e2a3a)' : 'transparent',
              borderLeft: selected?.type === m.type ? '3px solid var(--accent, #6a9eff)' : '3px solid transparent',
              transition: 'background 0.15s',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 13 }}>{m.name}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
              <span style={{
                background: DYNASTY_COLOR[m.dynasty] || '#6a9eff',
                color: '#000',
                borderRadius: 3,
                padding: '1px 5px',
                fontSize: 10,
                marginRight: 4,
              }}>{m.dynasty}</span>
              {TOPOLOGY_LABEL[m.topology] || m.topology}
            </div>
          </div>
        ))}
      </div>

      {/* 右侧：详情 */}
      {selected && (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* 标题 */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{selected.name}</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>{selected.description}</div>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <Chip label={`来源：${selected.dynasty}`} color={DYNASTY_COLOR[selected.dynasty]} />
              <Chip label={`拓扑：${TOPOLOGY_LABEL[selected.topology] || selected.topology}`} />
              <Chip label={`${selected.states.length} 个状态`} />
              <Chip label={`初始：${selected.initial_state}`} color="#6aef9a" />
            </div>
          </div>

          {/* 状态机流程 */}
          <Section title="状态机流程">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              {selected.states.map((s, i) => {
                const isTerminal = selected.terminal_states.includes(s);
                const isInitial  = s === selected.initial_state;
                return (
                  <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <StateBox state={s} isInitial={isInitial} isTerminal={isTerminal} />
                    {i < selected.states.length - 1 && (
                      <span style={{ color: 'var(--muted)', fontSize: 16 }}>→</span>
                    )}
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)', display: 'flex', gap: 12 }}>
              <span><span style={{ color: '#6aef9a' }}>■</span> 初始状态</span>
              <span><span style={{ color: '#ff5270' }}>■</span> 终态</span>
              <span><span style={{ color: '#6a9eff' }}>■</span> 中间状态</span>
            </div>
          </Section>

          {/* 终态 */}
          <Section title="终止状态">
            <div style={{ display: 'flex', gap: 6 }}>
              {selected.terminal_states.map((s) => (
                <StateBox key={s} state={s} isTerminal />
              ))}
            </div>
          </Section>

          {/* 类型标识 */}
          <Section title="模型标识">
            <code style={{ fontSize: 12, background: 'var(--bg2, #1a1a2e)', padding: '4px 8px', borderRadius: 4 }}>
              governance_type = "{selected.type}"
            </code>
          </Section>
        </div>
      )}
    </div>
  );
}

function Chip({ label, color }: { label: string; color?: string }) {
  return (
    <span style={{
      fontSize: 11,
      padding: '2px 8px',
      borderRadius: 4,
      background: color ? color + '33' : 'var(--bg2, #1a1a2e)',
      color: color || 'var(--muted)',
      border: `1px solid ${color || 'var(--border, #333)'}`,
    }}>
      {label}
    </span>
  );
}

function StateBox({ state, isInitial, isTerminal }: { state: string; isInitial?: boolean; isTerminal?: boolean }) {
  const color = isInitial ? '#6aef9a' : isTerminal ? '#ff5270' : '#6a9eff';
  return (
    <span style={{
      padding: '3px 10px',
      borderRadius: 4,
      fontSize: 12,
      fontWeight: 500,
      background: color + '22',
      border: `1px solid ${color}`,
      color,
    }}>
      {state}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
