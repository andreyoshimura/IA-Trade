function sheetService_getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(CONFIG.ABA_LANCAMENTOS);
}

function sheetService_existeMessageId(messageId) {
  const sheet = sheetService_getSheet();
  const dados = sheet.getRange(2, 1, sheet.getLastRow(), 1).getValues();
  return dados.flat().includes(messageId);
}

function sheetService_inserirLancamento(dados) {
  const sheet = sheetService_getSheet();
  sheet.appendRow([
    dados.messageId,
    new Date(),
    dados.dataCompetencia,
    dados.fornecedor,
    dados.valor,
    dados.dataVencimento,
    "PENDENTE",
    dados.linkArquivo
  ]);
}

function sheetService_verificarPendentes(hoje) {
  const sheet = sheetService_getSheet();
  const dados = sheet.getDataRange().getValues();
  for (let i = 1; i < dados.length; i++) {
    const vencimento = new Date(dados[i][5]);
    const status = dados[i][6];
    if (status === "PENDENTE" && vencimento <= hoje) {
      MailApp.sendEmail(Session.getActiveUser().getEmail(),
        "Conta vencida",
        "Conta do fornecedor " + dados[i][3] + " está vencida.");
    }
  }
}