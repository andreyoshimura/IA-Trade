function gmailService_identificarFornecedor(message) {
  const from = message.getFrom().toLowerCase();
  if (from.includes("cpfl.com.br")) return "CPFL";
  return null;
}

function gmailService_obterAnexo(message) {
  const anexos = message.getAttachments();
  if (anexos.length > 0) return anexos[0];
  return null;
}