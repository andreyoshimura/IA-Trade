function driveService_obterPastaDestino(fornecedor) {
  const raiz = DriveApp.getFoldersByName(CONFIG.PASTA_RAIZ).next();
  const ano = new Date().getFullYear().toString();
  let pastaAno = raiz.getFoldersByName(ano);
  pastaAno = pastaAno.hasNext() ? pastaAno.next() : raiz.createFolder(ano);

  const mes = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "MM-yyyy");
  let pastaMes = pastaAno.getFoldersByName(mes);
  pastaMes = pastaMes.hasNext() ? pastaMes.next() : pastaAno.createFolder(mes);

  let pastaFornecedor = pastaMes.getFoldersByName(fornecedor);
  pastaFornecedor = pastaFornecedor.hasNext() ? pastaFornecedor.next() : pastaMes.createFolder(fornecedor);

  return pastaFornecedor;
}

function driveService_salvarAnexo(anexo, pasta) {
  if (!anexo) return null;
  return pasta.createFile(anexo);
}