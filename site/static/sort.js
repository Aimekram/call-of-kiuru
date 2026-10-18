// Click a column heading to sort its table. Without JavaScript the tables
// simply stay in the order they were built in.

// The value a cell sorts by: its data-value if it has one, else its text.
// Numeric columns give a number, or NaN for an empty cell.
function sortKey(raw, numeric) {
  if (!numeric) return raw;
  return raw === "" ? NaN : Number(raw);
}

// Order of two keys. Empty numeric cells go last whichever way the column
// is sorted.
function compareKeys(x, y, numeric, descending) {
  if (numeric) {
    if (Number.isNaN(x)) return Number.isNaN(y) ? 0 : 1;
    if (Number.isNaN(y)) return -1;
  }
  const order = numeric ? x - y : String(x).localeCompare(String(y));
  return descending ? -order : order;
}

function makeSortable(table) {
  const body = table.tBodies[0];
  const headings = Array.from(table.querySelectorAll("thead th"));
  headings.forEach((heading, column) => {
    const button = document.createElement("button");
    button.type = "button";
    // The heading's text goes in a label that carries the sort arrow; any
    // small print (such as "rounded") follows on its own line.
    const label = document.createElement("span");
    label.className = "label";
    for (const node of Array.from(heading.childNodes)) {
      if (node.nodeName !== "SMALL") label.append(node);
    }
    button.append(label, ...heading.childNodes);
    heading.append(button);

    button.addEventListener("click", () => {
      const descending = heading.getAttribute("aria-sort") === "ascending";
      const numeric = heading.dataset.sort === "number";
      const key = (row) => {
        const cell = row.cells[column];
        return sortKey(cell.dataset.value ?? cell.textContent.trim(), numeric);
      };
      const rows = Array.from(body.rows).sort(
        (a, b) => compareKeys(key(a), key(b), numeric, descending));
      headings.forEach((other) => other.removeAttribute("aria-sort"));
      heading.setAttribute("aria-sort", descending ? "descending" : "ascending");
      body.append(...rows);
    });
  });
}

if (typeof document !== "undefined") {
  document.querySelectorAll("table.sortable").forEach(makeSortable);
}
if (typeof module !== "undefined") {
  module.exports = { sortKey, compareKeys };
}
