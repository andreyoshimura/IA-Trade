function financeService_extrairDados(message, fornecedor) {
  const body = message.getBody();
  const valorMatch = body.match(/R\$ ?(\d+[.,]\d{2})/);
  const dataMatch = body.match(/(\d{2}\/\d{2}\/\d{4})/);

  return {
    valor: valorMatch ? valorMatch[1] : "0.00",
    dataVencimento: dataMatch ? dataMatch[1] : "",
    dataCompetencia: new Date()
  };
}