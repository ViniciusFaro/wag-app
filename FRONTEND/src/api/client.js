import { localizeApiMessage } from "../locale.js";

export async function request(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Falha na conexão com o servidor de análise. O servidor Python precisa estar em execução.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(
      typeof data?.detail === "string"
        ? localizeApiMessage(data.detail)
        : response.status === 422
          ? "Os filtros informados são inválidos. Verificar os valores e o intervalo de datas."
          : "Servidor de análise indisponível. Detalhes no terminal do servidor Python.",
    );
    error.status = response.status;
    throw error;
  }
  return data;
}

export function listExperiments(params, options) {
  return request(`/api/experiments?${new URLSearchParams(params)}`, options);
}

export function getExperiment(id, options) {
  return request(`/api/experiments/${encodeURIComponent(id)}`, options);
}
