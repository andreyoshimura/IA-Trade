function processarEmails() {
  const threads = GmailApp.search('label:FINANCEIRO/ENTRADA');
  threads.forEach(thread => {
    const messages = thread.getMessages();
    messages.forEach(message => {
      const messageId = message.getId();
      if (sheetService_existeMessageId(messageId)) return;

      const fornecedor = gmailService_identificarFornecedor(message);
      if (!fornecedor) return;

      const anexo = gmailService_obterAnexo(message);
      const pasta = driveService_obterPastaDestino(fornecedor);

      const arquivo = driveService_salvarAnexo(anexo, pasta);

      const dados = financeService_extrairDados(message, fornecedor);

      sheetService_inserirLancamento({
        messageId: messageId,
        fornecedor: fornecedor,
        valor: dados.valor,
        dataVencimento: dados.dataVencimento,
        dataCompetencia: dados.dataCompetencia,
        linkArquivo: arquivo.getUrl()
      });

      thread.removeLabel(GmailApp.getUserLabelByName("FINANCEIRO/ENTRADA"));
      thread.addLabel(GmailApp.getUserLabelByName("FINANCEIRO/PROCESSADO"));
    });
  });
}

function verificarVencimentos() {
  const hoje = new Date();
  sheetService_verificarPendentes(hoje);
}