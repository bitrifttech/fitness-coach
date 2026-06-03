/* markdown.js — render coach prose as sanitized HTML from Markdown. */
(function () {
  "use strict";

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderMarkdown(text) {
    if (!text) return "";
    if (typeof marked === "undefined") return escapeHtml(text);
    const raw = marked.parse(String(text), { breaks: true, gfm: true });
    if (typeof DOMPurify !== "undefined") return DOMPurify.sanitize(raw);
    return raw;
  }

  window.renderMarkdown = renderMarkdown;
})();
