// Trend charts: point at a year, or focus and use the arrow keys. The newest
// year shows otherwise. Every value is also in the table below.
function setUpChart(chart) {
  const hits = Array.from(chart.querySelectorAll(".hit"));
  const bars = Array.from(chart.querySelectorAll(".bar"));
  const tip = chart.querySelector(".chart-tip");
  const newest = hits.length - 1;
  let active = newest;

  function show(i) {
    const hit = hits[i];
    active = i;
    bars.forEach((bar, j) => bar.classList.toggle("active", j === i));

    const value = document.createElement("strong");
    value.textContent = hit.dataset.tip;
    const when = document.createElement("span");
    when.textContent = `${hit.dataset.year} · ${hit.dataset.date}`;
    const key = document.createElement("i");
    key.className = hit.dataset.key;
    tip.replaceChildren(key, value, when);

    const x = Number(hit.dataset.x);
    tip.style.setProperty("--x", x);
    tip.dataset.edge = x < 15 ? "start" : x > 85 ? "end" : "";
  }

  chart.addEventListener("pointermove", (event) => {
    const hit = event.target.closest(".hit");
    if (hit) show(Number(hit.dataset.i));
  });
  chart.addEventListener("pointerleave", () => {
    if (document.activeElement !== chart) show(newest);
  });
  chart.addEventListener("blur", () => show(newest));
  chart.addEventListener("keydown", (event) => {
    const moves = {
      ArrowLeft: active - 1,
      ArrowRight: active + 1,
      Home: 0,
      End: hits.length - 1,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    show(Math.min(hits.length - 1, Math.max(0, moves[event.key])));
  });
}

document.querySelectorAll("[data-chart]").forEach(setUpChart);

// Model-against-observed charts: no year marked until pointed at or focused.
function setUpCheck(chart) {
  const hits = Array.from(chart.querySelectorAll(".hit"));
  const tip = chart.querySelector(".chart-tip");
  const observed = chart.querySelector(".dot.observed");
  const model = chart.querySelector(".dot.model");
  const newest = hits.length - 1;
  let active = null;

  function row(key, label, date) {
    const mark = document.createElement("i");
    mark.className = key;
    const text = document.createElement("span");
    text.textContent = `${label} ${date}`;
    return [mark, text];
  }

  function show(i) {
    const hit = hits[i];
    active = i;
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = `${hit.dataset.year} · ${hit.dataset.n}`;
    tip.replaceChildren(
      ...row("observed", "Observed", hit.dataset.observed),
      ...row("model", "Model", hit.dataset.model),
      when,
    );
    const x = Number(hit.dataset.x);
    chart.style.setProperty("--x", x);
    observed.style.top = `${hit.dataset.observedTop}px`;
    model.style.top = `${hit.dataset.modelTop}px`;
    tip.dataset.edge = x < 20 ? "start" : x > 80 ? "end" : "";
    chart.dataset.active = "";
  }

  function hide() {
    active = null;
    delete chart.dataset.active;
  }

  chart.addEventListener("pointermove", (event) => {
    const hit = event.target.closest(".hit");
    if (hit) show(Number(hit.dataset.i));
  });
  chart.addEventListener("pointerleave", () => {
    if (document.activeElement !== chart) hide();
  });
  chart.addEventListener("focus", () => {
    if (active === null) show(newest);
  });
  chart.addEventListener("blur", hide);
  chart.addEventListener("keydown", (event) => {
    const current = active === null ? newest : active;
    const moves = {
      ArrowLeft: current - 1,
      ArrowRight: current + 1,
      Home: 0,
      End: newest,
    };
    if (!(event.key in moves)) return;
    event.preventDefault();
    show(Math.min(newest, Math.max(0, moves[event.key])));
  });
}

document.querySelectorAll("[data-check]").forEach(setUpCheck);
