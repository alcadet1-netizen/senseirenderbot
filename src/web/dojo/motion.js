// Apply the saved preference before the stylesheet paints the loading screen.
(() => {
  let preference = "full";
  try { preference = localStorage.getItem("sensei_dojo_motion") || "full"; } catch {}
  const systemReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const reduced = preference === "off" || (preference === "auto" && systemReduced);
  document.documentElement.classList.toggle("motion-reduced", Boolean(reduced));
})();
