// 导出包解析：把 ChatGPT / Claude 导出的对话转换成入库格式。
// 浏览器（导入页）和 Node（测试）共用。不做任何网络请求。
(function (root) {
  "use strict";

  // 方案 A：你的消息存全文；AI 回答只存开头这么多字，全文留在原始导出包里
  const ASSISTANT_KEEP_CHARS = 500;

  function truncateAssistant(role, text) {
    if (role !== "assistant" || text.length <= ASSISTANT_KEEP_CHARS) return text;
    return text.slice(0, ASSISTANT_KEEP_CHARS) + "…〔截断，全文见原对话〕";
  }

  function isoFromEpoch(v) {
    if (v === null || v === undefined || v === "") return null;
    const n = Number(v);
    if (!Number.isFinite(n)) return null;
    return new Date(n * 1000).toISOString();
  }

  // ---------------- 来源识别 ----------------
  function detectSource(items) {
    for (const it of items.slice(0, 20)) {
      if (it && typeof it === "object") {
        if ("mapping" in it) return "chatgpt";
        if ("chat_messages" in it || ("uuid" in it && ("name" in it || "summary" in it))) return "claude";
      }
    }
    return null;
  }

  // 把任意解析结果展开成"对话对象"数组
  function flattenItems(data) {
    if (Array.isArray(data)) return data;
    if (data && typeof data === "object") {
      if (Array.isArray(data.conversations)) return data.conversations;
      if ("chat_messages" in data || "mapping" in data) return [data];
    }
    return [];
  }

  // ---------------- ChatGPT ----------------
  const SKIP_CONTENT_TYPES = new Set(["user_editable_context", "thoughts", "reasoning_recap", "model_editable_context"]);

  function chatgptText(message) {
    const content = message.content || {};
    if (SKIP_CONTENT_TYPES.has(content.content_type)) return "";
    const out = [];
    if (Array.isArray(content.parts)) {
      for (const p of content.parts) {
        if (typeof p === "string") out.push(p);
        else if (p && typeof p === "object") {
          if (typeof p.text === "string") out.push(p.text);
          else if (p.content_type === "image_asset_pointer") out.push("[图片]");
        }
      }
    }
    if (!out.length && typeof content.text === "string") out.push(content.text);
    if (!out.length && typeof content.result === "string") out.push(content.result);
    return out.filter(Boolean).join("\n").trim();
  }

  function convertChatgpt(conv) {
    const cid = conv.conversation_id || conv.id;
    const mapping = conv.mapping || {};
    if (!cid || !Object.keys(mapping).length) return null;

    let nodeId = conv.current_node;
    if (!(nodeId in mapping)) {
      let best = null, bestT = -1;
      for (const [k, n] of Object.entries(mapping)) {
        if (n.children && n.children.length) continue;
        const t = (n.message && n.message.create_time) || 0;
        if (t > bestT) { bestT = t; best = k; }
      }
      nodeId = best;
    }
    const chain = [], seen = new Set();
    while (nodeId && mapping[nodeId] && !seen.has(nodeId)) {
      seen.add(nodeId);
      chain.push(nodeId);
      nodeId = mapping[nodeId].parent;
    }
    chain.reverse();

    const messages = [];
    let prev = null;
    for (const nid of chain) {
      const msg = mapping[nid].message;
      if (!msg) continue;
      const meta = msg.metadata || {};
      if (meta.is_visually_hidden_from_conversation) continue;
      const role = (msg.author && msg.author.role) || "unknown";
      if (role === "system") continue;
      const text = chatgptText(msg);
      if (!text) continue;
      const id = msg.id || nid;
      messages.push({
        source_msg_id: id, parent_source_msg_id: prev, role,
        content: truncateAssistant(role, text),
        created_at: isoFromEpoch(msg.create_time), seq: messages.length, on_final_branch: true,
      });
      prev = id;
    }
    return {
      source_id: String(cid), title: conv.title || "",
      created_at: isoFromEpoch(conv.create_time),
      updated_at: isoFromEpoch(conv.update_time) || isoFromEpoch(conv.create_time),
      messages,
    };
  }

  // ---------------- Claude ----------------
  function claudeText(m) {
    const out = [];
    if (Array.isArray(m.content)) {
      for (const b of m.content) {
        if (b && b.type === "text" && typeof b.text === "string") out.push(b.text);
      }
    }
    if (!out.length && typeof m.text === "string") out.push(m.text);
    for (const key of ["attachments", "files"]) {
      for (const a of m[key] || []) {
        const name = a && (a.file_name || a.name);
        if (name) out.push(`[附件: ${name}]`);
      }
    }
    return out.filter(Boolean).join("\n").trim();
  }

  function convertClaude(conv) {
    const cid = conv.uuid;
    if (!cid) return null;
    let msgs = (conv.chat_messages || []).filter((m) => m && m.uuid);

    // 有分支信息时，只取通往最新一条消息的分支
    const byId = new Map(msgs.map((m) => [m.uuid, m]));
    if (msgs.some((m) => byId.has(m.parent_message_uuid))) {
      let leaf = msgs.reduce((a, b) => ((b.created_at || "") > (a.created_at || "") ? b : a), msgs[0]);
      const chain = [], seen = new Set();
      while (leaf && !seen.has(leaf.uuid)) {
        seen.add(leaf.uuid);
        chain.push(leaf);
        leaf = byId.get(leaf.parent_message_uuid);
      }
      msgs = chain.reverse();
    }

    const messages = [];
    let prev = null;
    for (const m of msgs) {
      const text = claudeText(m);
      if (!text) continue;
      const role = m.sender === "human" ? "user" : m.sender === "assistant" ? "assistant" : (m.sender || "unknown");
      messages.push({
        source_msg_id: m.uuid, parent_source_msg_id: prev, role,
        content: truncateAssistant(role, text),
        created_at: m.created_at || null, seq: messages.length, on_final_branch: true,
      });
      prev = m.uuid;
    }
    return {
      source_id: String(cid), title: conv.name || "",
      created_at: conv.created_at || null,
      updated_at: conv.updated_at || conv.created_at || null,
      messages,
    };
  }

  function convertAll(items) {
    const source = detectSource(items);
    if (!source) return { source: null, conversations: [] };
    const fn = source === "chatgpt" ? convertChatgpt : convertClaude;
    const conversations = [];
    for (const it of items) {
      if (!it || typeof it !== "object") continue;
      const c = fn(it);
      if (c) conversations.push(c);
    }
    return { source, conversations };
  }

  // 只上传新增或有变化的对话
  function pickChanged(conversations, known) {
    return conversations.filter((c) => {
      const old = known[c.source_id];
      if (!old || !c.updated_at) return true;
      return Math.abs(new Date(c.updated_at) - new Date(old)) > 1000;
    });
  }

  // 按大小分批
  function makeBatches(conversations, maxBytes, maxCount) {
    const enc = typeof TextEncoder !== "undefined" ? new TextEncoder() : null;
    const size = (o) => { const s = JSON.stringify(o); return enc ? enc.encode(s).length : s.length * 3; };
    const batches = [];
    let cur = [], bytes = 0;
    for (const c of conversations) {
      const s = size(c);
      if (cur.length && (bytes + s > maxBytes || cur.length >= maxCount)) { batches.push(cur); cur = []; bytes = 0; }
      cur.push(c);
      bytes += s;
    }
    if (cur.length) batches.push(cur);
    return batches;
  }

  const api = { flattenItems, detectSource, convertAll, convertChatgpt, convertClaude, pickChanged, makeBatches, ASSISTANT_KEEP_CHARS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MemConvert = api;
})(typeof window !== "undefined" ? window : globalThis);
