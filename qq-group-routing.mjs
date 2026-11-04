export function isDirectGroupMessage({ mentioned = false, text = '' } = {}) {
  if (mentioned) return true;
  return /(?:江生|林夏)/u.test(String(text));
}
