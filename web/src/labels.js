/* One vocabulary for the whole page.

   The API speaks in the payload's field codes and the registry's check names,
   which is right for a wire format and wrong for a person reading a verdict.
   The translation lives in one module so the table, the overlay tags and the
   adjudication panel cannot drift apart. */

const FIELDS = {
  id: "Invoice number",
  amt: "Amount",
  cur: "Currency",
  iban: "Account (IBAN)",
  bic: "Bank code (BIC)",
};

const CHECKS = {
  signature: "signature",
  identity: "identity",
  lookalike: "lookalike domain",
  duplicate: "seen before",
  domain_age: "domain age",
  fidelity: "page match",
  counterparty: "counterparty",
};

export function fieldLabel(name) {
  return FIELDS[name] ?? name.replace(/_/g, " ");
}

export function checkLabel(name) {
  return CHECKS[name] ?? name.replace(/_/g, " ");
}

/* The authoritative list of fields a person has to settle. The check marks a
   field doubtful for two reasons, and only one of them is a low score: a
   confidently offered value that cannot be what it claims to be counts too,
   so recomputing "confidence < threshold" here would silently drop the case
   the shape check exists for. */
export function uncertainFields(fidelity) {
  return new Set(fidelity?.evidence?.uncertain ?? []);
}
