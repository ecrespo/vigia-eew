// ── SISTEMA VISUAL — Vigía-eew · definido una vez, usado en todo el deck ──
// Regla dura: los colores de severidad SOLO indican severidad. El acento nunca los usa.
const D = {
  // Dominante (~65% del peso visual): fondos oscuros de portada, secciones y cierre
  dark:    "1B2028",
  darkAlt: "2E3744",   // tarjetas sobre oscuro
  // Soporte claro: slides de contenido
  light:   "EEF1F5",
  card:    "FFFFFF",
  ink:     "1B2028",   // texto sobre claro
  inkSoft: "5A6473",   // texto secundario sobre claro
  onDark:  "F2F5F8",   // texto sobre oscuro
  onDarkSoft: "9AA6B5",
  // Acento del motivo — turquesa. NO es un color de severidad.
  accent:  "00B4A6",
  accentSoft: "1F6F6A",
  // Semánticos de SEVERIDAD — uso exclusivo
  sev: { p1: "C0392B", p2: "E8A33D", ok: "27AE60", na: "8892A6" },
  // Tipografía: ambas de la lista segura (render fiel en QA + presentes en Office)
  fontH: "Cambria",
  fontB: "Calibri",
};

// Motivo visual: anillos concéntricos (eco del ícono de bandeja del propio producto:
// "círculo + ondas concéntricas"). Se repite en TODAS las slides, esquina inferior derecha.
function motif(slide, pptx, onDark) {
  const col = onDark ? D.accent : D.accent;
  const trans = onDark ? [78, 86, 92] : [86, 91, 95];
  [[2.7, 78], [4.0, 86], [5.4, 92]].forEach(([d, t], i) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: 13.33 - d / 2, y: 7.5 - d / 2, w: d, h: d,
      fill: { type: "solid", color: col, transparency: t },
      line: { color: col, width: 1, transparency: Math.max(0, t - 30) },
    });
  });
}

function titleSlide(slide, pptx, text, sub) {
  slide.background = { color: D.dark };
  motif(slide, pptx, true);
  slide.addText(text, { x: 0.7, y: 2.15, w: 9.6, h: 1.5, fontSize: 44, bold: true,
    color: D.onDark, fontFace: D.fontH, isTextBox: true, margin: 0 });
  if (sub) slide.addText(sub, { x: 0.7, y: 3.75, w: 9.6, h: 1.1, fontSize: 16,
    color: D.onDarkSoft, fontFace: D.fontB, isTextBox: true, margin: 0 });
}

// Cabecera de slide de contenido: sin línea de acento bajo el título (prohibido),
// solo jerarquía tipográfica y aire.
function head(slide, pptx, kicker, title, dark) {
  slide.background = { color: dark ? D.dark : D.light };
  motif(slide, pptx, dark);
  if (kicker) slide.addText(kicker.toUpperCase(), { x: 0.7, y: 0.42, w: 11.9, h: 0.3,
    fontSize: 11, bold: true, color: D.accent, fontFace: D.fontB, charSpacing: 2,
    isTextBox: true, margin: 0 });
  slide.addText(title, { x: 0.7, y: 0.75, w: 11.9, h: 0.8, fontSize: 32, bold: true,
    color: dark ? D.onDark : D.ink, fontFace: D.fontH, isTextBox: true, margin: 0 });
}

module.exports = { D, motif, titleSlide, head };
