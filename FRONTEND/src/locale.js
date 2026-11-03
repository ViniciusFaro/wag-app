// Presentation-only localization. Model class IDs and API keys stay unchanged.
export const number = (value) => new Intl.NumberFormat("pt-BR").format(value);

export const decimal = (value, digits = 2) =>
  new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);

export const percent = (value) =>
  value == null ? "—" : `${decimal(value * 100)}%`;

// Also support a backend already running in English, without requiring a restart.
const API_MESSAGES = {
  "Please choose a PNG, JPG, TIFF or WebP image.":
    "Formato não suportado. Formatos aceitos: PNG, JPG, TIFF e WebP.",
  "Selecione uma imagem PNG, JPG, TIFF ou WebP.":
    "Formato não suportado. Formatos aceitos: PNG, JPG, TIFF e WebP.",
  "Images must be 25 MB or smaller.": "A imagem deve ter no máximo 25 MB.",
  "Please use an image with no more than 40 megapixels.":
    "Resolução máxima permitida: 40 megapixels.",
  "Selecione uma imagem com no máximo 40 megapixels.":
    "Resolução máxima permitida: 40 megapixels.",
  "This file could not be read as an image.":
    "Não foi possível abrir este arquivo como uma imagem.",
  "Sample image is unavailable": "A imagem de exemplo não está disponível.",
  "Sample analysis is unavailable. Run the inference and analysis scripts first.":
    "Análise de exemplo indisponível. É necessária a execução prévia dos scripts de inferência e análise.",
  "A análise de exemplo não está disponível. Execute primeiro os scripts de inferência e análise.":
    "Análise de exemplo indisponível. É necessária a execução prévia dos scripts de inferência e análise.",
  "Analysis not found": "Análise não encontrada.",
  "Analysis could not be completed. Check the backend terminal for details.":
    "Falha no processamento da análise. Detalhes disponíveis no terminal do servidor Python.",
  "Não foi possível concluir a análise. Consulte o terminal do servidor Python para ver os detalhes.":
    "Falha no processamento da análise. Detalhes disponíveis no terminal do servidor Python.",
  "The backend restarted during analysis. Please upload the image again.":
    "Análise interrompida pelo reinício do servidor. É necessário reenviar a imagem.",
  "O servidor foi reiniciado durante a análise. Envie a imagem novamente.":
    "Análise interrompida pelo reinício do servidor. É necessário reenviar a imagem.",
};

export const localizeApiMessage = (message) => API_MESSAGES[message] || message;
