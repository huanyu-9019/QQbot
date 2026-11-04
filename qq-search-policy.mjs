import { readFileSync } from 'node:fs';

const configPath = `${process.env.HOME}/.hermes/config.yaml`;

// The search-only toolset is not listed by /v1/toolsets, so check both the
// configured allowlist and the endpoint's visible toolsets before each run.
export function assertConfiguredSearchOnly(configText) {
  let sections = 0;
  let inPlatformToolsets = false;
  const apiEntries = [];

  for (const line of configText.split(/\r?\n/)) {
    if (/^platform_toolsets:\s*(?:#.*)?$/.test(line)) {
      sections += 1;
      inPlatformToolsets = true;
      continue;
    }
    if (inPlatformToolsets && /^\S/.test(line) && !line.startsWith('#')) {
      inPlatformToolsets = false;
    }
    if (inPlatformToolsets) {
      const match = line.match(/^  api_server:\s*(.*?)\s*$/);
      if (match) apiEntries.push(match[1]);
    }
  }

  if (sections !== 1 || apiEntries.length !== 1 || apiEntries[0] !== '[search]') {
    throw new Error('QQ API 工具配置不再是仅网页搜索，已拒绝处理消息');
  }
}

export async function assertSearchOnlyAccess(api, headers, fetchImpl = fetch) {
  assertConfiguredSearchOnly(readFileSync(configPath, 'utf8'));
  const response = await fetchImpl(`${api}/v1/toolsets`, {
    headers,
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`工具检查 HTTP ${response.status}`);
  const toolsets = await response.json();
  // xAI may expose its native X search in addition to the search-only bundle.
  // Permit only that exact tool; no other enabled capability is accepted.
  const nativeSearchOnly = entry => entry.name === 'x_search' &&
    entry.enabled === true && Array.isArray(entry.tools) &&
    entry.tools.length === 1 && entry.tools[0] === 'x_search';
  if (toolsets.platform !== 'api_server' || !Array.isArray(toolsets.data) ||
      !toolsets.data.some(x => x.name === 'web') ||
      toolsets.data.some(x => x.enabled !== false && !nativeSearchOnly(x))) {
    throw new Error('QQ API 出现额外工具权限，已拒绝处理消息');
  }
}
