// Hover details for the trend charts: point at a year, or focus the chart and
// use the arrow keys. The tooltip shows the newest year until then, and goes
// back to it afterwards. Every value is also in the table under the chart.

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
    const moves = { ArrowLeft: active - 1, ArrowRight: active + 1, Home: 0, End: hits.length - 1 };
    if (!(event.key in moves)) return;
    event.preventDefault();
    show(Math.min(hits.length - 1, Math.max(0, moves[event.key])));
  });
}

document.querySelectorAll("[data-chart]").forEach(setUpChart);
