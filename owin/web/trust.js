/* The public AI data-use page: one card per endpoint, built from the same answers the app shows (/api/pack) and the
   dates Owin saw on each vendor page (/api/watch). Read-only; every vendor sentence is shown as fetched. */
(function () {
  "use strict";

  // Status codes from the API, and the words a reader sees for them
  const STATUS = {
    not_true: "Not true", stale: "Outdated", confirm: "Needs review", held: "Not stated", verified: "Verified",
  };
  const ORDER = ["not_true", "stale", "confirm", "held", "verified"];
  const QUESTION = {
    used_for_training: "Training use", retention_days: "Retention", zdr: "Zero data retention",
    region: "Processing region", third_party_access: "Who sees the data",
  };

  const $ = (id) => document.getElementById(id);

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function statusOf(cell) {
    if (cell.verdict === "contradicts") return "not_true";
    if (cell.stale) return "stale";
    if (cell.verdict === "confirm") return "confirm";
    if (cell.verdict === "held") return "held";
    return "verified";
  }

  function rowId(path, field) {
    return "row" + path.replace(/\W+/g, "-") + "-" + field;
  }

  function finding(answer, cell, status, vendor, company) {
    const li = el("li", "finding f-" + status);
    const a = el("a");
    a.href = "#" + rowId(cell.endpoint, answer.field);
    a.addEventListener("click", () => {
      const d = document.getElementById(rowId(cell.endpoint, answer.field));
      if (d) d.open = true;
    });
    const top = el("span", "finding-top");
    top.appendChild(tag(status));
    top.appendChild(el("span", "finding-path", cell.endpoint));
    a.appendChild(top);
    const text = status === "stale" && cell.list_source
      ? vendor + " changed its sub-processor list on " + cell.list_source.last_updated + ", after the company answered who sees the data."
      : (QUESTION[answer.field] || answer.question) + ": " + vendor + "'s page says " + plain(cell.value_label, company).replace(/^./, (c) => c.toLowerCase()) + ".";
    a.appendChild(el("span", "finding-text", text));
    li.appendChild(a);
    return li;
  }

  function tag(status) {
    return el("span", "tag s-" + status, STATUS[status]);
  }

  // The app speaks to the company ("your setting"); this page speaks to its buyers.
  function plain(label, company) {
    return String(label || "").replace(/\(your setting\)/g, "(" + company + " setting)")
      .replace(/\(not in your answer\)/g, "(not in the company's answer)");
  }

  function sourceLine(href, label, fetched, updated) {
    const box = el("div", "src");
    const line = el("p", "src-line", "Source: ");
    const a = el("a", "src-link", label + " page");
    a.href = href;
    a.rel = "noopener";
    line.appendChild(a);
    box.appendChild(line);
    const meta = el("p", "src-meta");
    meta.appendChild(el("span", null, "fetched " + (fetched || "date not recorded")));
    meta.appendChild(el("span", null, updated ? "Last updated on the page: " + updated : "The page shows no last-updated date"));
    box.appendChild(meta);
    return box;
  }

  function quote(text, who) {
    const fig = el("figure", "quote");
    const bq = el("blockquote", null, text);
    fig.appendChild(bq);
    fig.appendChild(el("figcaption", null, who));
    return fig;
  }

  function listChange(cell, vendor) {
    const box = el("div", "change");
    const ls = cell.list_source;
    box.appendChild(el("p", "change-h", "List updated " + ls.last_updated + " (was " + ls.was + ")"));
    const ul = el("ul", "change-list");
    (cell.list_evidence || []).forEach((e) => {
      const li = el("li");
      li.appendChild(el("strong", null, e.entity + " "));
      li.appendChild(el("span", "change-kind", e.change === "added" ? "added" : e.change === "removed" ? "removed" : "changed"));
      (e.rows || []).forEach((r) => {
        if (!r.value) return;
        const p = el("div", "change-row");
        p.appendChild(el("p", "change-key", r.key));
        if (r.was && r.was !== r.value) {
          const pair = el("div", "pair");
          const was = el("p", "was");
          was.appendChild(el("span", "pair-l", "Before"));
          was.appendChild(el("del", null, r.was));
          const now = el("p", "now");
          now.appendChild(el("span", "pair-l", "Now"));
          now.appendChild(el("ins", null, r.value));
          pair.appendChild(was);
          pair.appendChild(now);
          p.appendChild(pair);
        } else {
          p.appendChild(el("p", "change-val", r.value));
        }
        li.appendChild(p);
      });
      ul.appendChild(li);
    });
    box.appendChild(ul);
    box.appendChild(sourceLine(ls.url, ls.label, cell.fetched_at_local, ls.last_updated));
    return box;
  }

  function row(answer, cell, ctx) {
    const status = statusOf(cell);
    const d = el("details", "row s-" + status);
    d.id = rowId(cell.endpoint, answer.field);
    const s = el("summary");
    s.appendChild(el("span", "q", QUESTION[answer.field] || answer.question));
    s.appendChild(el("span", "a", plain(cell.value_label, ctx.company)));
    s.appendChild(tag(status));
    const chev = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chev.setAttribute("viewBox", "0 0 16 16");
    chev.setAttribute("aria-hidden", "true");
    chev.setAttribute("class", "chev");
    chev.innerHTML = '<path d="M4 6l4 4 4-4"/>';
    s.appendChild(chev);
    d.appendChild(s);

    const body = el("div", "detail");
    body.appendChild(el("p", "full-q", answer.question));
    const vendor = ctx.vendor;
    if (status === "not_true") {
      body.appendChild(el("p", "truth", "What " + vendor + " says: " + plain(cell.value_label, ctx.company) + "."));
    }
    if (cell.list_source) {
      body.appendChild(listChange(cell, vendor));
    } else {
      const q = cell.quote_display || cell.quote;
      if (q) {
        body.appendChild(quote(q, vendor + ", " + cell.source_label.replace(/^[^,]+,\s*/, "") + " page"));
      } else if (answer.field === "third_party_access") {
        body.appendChild(el("p", "none", "This endpoint sends data to " + vendor + "."));
      } else {
        body.appendChild(el("p", "none", "The vendor's page has no sentence on this."));
      }
      body.appendChild(sourceLine(cell.source_url, cell.source_label, cell.fetched_at_local, ctx.updated[cell.source_url]));
    }
    d.appendChild(body);
    return d;
  }

  function card(ep, rows, ctx) {
    const statuses = rows.map((r) => r.status);
    const worst = ORDER.find((o) => statuses.includes(o)) || "verified";
    const art = el("article", "card w-" + worst);
    art.setAttribute("aria-labelledby", "ep-" + ep.path.replace(/\W+/g, "-"));
    const head = el("header", "card-h");
    const h = el("h2", "path", ep.path);
    h.id = "ep-" + ep.path.replace(/\W+/g, "-");
    head.appendChild(h);
    head.appendChild(el("p", "purpose", ep.purpose));
    const dl = el("dl", "calls");
    [["Vendor", ep.provider_display], ["Feature", ep.label]].forEach(([k, v]) => {
      const div = el("div");
      div.appendChild(el("dt", null, k));
      div.appendChild(el("dd", null, v));
      dl.appendChild(div);
    });
    head.appendChild(dl);
    art.appendChild(head);
    const list = el("div", "rows");
    list.setAttribute("role", "list");
    rows.forEach((r) => {
      const n = row(r.answer, r.cell, { ...ctx, vendor: ep.provider_display });
      n.setAttribute("role", "listitem");
      list.appendChild(n);
    });
    art.appendChild(list);
    return art;
  }

  function render(pack, watch) {
    const company = String(pack.company || "Lumen Notes").replace(/\s+Inc\.?$/, "");
    $("company").textContent = company;
    document.title = company + " · AI data use, per endpoint";
    $("asof").textContent = "As of " + pack.as_of_local + " · checked against each vendor's own page";

    const updated = {};
    ((watch && watch.pages) || []).forEach((p) => { updated[p.url] = p.trusted_last_updated; });

    const counts = Object.fromEntries(ORDER.map((o) => [o, 0]));
    const cols = [$("col-a"), $("col-b")];
    cols.forEach((c) => { c.textContent = ""; });
    const found = $("findings");
    found.textContent = "";
    pack.stack.endpoints.forEach((ep, i) => {
      const rows = pack.answers.map((a) => {
        const cell = a.cells.find((c) => c.endpoint === ep.path);
        return cell && { answer: a, cell, status: statusOf(cell) };
      }).filter(Boolean);
      rows.forEach((r) => {
        counts[r.status] += 1;
        if (r.status === "not_true" || r.status === "stale") found.appendChild(finding(r.answer, r.cell, r.status, ep.provider_display, company));
      });
      const c = card(ep, rows, { company, updated });
      c.style.order = String(i);
      cols[i % 2].appendChild(c);
    });

    const tally = $("tally");
    tally.textContent = "";
    const total = ORDER.reduce((n, o) => n + counts[o], 0);
    const lead = el("li", "tally-total");
    lead.appendChild(el("strong", null, String(total)));
    lead.appendChild(el("span", null, " checks across " + pack.stack.endpoints.length + " endpoints"));
    tally.appendChild(lead);
    ORDER.filter((o) => counts[o]).forEach((o) => {
      const li = el("li", "tally-item");
      li.appendChild(el("strong", null, String(counts[o])));
      li.appendChild(tag(o));
      tally.appendChild(li);
    });
  }

  function fail() {
    const f = document.querySelector(".findings");
    if (f) f.hidden = true;
    $("asof").textContent = "The vendor pages could not be loaded. Reload the page to try again.";
  }

  Promise.all([
    fetch("/api/pack").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch("/api/watch").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]).then(([pack, watch]) => render(pack, watch)).catch(fail);
})();
