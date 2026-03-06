import { useState, useEffect } from 'react';
import { api } from '../api';
import type { GovernanceModelSummary, GovernanceDetail, MechanismInfo } from '../api';
import { GOVERNANCE_ICONS, MECHANISM_NAMES } from '../store';

const FLOW_PATTERN_LABELS: Record<string, string> = {
  linear: '线性流水线',
  hub_spoke: '中心辐射型',
  collective: '集体商议',
  debate_vote: '辩论投票',
  fast_track: '极简快速',
  decentralized: '去中心化',
  flat_consensus: '扁平共识',
  executive_advisory: '强执行+顾问',
  multi_level: '多级治理',
};

export default function GovernancePanel() {
  const [models, setModels] = useState<GovernanceModelSummary[]>([]);
  const [mechanisms, setMechanisms] = useState<MechanismInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<GovernanceDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.governanceList(), api.mechanismsList()])
      .then(([gl, ml]) => {
        setModels(gl.models);
        setMechanisms(ml.mechanisms);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    api.governanceDetail(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected]);

  if (loading) return <div className="p-8 text-center text-gray-400">加载治理制度数据...</div>;

  return (
    <div className="p-4 space-y-6">
      {/* 制度概览 */}
      <div>
        <h2 className="text-lg font-bold mb-3">治理制度总览</h2>
        <p className="text-sm text-gray-400 mb-4">
          9 种基础治理制度 + 3 种跨制度机制。每个任务可独立选择治理模式。
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {models.map((m) => (
            <div
              key={m.type}
              onClick={() => setSelected(selected === m.type ? null : m.type)}
              className={`cursor-pointer rounded-lg border p-4 transition-all hover:border-blue-400 ${
                selected === m.type
                  ? 'border-blue-500 bg-blue-900/20 ring-1 ring-blue-500/50'
                  : 'border-gray-700 bg-gray-800/50'
              }`}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">{GOVERNANCE_ICONS[m.type] || '🏛️'}</span>
                <span className="font-bold">{m.name}</span>
                <span className="text-xs text-gray-500 ml-auto">{m.dynasty}</span>
              </div>
              <p className="text-xs text-gray-400 mb-2 line-clamp-2">{m.description}</p>
              <div className="flex flex-wrap gap-1">
                <span className="text-[10px] px-1.5 py-0.5 bg-gray-700 rounded">
                  {FLOW_PATTERN_LABELS[m.flow_pattern] || m.flow_pattern}
                </span>
                {m.states_count && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-gray-700 rounded">
                    {m.states_count} 状态
                  </span>
                )}
                {m.roles_count && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-gray-700 rounded">
                    {m.roles_count} 角色
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {m.suitable_for.slice(0, 3).map((s) => (
                  <span key={s} className="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 跨制度机制 */}
      <div>
        <h2 className="text-lg font-bold mb-3">跨制度机制</h2>
        <p className="text-sm text-gray-400 mb-3">可叠加到任何基础制度上的增强机制。</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {mechanisms.map((m) => (
            <div key={m.type} className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">
                  {m.type === 'ke_ju' ? '📝' : m.type === 'yu_shi_tai' ? '👁️' : '📊'}
                </span>
                <span className="font-bold">{MECHANISM_NAMES[m.type] || m.name}</span>
              </div>
              <p className="text-xs text-gray-400">{m.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 制度详情 */}
      {detail && (
        <div className="border border-gray-700 rounded-lg bg-gray-800/30 p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-3xl">{GOVERNANCE_ICONS[detail.type] || '🏛️'}</span>
            <div>
              <h3 className="text-xl font-bold">{detail.name}</h3>
              <span className="text-xs text-gray-500">{detail.dynasty} · {FLOW_PATTERN_LABELS[detail.flow_pattern] || detail.flow_pattern}</span>
            </div>
          </div>
          <p className="text-sm text-gray-300 mb-4">{detail.description}</p>

          {/* 状态流转 */}
          <div className="mb-4">
            <h4 className="text-sm font-bold mb-2 text-gray-200">状态流转</h4>
            <div className="flex flex-wrap items-center gap-1 mb-2">
              {detail.states.map((s, i) => {
                const isInitial = s === detail.initial_state;
                const isTerminal = detail.terminal_states.includes(s);
                return (
                  <span key={s} className="flex items-center gap-1">
                    {i > 0 && <span className="text-gray-600 text-xs">→</span>}
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        isInitial
                          ? 'bg-green-900/40 text-green-300 border border-green-700'
                          : isTerminal
                          ? 'bg-red-900/40 text-red-300 border border-red-700'
                          : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {s}
                    </span>
                  </span>
                );
              })}
            </div>
            <div className="text-[10px] text-gray-500">
              <span className="text-green-400">●</span> 初始状态 &nbsp;
              <span className="text-red-400">●</span> 终态
            </div>
          </div>

          {/* 流转规则 */}
          <div className="mb-4">
            <h4 className="text-sm font-bold mb-2 text-gray-200">流转规则</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {Object.entries(detail.transitions).map(([from, tos]) => (
                <div key={from} className="text-xs flex items-center gap-1">
                  <span className="font-mono bg-gray-700 px-1.5 py-0.5 rounded min-w-[100px]">{from}</span>
                  <span className="text-gray-600">→</span>
                  <span className="text-gray-400">{tos.join(' / ')}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 角色 */}
          <div className="mb-4">
            <h4 className="text-sm font-bold mb-2 text-gray-200">角色定义</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {detail.roles.map((r) => (
                <div key={r.role_id} className="flex items-center gap-2 text-xs bg-gray-800 rounded p-2">
                  <span className="font-bold text-blue-300">{r.name}</span>
                  <span className="text-gray-400 flex-1">{r.description}</span>
                  {r.agent_id && (
                    <span className="font-mono text-[10px] bg-gray-700 px-1 rounded">{r.agent_id}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 权限矩阵 */}
          <div>
            <h4 className="text-sm font-bold mb-2 text-gray-200">权限矩阵</h4>
            <div className="overflow-x-auto">
              <table className="text-[10px] w-full">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left p-1 text-gray-400">From ↓ → To</th>
                    {Object.keys(detail.permission_matrix).map((k) => (
                      <th key={k} className="p-1 text-center text-gray-400">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(detail.permission_matrix).map(([from, tos]) => (
                    <tr key={from} className="border-b border-gray-800">
                      <td className="p-1 font-bold text-gray-300">{from}</td>
                      {Object.keys(detail.permission_matrix).map((col) => (
                        <td key={col} className="p-1 text-center">
                          {tos.includes(col) ? (
                            <span className="text-green-400">✓</span>
                          ) : from === col ? (
                            <span className="text-gray-600">—</span>
                          ) : (
                            <span className="text-gray-700">·</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
