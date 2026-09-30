// Claude 对话导出（含上传图片）
//
// 基于 agarwalvishal/claude-chat-exporter（MIT，见同目录 LICENSE）改写。
// 上游只把图片写成需要登录才能加载的 claude.ai 链接；这里在生成 Markdown 之前
// 用同源请求把每个上传的图片（以及 PDF 文档）下载下来，打包进 ZIP，并把链接改写为
// attachments/ 下的相对路径，离线、换设备、会话过期后都能正常显示，可直接解压进 Obsidian 库。
//
// 用法：在 claude.ai 页面打开开发者工具控制台，粘贴整个文件回车。
//   • 当前页是某个对话 → 导出这个对话
//   • 当前页不是对话（首页、/recents 等）→ 确认后批量导出全部历史对话
//
// 可选项：粘贴前先在控制台执行 window.claudeExportOptions = { ... }，字段见 DEFAULTS。
(() => {
  'use strict';

  const DEFAULTS = {
    images: 'zip',          // 'zip'：图片打包进 ZIP 用相对路径引用；'base64'：内嵌为 data URI
    documents: true,        // 是否一并下载上传的 PDF 等文档
    mode: 'auto',           // 'auto' | 'single' | 'all'
    delayMs: 300,           // 批量导出时每个对话之间的间隔，避免触发限流
    attachmentsDir: 'attachments'
  };
  const OPTS = Object.assign({}, DEFAULTS, window.claudeExportOptions || {});

  const warnings = [];
  const warn = (msg) => { console.warn('[claude-export]', msg); warnings.push(msg); };
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const encoder = new TextEncoder();

  // ───────────────────────── 网络 ─────────────────────────

  // 同源请求，自带登录态。429 与 5xx 按指数退避重试。
  async function request(url, kind) {
    let lastError;
    for (let attempt = 0; attempt < 4; attempt++) {
      if (attempt) await sleep(1000 * 2 ** attempt);
      let res;
      try {
        res = await fetch(url, { credentials: 'include' });
      } catch (e) {
        lastError = new Error(`无法连接 ${url}：${e.message}`);
        continue;
      }
      if (res.status === 429 || res.status >= 500) {
        lastError = new Error(`请求 ${url} 失败（HTTP ${res.status}）`);
        continue;
      }
      if (!res.ok) {
        const hint = (res.status === 401 || res.status === 403) ? '，登录可能已过期，请刷新页面重新登录' : '';
        throw new Error(`请求 ${url} 失败（HTTP ${res.status}）${hint}`);
      }
      if (kind === 'json') return res.json();
      const type = (res.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
      return { bytes: new Uint8Array(await res.arrayBuffer()), type };
    }
    throw lastError;
  }

  function getOrgId() {
    const orgId = document.cookie.match(/lastActiveOrg=([^;]+)/)?.[1];
    if (!orgId) throw new Error('读不到 lastActiveOrg cookie，请确认已登录 claude.ai');
    return orgId;
  }

  function currentConversationId() {
    const id = window.location.pathname.split('/').pop();
    return id && id.length >= 20 && id.includes('-') ? id : null;
  }

  function fetchConversation(orgId, id) {
    return request(`/api/organizations/${orgId}/chat_conversations/${id}?tree=true&rendering_mode=messages&render_all_tools=true`, 'json');
  }

  // 对话列表接口的分页参数没有文档，这里按 limit/offset 翻页，并以“没有新条目”作为终止条件，
  // 这样无论接口忽略分页还是真的分页都不会死循环或漏项。
  async function listConversations(orgId) {
    const PAGE = 200;
    const seen = new Map();
    for (let offset = 0; ; offset += PAGE) {
      const page = await request(`/api/organizations/${orgId}/chat_conversations?limit=${PAGE}&offset=${offset}`, 'json');
      const items = Array.isArray(page) ? page : (page?.data || page?.conversations || []);
      let added = 0;
      for (const c of items) {
        if (c?.uuid && !seen.has(c.uuid)) { seen.set(c.uuid, c); added++; }
      }
      if (!added || items.length < PAGE) break;
    }
    return [...seen.values()];
  }

  // ───────────────────────── ZIP（仅存储，不压缩）─────────────────────────
  // claude.ai 的 CSP 不允许加载外部脚本，所以不用 JSZip，自己写一个最小的 ZIP 生成器。
  // 图片本身已是压缩格式，存储模式几乎不损失体积。

  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function makeZip(entries) {
    if (entries.length > 0xFFFF) throw new Error('文件数超过 65535，ZIP 无法容纳，请分批导出');
    const now = new Date();
    const dosTime = (now.getHours() << 11) | (now.getMinutes() << 5) | (now.getSeconds() >> 1);
    const dosDate = ((now.getFullYear() - 1980) << 9) | ((now.getMonth() + 1) << 5) | now.getDate();
    const local = [];
    const central = [];
    let offset = 0;
    let centralSize = 0;

    for (const { name, data } of entries) {
      const nameBytes = encoder.encode(name);
      const crc = crc32(data);

      const h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true);
      h.setUint16(4, 20, true);
      h.setUint16(6, 0x0800, true);          // 文件名为 UTF-8
      h.setUint16(8, 0, true);               // 存储
      h.setUint16(10, dosTime, true);
      h.setUint16(12, dosDate, true);
      h.setUint32(14, crc, true);
      h.setUint32(18, data.length, true);
      h.setUint32(22, data.length, true);
      h.setUint16(26, nameBytes.length, true);
      h.setUint16(28, 0, true);
      local.push(h, nameBytes, data);

      const c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true);
      c.setUint16(4, 20, true);
      c.setUint16(6, 20, true);
      c.setUint16(8, 0x0800, true);
      c.setUint16(10, 0, true);
      c.setUint16(12, dosTime, true);
      c.setUint16(14, dosDate, true);
      c.setUint32(16, crc, true);
      c.setUint32(20, data.length, true);
      c.setUint32(24, data.length, true);
      c.setUint16(28, nameBytes.length, true);
      c.setUint32(42, offset, true);         // 其余字段保持 0
      central.push(c, nameBytes);

      offset += 30 + nameBytes.length + data.length;
      centralSize += 46 + nameBytes.length;
      if (offset > 0xFFFFFFFF) throw new Error('导出内容超过 4 GB，请分批导出');
    }

    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, entries.length, true);
    end.setUint16(10, entries.length, true);
    end.setUint32(12, centralSize, true);
    end.setUint32(16, offset, true);
    return new Blob([...local, ...central, end], { type: 'application/zip' });
  }

  function download(blob, filename) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // 大文件立即 revoke 可能让下载中断，延后释放
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
  }

  // ───────────────────────── 附件下载 ─────────────────────────

  const EXT_BY_TYPE = {
    'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif',
    'image/svg+xml': 'svg', 'image/heic': 'heic', 'image/avif': 'avif', 'application/pdf': 'pdf'
  };

  function safeFileName(name) {
    return String(name || '')
      .replace(/[<>:"/\\|?*\u0000-\u001f#^[\]]/g, '_')
      .replace(/\s+/g, '_')
      .replace(/_{2,}/g, '_')
      .replace(/^[_.]+|_+$/g, '')
      .slice(0, 80);
  }

  function splitExt(name) {
    const i = name.lastIndexOf('.');
    return i > 0 ? [name.slice(0, i), name.slice(i + 1).toLowerCase()] : [name, ''];
  }

  function toBase64(bytes) {
    let bin = '';
    for (let i = 0; i < bytes.length; i += 0x8000) {
      bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(bin);
  }

  function messageFiles(m) {
    return (m.files && m.files.length ? m.files : m.files_v2) || [];
  }

  // 图片依次尝试预览图与缩略图地址；文档用 document_asset.url。
  function candidateUrls(file) {
    const urls = file.file_kind === 'image'
      ? [file.preview_url, file.preview_asset?.url, file.thumbnail_url, file.thumbnail_asset?.url]
      : file.file_kind === 'document' ? [file.document_asset?.url] : [];
    return [...new Set(urls.filter(u => typeof u === 'string' && u))];
  }

  // 下载一条对话里所有可下载的附件。返回 Map<file 对象, 本地引用>，
  // 引用是相对路径（zip 模式）或 data URI（base64 模式）；失败的文件不在 Map 里，渲染时退回原链接。
  async function downloadFiles(ordered, slug, zipEntries) {
    const refs = new Map();
    const byUuid = new Map();
    let n = 0;
    for (const m of ordered) {
      for (const file of messageFiles(m)) {
        if (file.file_kind !== 'image' && !(file.file_kind === 'document' && OPTS.documents)) continue;
        if (file.uuid && byUuid.has(file.uuid)) { refs.set(file, byUuid.get(file.uuid)); continue; }
        const urls = candidateUrls(file);
        if (!urls.length) continue;

        let got = null;
        for (const u of urls) {
          try {
            const r = await request(u, 'binary');
            // 拿到 HTML/JSON 说明不是文件本体（例如被重定向到了登录页）
            if (r.bytes.length && !/^(text\/html|application\/json)$/.test(r.type)) { got = r; break; }
          } catch (e) {
            console.debug('[claude-export]', e.message);
          }
        }
        const name = file.file_name || 'file';
        if (!got) { warn(`附件下载失败，保留原链接：${name}`); continue; }

        const [base, origExt] = splitExt(name);
        const ext = EXT_BY_TYPE[got.type] || origExt || 'bin';
        let ref;
        if (OPTS.images === 'base64' && file.file_kind === 'image') {
          ref = `data:${got.type || 'image/' + ext};base64,${toBase64(got.bytes)}`;
        } else {
          n++;
          const fname = `${String(n).padStart(3, '0')}-${safeFileName(base) || 'file'}.${ext}`;
          const path = `${OPTS.attachmentsDir}/${slug}/${fname}`;
          zipEntries.push({ name: path, data: got.bytes });
          ref = path.split('/').map(encodeURIComponent).join('/');
        }
        refs.set(file, ref);
        if (file.uuid) byUuid.set(file.uuid, ref);
      }
    }
    return refs;
  }

  // ───────────────────────── Markdown 渲染（沿用上游逻辑）─────────────────────────

  function formatTimestamp(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return null;
    return date.toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit'
    });
  }

  function formatBytes(n) {
    if (n == null || isNaN(n)) return null;
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  }

  // 沿当前分支（current_leaf_message_uuid → parent_message_uuid）还原屏幕上看到的顺序。
  function orderMessages(data) {
    const all = data?.chat_messages || [];
    if (!all.length) return [];
    const byUuid = new Map(all.map(m => [m.uuid, m]));
    const leaf = data.current_leaf_message_uuid;
    if (leaf && byUuid.has(leaf)) {
      const path = [];
      const seen = new Set();
      let cur = byUuid.get(leaf);
      while (cur && !seen.has(cur.uuid)) {
        seen.add(cur.uuid);
        path.push(cur);
        cur = cur.parent_message_uuid ? byUuid.get(cur.parent_message_uuid) : null;
      }
      if (path.length) return path.reverse();
    }
    warn(`「${data.name || '未命名'}」无法确定当前分支，按 index 排序，分支对话可能不准确`);
    return [...all].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  }

  function describeAttachments(m, refs) {
    const toAbsolute = (u) => {
      if (!u || typeof u !== 'string') return null;
      try { return new URL(u, 'https://claude.ai').href; } catch { return null; }
    };
    const meta = (...bits) => bits.filter(Boolean).join(' · ');
    const parts = [];

    for (const file of messageFiles(m)) {
      const name = file.file_name || 'file';
      const local = refs.get(file);
      if (file.file_kind === 'image') {
        const url = local || toAbsolute(candidateUrls(file)[0]);
        const label = `**Attachment: ${meta(name, 'image')}**`;
        parts.push(url ? `${label}\n\n![${name.replace(/[[\]]/g, '')}](${url})` : label);
      } else if (file.file_kind === 'document') {
        const url = local || toAbsolute(file.document_asset?.url);
        const pages = file.document_asset?.page_count;
        const info = meta('document', pages ? `${pages} page${pages === 1 ? '' : 's'}` : null);
        parts.push(`**Attachment: ${meta(url ? `[${name}](${url})` : name, info)}**`);
      } else {
        parts.push(`**Attachment: ${meta(name, file.file_kind, formatBytes(file.size_bytes))}**`);
      }
    }

    for (const attachment of (m.attachments || [])) {
      const name = attachment.file_name || attachment.name || 'attachment';
      const info = meta(attachment.file_type, formatBytes(attachment.file_size));
      const content = typeof attachment.extracted_content === 'string' ? attachment.extracted_content.trim() : '';
      const lines = [`**Attachment: ${meta(name, info)}**`];
      if (content) lines.push('', ...content.split('\n'));
      parts.push(lines.map(line => (line ? `> ${line}` : '>')).join('\n'));
    }
    return parts.join('\n\n');
  }

  // artifacts 工具有修订模型：create/rewrite 带全文，update 是 old_str→new_str 的差量。
  // 按顺序折叠出最终版本，只在最后一次编辑处输出一次。
  function collectArtifacts(ordered) {
    const artifacts = new Map();
    for (const m of ordered) {
      for (const block of (m.content || [])) {
        if (block.type !== 'tool_use' || block.name !== 'artifacts') continue;
        const input = block.input || {};
        const id = input.id || '__artifact__';
        let a = artifacts.get(id);
        if (!a) { a = { content: '' }; artifacts.set(id, a); }
        if (input.command === 'update') {
          if (typeof input.old_str === 'string' && typeof input.new_str === 'string') {
            if (a.content.indexOf(input.old_str) === -1) {
              warn(`Artifact「${a.title || id}」有一次更新无法应用，内容可能不完整`);
            } else {
              // 必须用函数替换：字符串替换会把 new_str 里的 $& 等当成替换模式
              a.content = a.content.replace(input.old_str, () => input.new_str);
            }
          }
        } else if (typeof input.content === 'string') {
          a.content = input.content;
        }
        if (input.title) a.title = input.title;
        if (input.type) a.type = input.type;
        if (input.language) a.language = input.language;
        a.lastVersionUuid = input.version_uuid;
      }
    }
    return artifacts;
  }

  function renderToolUse(block, artifacts) {
    const input = block.input || {};
    const name = block.name || '';
    const fenceFor = (src) => '`'.repeat(Math.max(3, ...(src.match(/`+/g) || []).map(s => s.length + 1)));
    const codeBlock = (label, source, lang) => {
      const fence = fenceFor(source);
      return `**${label}**\n\n${fence}${lang || ''}\n${source}\n${fence}`;
    };

    if (name === 'artifacts') {
      const a = artifacts.get(input.id || '__artifact__');
      if (!a || input.version_uuid !== a.lastVersionUuid || !a.content) return '';
      const TYPE = {
        'application/vnd.ant.react': { lang: 'jsx', label: 'React' },
        'text/html': { lang: 'html', label: 'HTML' },
        'image/svg+xml': { lang: 'svg', label: 'SVG' },
        'application/vnd.ant.mermaid': { lang: 'mermaid', label: 'Mermaid' },
        'text/markdown': { lang: 'markdown', label: 'Markdown' },
        'application/vnd.ant.code': { lang: a.language || '', label: a.language || 'Code' }
      };
      const t = TYPE[a.type] || { lang: a.language || '', label: a.language || '' };
      return codeBlock(`Artifact: ${a.title || 'untitled'}${t.label ? ` · ${t.label}` : ''}`, a.content, t.lang);
    }

    if (name === 'create_file' && typeof input.file_text === 'string' && input.file_text) {
      const file = String(input.path || 'file').split('/').pop();
      const ext = file.includes('.') ? file.split('.').pop().toLowerCase() : '';
      const EXT_LANG = {
        py: 'python', js: 'javascript', jsx: 'jsx', ts: 'typescript', tsx: 'tsx',
        md: 'markdown', html: 'html', css: 'css', json: 'json', sh: 'bash',
        yml: 'yaml', yaml: 'yaml', sql: 'sql', java: 'java', rb: 'ruby', go: 'go',
        rs: 'rust', c: 'c', cpp: 'cpp', txt: ''
      };
      return codeBlock(`File: ${file}`, input.file_text, EXT_LANG[ext] ?? '');
    }

    if (name === 'visualize:show_widget' && typeof input.widget_code === 'string' && input.widget_code) {
      return codeBlock(`Widget: ${input.title || 'untitled'}`, input.widget_code, 'jsx');
    }
    return '';
  }

  function yamlString(value) {
    return '"' + String(value ?? '').replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  }

  function incompleteNote(m) {
    if (m.truncated) return '> **Truncated:** the message was truncated in the source data and may be incomplete.';
    if (m.stop_reason === 'user_canceled') return '> **Interrupted:** this response was stopped before Claude finished.';
    return '';
  }

  function buildMarkdown(data, ordered, refs, source) {
    const artifacts = collectArtifacts(ordered);
    const title = data.name?.trim() || 'Claude conversation';
    const fm = ['---', `title: ${yamlString(title)}`, `source: ${yamlString(source)}`];
    if (data.model) fm.push(`model: ${yamlString(data.model)}`);
    if (data.created_at) fm.push(`created: ${String(data.created_at).slice(0, 10)}`);
    fm.push(`exported: ${new Date().toISOString().slice(0, 10)}`, '---', '');

    let markdown = fm.join('\n') + '\n';
    let count = 0;
    for (const m of ordered) {
      const parts = [];
      for (const block of (m.content || [])) {
        if (block.type === 'text' && typeof block.text === 'string') parts.push(block.text.trim());
        else if (block.type === 'tool_use') parts.push(renderToolUse(block, artifacts));
      }
      let body = [describeAttachments(m, refs), ...parts].filter(Boolean).join('\n\n').trim();
      if (!body) continue;
      const note = incompleteNote(m);
      if (note) body += `\n\n${note}`;
      const who = m.sender === 'human' ? 'Human' : 'Claude';
      const ts = formatTimestamp(m.created_at);
      markdown += `${ts ? `# ${who} — ${ts}` : `# ${who}`}\n\n${body}\n\n`;
      count++;
    }
    return { markdown, count };
  }

  function sanitizeTitle(title) {
    return String(title || '')
      .replace(/[<>:"/\\|?*#^[\]\u0000-\u001f]/g, '_')
      .replace(/\s+/g, '_')
      .replace(/_{2,}/g, '_')
      .replace(/^[_.]+|_+$/g, '')
      .toLowerCase()
      .substring(0, 100);
  }

  function slugFor(data) {
    const t = data?.name?.trim();
    return (t && t !== 'New conversation' && sanitizeTitle(t)) || 'claude_conversation';
  }

  // 导出一条对话：附件写进 zipEntries，Markdown 作为返回值。
  async function exportConversation(data, slug, zipEntries) {
    if (!data || !Array.isArray(data.chat_messages)) {
      throw new Error('接口返回里没有 chat_messages，接口格式可能已变化');
    }
    const ordered = orderMessages(data);
    const refs = await downloadFiles(ordered, slug, zipEntries);
    const source = `${window.location.origin}/chat/${data.uuid || ''}`;
    const { markdown, count } = buildMarkdown(data, ordered, refs, source);
    return { markdown, count, attachments: refs.size };
  }

  // ───────────────────────── 状态框 ─────────────────────────

  if (typeof window.__claudeExportDispose === 'function') {
    try { window.__claudeExportDispose(); } catch (_) { /* 上一次的状态框已不存在 */ }
  }
  const box = document.createElement('div');
  box.setAttribute('role', 'status');
  box.style.cssText = `
    position: fixed; top: 10px; right: 10px; z-index: 10000;
    background: #2196F3; color: #1a1a1a; padding: 10px 15px;
    border-radius: 5px; font-family: monospace; font-size: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3); max-width: 320px;
    overflow-wrap: anywhere; cursor: pointer; white-space: pre-line;
  `;
  const dispose = () => {
    if (document.body.contains(box)) document.body.removeChild(box);
    if (window.__claudeExportDispose === dispose) delete window.__claudeExportDispose;
  };
  box.addEventListener('click', dispose);
  window.__claudeExportDispose = dispose;
  document.body.appendChild(box);
  const status = (text, color) => { box.textContent = text; if (color) box.style.background = color; };

  function finish(summary) {
    const clean = warnings.length === 0;
    status(`${clean ? '✅' : '⚠️'} ${summary}${clean ? '' : `\n${warnings.length} 条警告，详见控制台`}\n（点击关闭）`,
      clean ? '#4CAF50' : '#ff9800');
  }

  // ───────────────────────── 主流程 ─────────────────────────

  async function exportSingle(orgId, id) {
    status('正在获取对话…');
    const data = await fetchConversation(orgId, id);
    data.uuid = data.uuid || id;
    const slug = slugFor(data);
    const entries = [];
    status('正在下载附件…');
    const { markdown, count, attachments } = await exportConversation(data, slug, entries);
    if (!count) throw new Error('这个对话里没有可导出的内容');

    if (entries.length) {
      entries.unshift({ name: `${slug}.md`, data: encoder.encode(markdown) });
      download(makeZip(entries), `${slug}.zip`);
      finish(`已导出 ${count} 条消息、${attachments} 个附件：${slug}.zip`);
    } else {
      download(new Blob([markdown], { type: 'text/markdown' }), `${slug}.md`);
      finish(`已导出 ${count} 条消息${attachments ? `（${attachments} 张图片已内嵌）` : ''}：${slug}.md`);
    }
  }

  async function exportAll(orgId) {
    status('正在获取对话列表…');
    const list = await listConversations(orgId);
    if (!list.length) throw new Error('没有找到任何对话');
    if (!window.confirm(`将导出全部 ${list.length} 个对话（含附件），可能需要几分钟，期间请保持此页面打开。继续吗？`)) {
      dispose();
      return;
    }

    const entries = [];
    const usedSlugs = new Set();
    let ok = 0;
    let files = 0;
    for (let i = 0; i < list.length; i++) {
      const item = list[i];
      status(`导出中 ${i + 1}/${list.length}\n${item.name || item.uuid}`);
      try {
        const data = await fetchConversation(orgId, item.uuid);
        data.uuid = data.uuid || item.uuid;
        const date = String(data.created_at || item.created_at || '').slice(0, 10);
        const base = `${date ? date + '_' : ''}${slugFor(data)}`;
        let slug = base;
        for (let k = 2; usedSlugs.has(slug); k++) slug = `${base}-${k}`;
        usedSlugs.add(slug);

        const { markdown, count, attachments } = await exportConversation(data, slug, entries);
        if (count) {
          entries.push({ name: `${slug}.md`, data: encoder.encode(markdown) });
          ok++;
          files += attachments;
        }
      } catch (e) {
        warn(`跳过「${item.name || item.uuid}」：${e.message}`);
      }
      if (OPTS.delayMs) await sleep(OPTS.delayMs);
    }

    status('正在打包…');
    const filename = `claude-export-${new Date().toISOString().slice(0, 10)}.zip`;
    download(makeZip(entries), filename);
    finish(`已导出 ${ok}/${list.length} 个对话、${files} 个附件：${filename}`);
  }

  (async () => {
    try {
      const orgId = getOrgId();
      const id = currentConversationId();
      const mode = OPTS.mode === 'auto' ? (id ? 'single' : 'all') : OPTS.mode;
      if (mode === 'single') {
        if (!id) throw new Error('当前页面不是具体的对话，请先打开一个对话');
        await exportSingle(orgId, id);
      } else {
        await exportAll(orgId);
      }
    } catch (e) {
      box.setAttribute('role', 'alert');
      status(`出错：${e.message}\n（点击关闭）`, '#f44336');
      console.error('[claude-export]', e);
    }
  })();
})();
