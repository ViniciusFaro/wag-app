import { useState } from "react";
import { decimal, number } from "./locale.js";
import "./ResidualOil.css";

const percentage = (value) => (value == null ? "—" : `${decimal(value)}%`);

export function ResidualOilMetrics({ data, compact = false }) {
  if (!data) return null;
  const available = data.initial_oil_equivalent_px > 0;
  const metrics = [
    {
      label: "Óleo inicial equivalente",
      percent: data.initial_oil_equivalent_percent,
      pixels: data.initial_oil_equivalent_px,
      formula: "Água + óleo + gás",
      type: "initial",
    },
    {
      label: "Fração residual (óleo + gás)",
      percent: data.residual_percent,
      pixels: data.residual_oil_gas_px,
      formula: "(Óleo + gás) / óleo inicial × 100",
      type: "remaining",
    },
    {
      label: "Óleo removido equivalente",
      percent: data.removed_percent,
      pixels: data.removed_oil_equivalent_px,
      formula: "Água / óleo inicial × 100",
      type: "removed",
    },
  ];
  return (
    <div className={`residual-summary ${compact ? "residual-compact" : ""}`}>
      <div className="residual-metrics">
        {metrics.map((metric) => (
          <div
            className={`residual-metric residual-${metric.type}`}
            key={metric.type}
          >
            <h3>{metric.label}</h3>
            <strong>{percentage(metric.percent)}</strong>
            <span>{number(metric.pixels)} pixels</span>
            <p>{metric.formula}</p>
          </div>
        ))}
      </div>
      {available ? (
        <div className="residual-balance">
          <div className="residual-balance-label">
            <span>Balanço em relação ao óleo inicial</span>
            <span>Residual + removido = 100%</span>
          </div>
          <div
            className="residual-balance-bar"
            role="img"
            aria-label={`Residual: ${percentage(data.residual_percent)}; removido: ${percentage(data.removed_percent)}`}
          >
            <span
              className="remaining"
              style={{ width: `${data.residual_percent}%` }}
            />
            <span
              className="removed"
              style={{ width: `${data.removed_percent}%` }}
            />
          </div>
          <div className="residual-balance-legend">
            <span>
              <i className="remaining" />
              Residual {percentage(data.residual_percent)}
            </span>
            <span>
              <i className="removed" />
              Removido {percentage(data.removed_percent)}
            </span>
          </div>
        </div>
      ) : (
        <p className="residual-empty" role="status">
          Sem pixels de água, óleo ou gás nesta área. Percentuais não definidos.
        </p>
      )}
      <div
        className="residual-inputs"
        aria-label="Áreas por classe usadas no cálculo"
      >
        {[
          {
            label: "Água",
            count: data.water_px,
            percent: data.removed_percent,
            color: "#749de8",
          },
          {
            label: "Óleo",
            count: data.oil_px,
            percent: data.oil_percent,
            color: "#e3676d",
          },
          {
            label: "Gás",
            count: data.gas_px,
            percent: data.gas_percent,
            color: "#77c6a3",
          },
        ].map((phase) => (
          <div key={phase.label}>
            <span>
              <i style={{ background: phase.color }} />
              {phase.label}
            </span>
            <strong>{number(phase.count)} pixels</strong>
            <small>{percentage(phase.percent)} do óleo inicial</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ResidualOilSection({ composition, assets }) {
  const [scope, setScope] = useState("deadends");
  const data = composition[scope].residual_oil;
  return (
    <section
      className="panel residual-panel"
      id="oleo-residual"
      aria-labelledby="residual-oil-title"
    >
      <div className="residual-heading">
        <div>
          <span className="step-label">03 / ÓLEO RESIDUAL E REMOÇÃO</span>
          <h2 id="residual-oil-title">Óleo residual em Dead ends</h2>
          <p>
            Estimativa por área a partir das classes segmentadas, com exclusão
            da parede.
          </p>
        </div>
        <div className="button-row">
          {assets.residual_report && (
            <a
              href={assets.residual_report}
              download
              className="secondary-button"
            >
              Exportar JSON
            </a>
          )}
          {assets.residual_csv && (
            <a href={assets.residual_csv} download className="secondary-button">
              Exportar CSV
            </a>
          )}
        </div>
      </div>
      <div
        className="residual-scope"
        role="group"
        aria-label="Área de referência do óleo residual"
      >
        <button
          aria-pressed={scope === "deadends"}
          className={scope === "deadends" ? "active" : ""}
          onClick={() => setScope("deadends")}
        >
          Dead ends (união das caixas)
        </button>
        <button
          aria-pressed={scope === "full_image"}
          className={scope === "full_image" ? "active" : ""}
          onClick={() => setScope("full_image")}
        >
          Imagem completa
        </button>
        {composition.outside_deadends && (
          <button
            aria-pressed={scope === "outside_deadends"}
            className={scope === "outside_deadends" ? "active" : ""}
            onClick={() => setScope("outside_deadends")}
          >
            Fora dos Dead ends
          </button>
        )}
      </div>
      <p className="residual-scope-note">
        {scope === "deadends"
          ? "Cálculo sobre a união das caixas detectadas. Pixels sobrepostos são contados uma única vez."
          : scope === "outside_deadends"
            ? "Cálculo sobre os pixels externos à união das caixas de Dead ends, excluindo a parede."
            : "Cálculo sobre todos os pixels de água, óleo e gás da imagem segmentada."}
      </p>
      {data ? (
        <ResidualOilMetrics data={data} />
      ) : (
        <p className="residual-empty">
          Indicador indisponível nesta resposta. Reiniciar o servidor Python
          para carregar a nova análise.
        </p>
      )}
      <div className="residual-method">
        <strong>Hipótese de referência</strong>
        <p>
          A área de água + óleo + gás é considerada inicialmente preenchida por
          óleo. Óleo + gás representam a fração residual; a água representa o
          óleo removido equivalente. Os valores são estimativas de área em
          pixels a partir de uma imagem, sem conversão para volume.
        </p>
      </div>
    </section>
  );
}
