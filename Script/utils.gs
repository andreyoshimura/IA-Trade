function gerarHash(texto) {
  const raw = Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, texto);
  return raw.map(byte => (byte + 256).toString(16).slice(-2)).join("");
}