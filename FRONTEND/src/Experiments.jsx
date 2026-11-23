import { useEffect, useState } from "react";
import { Link, NavLink, useSearchParams } from "react-router-dom";
import Icon from "./Icon.jsx";
import { listExperiments } from "./api/client.js";
import { decimal, number, percent } from "./locale.js";
import "./Experiments.css";

const dateTime = (value) =>
  value
    ? new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value))
    : "Não registrado";
const dimensions = (value) =>
  value ? `${value.join(" × ")} px` : "Não registrada";
const SCOPES = [
  ["full_image", "Imagem completa"],
  ["deadends", "Nos Dead ends (união)"],
  ["outside_deadends", "Fora dos Dead ends"],
];

export function EntryOptions() {
  return (
    <nav className="entry-options" aria-label="Modo de trabalho">
      <NavLink to="/" end>
        <span className="entry-icon">
          <Icon name="upload" size={23} />
        </span>
        <span>
          <strong>Nova análise</strong>
          <small>Importação e processamento de imagem</small>
        </span>
        <Icon name="chevron" size={17} />
      </NavLink>
      <NavLink to="/experiments">
        <span className="entry-icon">
          <Icon name="database" size={23} />
        </span>
        <span>
          <strong>Consultar experimentos</strong>
          <small>Resultados e regiões já armazenados</small>
        </span>
        <Icon name="chevron" size={17} />
      </NavLink>
    </nav>
  );
}

export default function ExperimentsPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") || "";
  const from = params.get("from") || "";
  const until = params.get("until") || "";
  const sort = params.get("sort") || "recent";
  const limit = [10, 20, 50].includes(Number(params.get("limit")))
    ? Number(params.get("limit"))
    : 10;
  const rawPage = Number(params.get("page") || 0);
  const page = Number.isSafeInteger(rawPage) && rawPage >= 0 ? rawPage : 0;
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState({
    loading: true,
    data: null,
    error: "",
  });
  const queryString = params.toString();
  function change(key, value) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        if (value) next.set(key, value);
        else next.delete(key);
        if (key !== "page") next.delete("page");
        return next;
      },
      { replace: true },
    );
  }
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setResult({ loading: true, data: null, error: "" });
    const timer = setTimeout(async () => {
      try {
        const sorting = {
          recent: ["saved_at", "desc"],
          oldest: ["saved_at", "asc"],
          name: ["name", "asc"],
          regions: ["deadend_count", "desc"],
        }[sort] || ["saved_at", "desc"];
        const filters = {
          limit,
          offset: page * limit,
          sort_by: sorting[0],
          order: sorting[1],
        };
        if (query.trim()) filters.q = query.trim();
        if (from)
          filters.saved_from = new Date(`${from}T00:00:00`).toISOString();
        if (until)
          filters.saved_until = new Date(`${until}T23:59:59.999`).toISOString();
        const data = await listExperiments(filters, {
          signal: controller.signal,
        });
        if (!active) return;
        if (page > 0 && page * limit >= data.total) {
          setParams(
            (previous) => {
              const next = new URLSearchParams(previous);
              next.set(
                "page",
                String(Math.max(0, Math.ceil(data.total / limit) - 1)),
              );
              return next;
            },
            { replace: true },
          );
          return;
        }
        setResult({ loading: false, data, error: "" });
      } catch (error) {
        if (active && error.name !== "AbortError")
          setResult({
            loading: false,
            data: null,
            error:
              error instanceof RangeError
                ? "Intervalo de datas inválido."
                : error.message,
          });
      }
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [queryString, query, from, until, sort, limit, page, refresh, setParams]);
  const filtered = Boolean(query || from || until);
  const data = result.data;
  const pages = Math.max(1, Math.ceil((data?.total || 0) / limit));
  return (
    <div className="page history-page">
      <div className="breadcrumb">
        <Link to="/">Área de trabalho</Link>
        <Icon name="chevron" size={13} />
        <span>Experimentos salvos</span>
      </div>
      <section className="upload-intro history-intro">
        <div>
          <span className="eyebrow">
            <span />
            CONSULTA AO HISTÓRICO
          </span>
          <h1>Experimentos salvos</h1>
          <p>
            Consulta de resultados, composição dos fluidos e regiões
            <br className="desktop-break" /> de análises registradas no banco de
            dados.
          </p>
        </div>
        <span className="history-source">
          <Icon name="database" size={18} />
          Resultados armazenados
        </span>
      </section>
      <EntryOptions />
      <section className="panel history-panel" aria-labelledby="history-title">
        <div className="history-heading">
          <div>
            <span className="step-label">REGISTROS DE EXPERIMENTOS</span>
            <h2 id="history-title">Histórico de análises</h2>
            <p>Resultados existentes, sem novo processamento de imagem.</p>
          </div>
          <button
            className="secondary-button"
            onClick={() => setRefresh((value) => value + 1)}
            disabled={result.loading}
          >
            <Icon name="refresh" size={16} />
            Atualizar
          </button>
        </div>
        <div className="history-filters">
          <label className="history-search">
            <span>Nome, arquivo ou identificação</span>
            <div className="search-field">
              <Icon name="search" size={17} />
              <input
                type="search"
                value={query}
                onChange={(event) => change("q", event.target.value)}
                placeholder="Buscar experimentos…"
                maxLength={512}
              />
            </div>
          </label>
          <label>
            <span>Salvo a partir de</span>
            <input
              type="date"
              value={from}
              max={until || undefined}
              onChange={(event) => change("from", event.target.value)}
            />
          </label>
          <label>
            <span>Salvo até</span>
            <input
              type="date"
              value={until}
              min={from || undefined}
              onChange={(event) => change("until", event.target.value)}
            />
          </label>
          <label>
            <span>Ordenação</span>
            <select
              value={sort}
              onChange={(event) => change("sort", event.target.value)}
            >
              <option value="recent">Mais recentes</option>
              <option value="oldest">Mais antigos</option>
              <option value="name">Nome do experimento</option>
              <option value="regions">Mais Dead ends</option>
            </select>
          </label>
        </div>
        <div className="history-count" role="status" aria-live="polite">
          <span>
            {result.loading
              ? "Consultando registros…"
              : data
                ? `${number(data.total)} ${data.total === 1 ? "experimento encontrado" : "experimentos encontrados"}`
                : "Consulta indisponível"}
          </span>
          {filtered && (
            <button onClick={() => setParams({}, { replace: true })}>
              Limpar filtros
            </button>
          )}
        </div>
        {result.loading ? (
          <div className="history-empty" role="status">
            <span className="spinner" />
            <p>Carregando experimentos salvos…</p>
          </div>
        ) : result.error ? (
          <div className="history-empty">
            <Icon name="info" size={28} />
            <h3>Histórico indisponível</h3>
            <p role="alert">{result.error}</p>
            <button
              className="secondary-button"
              onClick={() => setRefresh((value) => value + 1)}
            >
              Tentar novamente
            </button>
          </div>
        ) : !data?.items.length ? (
          <div className="history-empty">
            <Icon name={filtered ? "search" : "database"} size={30} />
            <h3>
              {filtered
                ? "Nenhum experimento encontrado"
                : "Nenhum experimento salvo"}
            </h3>
            <p>
              {filtered
                ? "Nenhum registro corresponde aos filtros informados."
                : "As novas análises são registradas automaticamente após a conclusão."}
            </p>
            {filtered ? (
              <button
                className="secondary-button"
                onClick={() => setParams({})}
              >
                Limpar filtros
              </button>
            ) : (
              <Link to="/" className="primary-button">
                Nova análise
                <Icon name="plus" size={17} />
              </Link>
            )}
          </div>
        ) : (
          <div className="table-scroll">
            <table className="history-table">
              <thead>
                <tr>
                  <th>EXPERIMENTO / ARQUIVO</th>
                  <th>SALVAMENTO</th>
                  <th>DEAD ENDS</th>
                  <th>ÓLEO NAS CAIXAS</th>
                  <th>RESIDUAL NAS CAIXAS</th>
                  <th>RESOLUÇÃO DE ANÁLISE</th>
                  <th>
                    <span className="visually-hidden">
                      Consultar resultados
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        className="experiment-name"
                        to={`/experiments/${item.id}`}
                        state={{ historySearch: queryString }}
                      >
                        {item.name}
                        <small>{item.filename}</small>
                        <code title={item.id}>ID {item.id.slice(0, 12)}…</code>
                      </Link>
                    </td>
                    <td>{dateTime(item.saved_at)}</td>
                    <td className="experiment-count">
                      {number(item.deadend_count)}
                    </td>
                    <td className="oil-value">
                      {percent(item.composition.deadends.class_fractions.Oil)}
                    </td>
                    <td>
                      {item.composition.deadends.residual_oil
                        .residual_percent == null
                        ? "—"
                        : `${decimal(item.composition.deadends.residual_oil.residual_percent)}%`}
                    </td>
                    <td>{dimensions(item.analysis_size_wh)}</td>
                    <td>
                      <Link
                        className="secondary-button"
                        to={`/experiments/${item.id}`}
                        state={{ historySearch: queryString }}
                        aria-label={`Abrir experimento ${item.name}`}
                      >
                        Abrir
                        <Icon name="arrow" size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination history-pagination">
          <label>
            Por página{" "}
            <select
              aria-label="Experimentos por página"
              value={limit}
              onChange={(event) => change("limit", event.target.value)}
            >
              {[10, 20, 50].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <div>
            <button
              className="icon-button"
              disabled={result.loading || page === 0}
              onClick={() => change("page", String(page - 1))}
              aria-label="Página anterior de experimentos"
            >
              <Icon name="back" size={15} />
            </button>
            <span>
              Página {page + 1} de {pages}
            </span>
            <button
              className="icon-button"
              disabled={result.loading || page + 1 >= pages}
              onClick={() => change("page", String(page + 1))}
              aria-label="Próxima página de experimentos"
            >
              <Icon name="chevron" size={15} />
            </button>
          </div>
        </div>
        <p className="history-footnote">
          <Icon name="info" size={15} />
          Óleo: apenas a classe óleo. Residual: óleo + gás. Percentuais
          calculados sobre os pixels de fluido da união das caixas, excluindo a
          parede.
        </p>
      </section>
    </div>
  );
}

export function ExperimentInfo({ experiment }) {
  const fields = [
    ["Arquivo de entrada", experiment.filename],
    ["Criação da análise", dateTime(experiment.created_at)],
    ["Conclusão da análise", dateTime(experiment.completed_at)],
    ["Salvamento no banco", dateTime(experiment.saved_at)],
    ["Resolução original", dimensions(experiment.image_size_wh)],
    ["Resolução de análise", dimensions(experiment.analysis_size_wh)],
    ["Máscara da UNet", dimensions(experiment.segmentation_size_wh)],
    ["Dispositivo de inferência", experiment.device.toUpperCase()],
  ];
  return (
    <section
      className="panel experiment-info"
      aria-labelledby="experiment-info-title"
    >
      <div className="history-heading">
        <div>
          <span className="step-label">REGISTRO DO EXPERIMENTO</span>
          <h2 id="experiment-info-title">Informações do experimento</h2>
        </div>
        <span className="history-source">
          <Icon name="database" size={16} />
          Consulta ao banco
        </span>
      </div>
      <dl className="experiment-fields">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <dl className="experiment-identifiers">
        <div>
          <dt>ID do experimento</dt>
          <dd>
            <code>{experiment.id}</code>
          </dd>
        </div>
        <div>
          <dt>ID da análise</dt>
          <dd>
            <code>{experiment.analysis_id}</code>
          </dd>
        </div>
        {experiment.image_sha256 && (
          <div>
            <dt>SHA-256 da imagem</dt>
            <dd>
              <code>{experiment.image_sha256}</code>
            </dd>
          </div>
        )}
      </dl>
      {experiment.notes && (
        <div className="experiment-notes">
          <strong>Observações</strong>
          <p>{experiment.notes}</p>
        </div>
      )}
      <details className="experiment-settings">
        <summary>Parâmetros e informações dos modelos</summary>
        <pre>
          {JSON.stringify(
            {
              parametros: experiment.parameters,
              inferencia: experiment.inference,
            },
            null,
            2,
          )}
        </pre>
      </details>
    </section>
  );
}

export function NumericalResults({ composition }) {
  return (
    <section
      className="panel numerical-panel"
      aria-labelledby="numerical-title"
    >
      <div className="history-heading">
        <div>
          <span className="step-label">RESULTADOS NUMÉRICOS</span>
          <h2 id="numerical-title">Composição por área de referência</h2>
          <p>
            Frações dos fluidos e balanço de óleo na imagem completa, dentro e
            fora dos Dead ends.
          </p>
        </div>
      </div>
      <div className="table-scroll">
        <table className="numerical-table">
          <thead>
            <tr>
              <th>ÁREA DE REFERÊNCIA</th>
              <th>ÁREA TOTAL (PX)</th>
              <th>FLUIDOS (PX)</th>
              <th>PAREDE (PX)</th>
              <th>ÁGUA</th>
              <th>ÓLEO</th>
              <th>GÁS</th>
              <th>RESIDUAL (ÓLEO + GÁS)</th>
              <th>REMOVIDO EQUIVALENTE</th>
            </tr>
          </thead>
          <tbody>
            {SCOPES.filter(([key]) => composition[key]).map(([key, label]) => {
              const group = composition[key];
              return (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  <td>{number(group.area_px)}</td>
                  <td>{number(group.fluid_area_px)}</td>
                  <td>{number(group.excluded_wall_px)}</td>
                  <td>{percent(group.class_fractions.Water)}</td>
                  <td className="oil-value">
                    {percent(group.class_fractions.Oil)}
                  </td>
                  <td>{percent(group.class_fractions.Gas)}</td>
                  <td>
                    {group.residual_oil.residual_percent == null
                      ? "—"
                      : `${decimal(group.residual_oil.residual_percent)}%`}
                  </td>
                  <td>
                    {group.residual_oil.removed_percent == null
                      ? "—"
                      : `${decimal(group.residual_oil.removed_percent)}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="history-footnote">
        <Icon name="info" size={15} />A parede é excluída dos percentuais. O
        óleo inicial equivalente corresponde à área fluida. Agregados usam a
        união das caixas, sem duplicar sobreposições.
      </p>
    </section>
  );
}
