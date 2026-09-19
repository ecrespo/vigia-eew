const pptxgen = require("pptxgenjs");
const { D, motif, titleSlide, head } = require("./design");
const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";              // 13.33 x 7.5
pptx.author = "Auditoría vigia-eew";
pptx.title = "Vigía-eew · Evaluación de código, seguridad y contenedores";

const S = () => pptx.addSlide();
const card = (s, x, y, w, h, fill) => s.addShape(pptx.ShapeType.roundRect, {
  x, y, w, h, rectRadius: 0.08, fill: { color: fill || D.card },
  line: { color: fill || D.card, width: 0 },
  shadow: { type: "outer", angle: 90, blur: 6, offset: 1, color: "9AA6B5", opacity: 0.22 } });
const txt = (s, t, o) => s.addText(t, Object.assign({ isTextBox: true, margin: 0,
  valign: "top", fontFace: D.fontB, color: D.ink }, o));

/* 1 ─ Portada */
{ const s = S();
  titleSlide(s, pptx, "Vigía-eew", "Evaluación de código, seguridad y contenedores · 2026-09-06");
  txt(s, "Agente de alerta sísmica de escritorio · commit c3a2c29 (v0.6.0)",
    { x: 0.7, y: 4.75, w: 9.6, h: 0.4, fontSize: 13, color: D.onDarkSoft });
  txt(s, "94 artefactos de análisis · 5 etapas · un repositorio",
    { x: 0.7, y: 5.2, w: 9.6, h: 0.4, fontSize: 13, bold: true, color: D.accent });
  s.addNotes("Un solo repositorio conectado: no hay deck de síntesis porque no hay varios repos que sintetizar.");
}

/* 2 ─ Cómo leer este deck (sistema visual + leyenda de severidad) */
{ const s = S(); head(s, pptx, "Cómo leer este deck", "Los colores significan una sola cosa");
  const items = [["P1", "Crítico · explotable o pérdida de datos", D.sev.p1],
                 ["P2", "Debilita defensas", D.sev.p2],
                 ["OK / P3", "Sano, o calidad sin riesgo", D.sev.ok],
                 ["—", "No evaluado: falta herramienta, no falta hallazgo", D.sev.na]];
  items.forEach(([k, v, c], i) => {
    const y = 1.85 + i * 0.92;
    card(s, 0.7, y, 7.4, 0.74);
    s.addShape(pptx.ShapeType.ellipse, { x: 0.95, y: y + 0.17, w: 0.4, h: 0.4, fill: { color: c }, line: { color: c, width: 0 } });
    txt(s, k, { x: 1.5, y: y + 0.1, w: 1.5, h: 0.3, fontSize: 15, bold: true, color: c });
    txt(s, v, { x: 1.5, y: y + 0.38, w: 6.3, h: 0.3, fontSize: 12, color: D.inkSoft });
  });
  card(s, 8.5, 1.85, 4.1, 3.66, D.darkAlt);
  txt(s, "El acento turquesa", { x: 8.85, y: 2.12, w: 3.5, h: 0.32, fontSize: 15, bold: true, color: D.accent, fontFace: D.fontH });
  txt(s, "no indica severidad en ningún caso: marca navegación y énfasis.\n\nEl motivo de anillos concéntricos que se repite en cada slide es el propio ícono de bandeja del producto: un círculo con ondas.",
    { x: 8.85, y: 2.55, w: 3.45, h: 2.7, fontSize: 12.5, color: D.onDarkSoft, lineSpacing: 18 });
  s.addNotes("Regla del sistema visual: rojo/ámbar/verde SOLO para severidad. El turquesa es navegación.");
}

/* 3 ─ Qué se auditó */
{ const s = S(); head(s, pptx, "Alcance", "Cinco etapas, 94 artefactos, un repositorio");
  const st = [["1", "Capas de contexto", "CodeGraph · Graphify · lat.md", "17"],
              ["2", "Ingeniería inversa", "17 HU · 95 criterios · 157 casos", "29"],
              ["3", "Auditoría de código", "8 dimensiones con evidencia", "22"],
              ["4", "Arquitectura", "Grafo · git · 8 atributos · 3 ADR", "11"],
              ["5", "Especificación v2", "56 requisitos EARS · Analyze", "13"]];
  st.forEach(([n, t, d, c], i) => {
    const x = 0.7 + i * 2.46;
    card(s, x, 2.0, 2.26, 2.9);
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.85, y: 2.25, w: 0.56, h: 0.56, fill: { color: D.accent }, line: { color: D.accent, width: 0 } });
    txt(s, n, { x: x + 0.85, y: 2.36, w: 0.56, h: 0.34, fontSize: 17, bold: true, color: "FFFFFF", align: "center" });
    txt(s, t, { x: x + 0.18, y: 3.02, w: 1.9, h: 0.6, fontSize: 13.5, bold: true, align: "center", fontFace: D.fontH });
    txt(s, d, { x: x + 0.18, y: 3.66, w: 1.9, h: 0.85, fontSize: 10.5, color: D.inkSoft, align: "center", lineSpacing: 13 });
    txt(s, c + " docs", { x: x + 0.18, y: 4.5, w: 1.9, h: 0.3, fontSize: 10, bold: true, color: D.accentSoft, align: "center" });
  });
  txt(s, "Cada afirmación lleva su evidencia: 327 citas archivo:línea verificadas y 39 hashes de commit comprobados con git.",
    { x: 0.7, y: 5.3, w: 11.9, h: 0.5, fontSize: 13, color: D.inkSoft, italic: true });
  s.addNotes("94 archivos verificados contra el sistema de archivos, no contra lo reportado.");
}

/* 4 ─ El sistema en 30 segundos */
{ const s = S(); head(s, pptx, "El sistema", "Un proceso por máquina, cuatro redes sísmicas", true);
  const src = [["EMSC", "WebSocket · canal primario"], ["USGS", "REST · respaldo con cursor"],
               ["GEOFON", "REST · red independiente"], ["FUNVISIS", "REST · cobertura local"]];
  src.forEach(([n, d], i) => {
    const y = 2.25 + i * 0.66;
    card(s, 0.7, y, 3.5, 0.56, D.darkAlt);
    txt(s, n, { x: 0.95, y: y + 0.07, w: 2.2, h: 0.26, fontSize: 13, bold: true, color: D.accent });
    txt(s, d, { x: 0.95, y: y + 0.3, w: 3.0, h: 0.23, fontSize: 10.5, color: D.onDarkSoft });
  });
  card(s, 4.75, 2.25, 3.6, 2.55, D.darkAlt);
  txt(s, "Pipeline", { x: 5.05, y: 2.5, w: 3.0, h: 0.35, fontSize: 16, bold: true, color: D.onDark, fontFace: D.fontH });
  txt(s, "normalizar → filtrar → deduplicar\n\nUn solo contrato interno.\nFiltro antes que dedup:\ninvariante, no estilo.",
    { x: 5.05, y: 2.95, w: 3.05, h: 1.7, fontSize: 12, color: D.onDarkSoft, lineSpacing: 17 });
  card(s, 8.9, 2.25, 3.7, 2.55, D.darkAlt);
  txt(s, "Alerta no descartable", { x: 9.2, y: 2.5, w: 3.2, h: 0.35, fontSize: 16, bold: true, color: D.onDark, fontFace: D.fontH });
  txt(s, "Solo el acuse explícito la cierra.\n\nTres frontends: ventana Tk,\npanel de terminal, bandeja.",
    { x: 9.2, y: 2.95, w: 3.15, h: 1.7, fontSize: 12, color: D.onDarkSoft, lineSpacing: 17 });
  txt(s, "Sin servidor. Sin base de datos. Sin contenedores. Es software de escritorio.",
    { x: 0.7, y: 5.35, w: 11.9, h: 0.4, fontSize: 13.5, bold: true, color: D.accent });
  s.addNotes("Nivel 1 de C4 resumido. El detalle está en docs/ARQUITECTURA-C4.md.");
}

/* 5 ─ Scorecard */
{ const s = S(); head(s, pptx, "Auditoría de código", "Ocho dimensiones, cero hallazgos P1");
  const dims = [["DRY", "0,95 % duplicado", D.sev.ok], ["SOLID", "S y O en ámbar", D.sev.p2],
    ["Pruebas unitarias", "cobertura no medible aquí", D.sev.na], ["Pruebas integración", "sin separación formal", D.sev.p2],
    ["SAST", "0 HIGH sobre 3.565 LOC", D.sev.ok], ["SCA", "1 de 90 paquetes", D.sev.ok],
    ["Secretos", "0 en árbol e historia", D.sev.ok], ["Contenedores", "fuera de alcance", D.sev.na]];
  dims.forEach(([n, v, c], i) => {
    const x = 0.7 + (i % 4) * 3.07, y = 1.95 + Math.floor(i / 4) * 1.62;
    card(s, x, y, 2.85, 1.38);
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.25, y: y + 0.25, w: 0.3, h: 0.3, fill: { color: c }, line: { color: c, width: 0 } });
    txt(s, n, { x: x + 0.66, y: y + 0.24, w: 2.0, h: 0.34, fontSize: 12.5, bold: true, fontFace: D.fontH });
    txt(s, v, { x: x + 0.25, y: y + 0.72, w: 2.4, h: 0.5, fontSize: 11, color: D.inkSoft, lineSpacing: 13 });
  });
  card(s, 0.7, 5.3, 11.92, 1.05, D.dark);
  txt(s, "0 hallazgos P1  ·  5 P2  ·  8 P3", { x: 1.0, y: 5.5, w: 5.0, h: 0.4, fontSize: 20, bold: true, color: D.onDark, fontFace: D.fontH });
  txt(s, "Los cinco P2 son de gate, no de código. Todos de tamaño S.", { x: 6.2, y: 5.57, w: 6.1, h: 0.4, fontSize: 13, color: D.onDarkSoft });
  s.addNotes("Ninguna dimensión sin herramienta ejecutada recibe color: se marca 'no evaluado'.");
}

/* 6 ─ Seguridad: secretos y SAST */
{ const s = S(); head(s, pptx, "Seguridad · 1 de 2", "Secretos y análisis estático", true);
  const stats = [["0", "secretos en el árbol\nde trabajo"], ["0", "secretos en los 59 commits\nde todas las ramas"],
                 ["0", "hallazgos SAST de\nseveridad alta"]];
  stats.forEach(([n, l], i) => {
    const x = 0.7 + i * 4.07;
    card(s, x, 1.95, 3.75, 2.0, D.darkAlt);
    txt(s, n, { x: x + 0.3, y: 2.15, w: 3.15, h: 1.0, fontSize: 60, bold: true, color: D.sev.ok, fontFace: D.fontH });
    txt(s, l, { x: x + 0.3, y: 3.15, w: 3.15, h: 0.65, fontSize: 12, color: D.onDarkSoft, lineSpacing: 15 });
  });
  card(s, 0.7, 4.25, 11.92, 1.75, D.darkAlt);
  txt(s, "Lo que sí encontró la herramienta, y por qué se descartó", { x: 1.0, y: 4.45, w: 11.3, h: 0.35, fontSize: 15, bold: true, color: D.onDark, fontFace: D.fontH });
  txt(s, [
    { text: "Los 3 positivos del árbol son checksums SHA-256 de binarios pinneados en el workflow de seguridad y un id de ejemplo en documentación. ", options: { color: D.onDarkSoft } },
    { text: "Fijar los binarios por checksum es buena práctica, no fuga.", options: { color: D.accent, bold: true } },
  ], { x: 1.0, y: 4.85, w: 11.3, h: 0.9, fontSize: 12.5, lineSpacing: 17 });
  s.addNotes("Gitleaks no pudo ejecutarse (GitHub bloqueado); se sustituyó por detect-secrets sobre árbol e historia. Gap documentado.");
}

/* 7 ─ SCA: instalado vs declarado */
{ const s = S(); head(s, pptx, "Seguridad · 2 de 2", "Instalado está sano. Lo declarado, no.");
  card(s, 0.7, 1.95, 5.8, 3.15);
  s.addShape(pptx.ShapeType.ellipse, { x: 1.0, y: 2.2, w: 0.34, h: 0.34, fill: { color: D.sev.ok }, line: { color: D.sev.ok, width: 0 } });
  txt(s, "Lo que está instalado", { x: 1.45, y: 2.2, w: 4.6, h: 0.35, fontSize: 16, bold: true, fontFace: D.fontH });
  txt(s, "89 de 90 paquetes del lockfile sin ningún aviso.\n\nEl único afectado es pip 26.1.2 (CVE-2026-13346), dependencia de desarrollo que no viaja al usuario final.",
    { x: 1.0, y: 2.75, w: 5.2, h: 2.0, fontSize: 13, color: D.inkSoft, lineSpacing: 18 });
  card(s, 6.82, 1.95, 5.8, 3.15);
  s.addShape(pptx.ShapeType.ellipse, { x: 7.12, y: 2.2, w: 0.34, h: 0.34, fill: { color: D.sev.p1 }, line: { color: D.sev.p1, width: 0 } });
  txt(s, "Lo que el rango permite instalar", { x: 7.57, y: 2.2, w: 4.9, h: 0.35, fontSize: 16, bold: true, fontFace: D.fontH });
  txt(s, "Pillow>=10.0 admite versiones con 34 avisos conocidos.\n\nEl lockfile resuelve 12.3.0, que tiene cero. Pero el lockfile no está versionado: lo que protege al desarrollador no protege al usuario.",
    { x: 7.12, y: 2.75, w: 5.2, h: 2.1, fontSize: 13, color: D.inkSoft, lineSpacing: 18 });
  card(s, 0.7, 5.3, 11.92, 1.05, D.dark);
  txt(s, "Son dos preguntas distintas. La auditoría respondió la primera; esta revisión hizo la segunda.",
    { x: 1.0, y: 5.58, w: 11.3, h: 0.4, fontSize: 14, color: D.onDark, italic: true });
  s.addNotes("El informe SCA no estaba equivocado: su alcance era 'lo instalado'. El hallazgo nuevo vive en 'lo declarado'.");
}

/* 8 ─ Pillow: gráfico */
{ const s = S(); head(s, pptx, "El hallazgo P-02", "Avisos conocidos por versión de Pillow");
  s.addChart(pptx.ChartType.bar, [{ name: "Avisos en el feed de PyPI",
    labels: ["10.0.0", "11.0.0", "11.2.1", "12.0.0", "12.1.0", "12.2.0", "12.3.0"],
    values: [34, 33, 37, 37, 37, 25, 0] }], {
    x: 0.7, y: 1.9, w: 7.6, h: 3.9, barDir: "col",
    chartColors: [D.sev.p1], showTitle: false, showLegend: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: D.ink,
    dataLabelFontSize: 11, dataLabelFontFace: D.fontB,
    catAxisLabelColor: D.inkSoft, valAxisLabelColor: D.inkSoft,
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
    valGridLine: { color: "D8DEE6", size: 1 }, catGridLine: { style: "none" },
    valAxisMinVal: 0, valAxisMaxVal: 40, barGapWidthPct: 45 });
  card(s, 8.6, 1.9, 4.02, 3.9, D.darkAlt);
  txt(s, "12.3.0", { x: 8.9, y: 2.15, w: 3.4, h: 0.75, fontSize: 42, bold: true, color: D.accent, fontFace: D.fontH });
  txt(s, "es el primer release con cero avisos: el piso de seguridad real.\n\nEl rango declarado empieza en 10.0, veintitantos releases por debajo.",
    { x: 8.9, y: 2.95, w: 3.45, h: 1.7, fontSize: 12.5, color: D.onDarkSoft, lineSpacing: 17 });
  txt(s, "Acción:  Pillow>=12.3.0,<13", { x: 8.9, y: 4.85, w: 3.45, h: 0.6, fontSize: 13, bold: true, color: D.onDark, fontFace: D.fontB });
  txt(s, "Fuente: feed de avisos de PyPI, la misma que usa pip-audit -s pypi. No reporta severidad — por eso se cuentan avisos, no CVSS.",
    { x: 0.7, y: 5.95, w: 11.9, h: 0.45, fontSize: 11, color: D.inkSoft, italic: true });
  s.addNotes("Pillow entra al árbol por pystray, que lleva 1.085 días sin publicar.");
}

/* 9 ─ Runtime Python */
{ const s = S(); head(s, pptx, "Runtime", "El piso del proyecto ya no recibe correcciones", true);
  const rows = [["3.11", "security-only", "piso actual del proyecto", D.sev.p2],
                ["3.12", "security-only", "piso propuesto para la v2", D.sev.p2],
                ["3.13", "bugfix", "piso recomendado · soporte a 2029", D.sev.ok],
                ["3.14", "bugfix", "alternativa · soporte a 2030", D.sev.ok]];
  rows.forEach(([v, f, n, c], i) => {
    const y = 1.95 + i * 0.98;
    card(s, 0.7, y, 8.3, 0.82, D.darkAlt);
    txt(s, "Python " + v, { x: 1.0, y: y + 0.2, w: 1.9, h: 0.42, fontSize: 17, bold: true, color: D.onDark, fontFace: D.fontH });
    s.addShape(pptx.ShapeType.roundRect, { x: 3.0, y: y + 0.22, w: 1.75, h: 0.38, rectRadius: 0.06, fill: { color: c }, line: { color: c, width: 0 } });
    txt(s, f, { x: 3.0, y: y + 0.29, w: 1.75, h: 0.26, fontSize: 11, bold: true, color: "FFFFFF", align: "center" });
    txt(s, n, { x: 5.0, y: y + 0.27, w: 3.8, h: 0.3, fontSize: 12.5, color: D.onDarkSoft });
  });
  card(s, 9.3, 1.95, 3.32, 3.85, D.darkAlt);
  txt(s, "Inconsistencia\ndetectada", { x: 9.6, y: 2.2, w: 2.8, h: 0.75, fontSize: 16, bold: true, color: D.sev.p2, fontFace: D.fontH, lineSpacing: 20 });
  txt(s, "La constitución que se generó en el paso anterior fija Python ≥ 3.12.\n\nEse destino también está en security-only. Se anotó en vez de editarla: cambiarla exige enmienda con changelog.",
    { x: 9.6, y: 3.05, w: 2.75, h: 2.5, fontSize: 11.5, color: D.onDarkSoft, lineSpacing: 16 });
  s.addNotes("Fuente: guía oficial del desarrollador de Python, actualizada 2026-05-27.");
}

/* 10 ─ Contenedores */
{ const s = S(); head(s, pptx, "Contenedores", "El producto no. La fábrica sí.");
  card(s, 0.7, 1.95, 5.8, 3.5);
  s.addShape(pptx.ShapeType.ellipse, { x: 1.0, y: 2.2, w: 0.34, h: 0.34, fill: { color: D.sev.p1 }, line: { color: D.sev.p1, width: 0 } });
  txt(s, "No se contenariza el producto", { x: 1.45, y: 2.2, w: 4.8, h: 0.35, fontSize: 16, bold: true, fontFace: D.fontH });
  txt(s, "Necesita la sesión gráfica, el audio y el bus del usuario. Exponerlos desmonta el aislamiento que justifica el contenedor, para lograr algo que el paquete nativo ya hace mejor.\n\nEl repositorio tiene 0 Dockerfiles, y es correcto.",
    { x: 1.0, y: 2.75, w: 5.2, h: 2.45, fontSize: 12.5, color: D.inkSoft, lineSpacing: 17 });
  card(s, 6.82, 1.95, 5.8, 3.5);
  s.addShape(pptx.ShapeType.ellipse, { x: 7.12, y: 2.2, w: 0.34, h: 0.34, fill: { color: D.sev.ok }, line: { color: D.sev.ok, width: 0 } });
  txt(s, "Sí se contenariza el build de Linux", { x: 7.57, y: 2.2, w: 4.9, h: 0.35, fontSize: 16, bold: true, fontFace: D.fontH });
  txt(s, "El binario de PyInstaller enlaza contra la glibc de la máquina que lo construye, y hoy se construye en ubuntu-latest.\n\nCuando GitHub mueve qué es \"latest\", el binario eleva su glibc mínima en silencio y deja de arrancar en distros más antiguas.",
    { x: 7.12, y: 2.75, w: 5.2, h: 2.45, fontSize: 12.5, color: D.inkSoft, lineSpacing: 17 });
  card(s, 0.7, 5.65, 11.92, 0.95, D.dark);
  txt(s, "Fijar la imagen base convierte la glibc mínima en una decisión declarada, no en un efecto colateral del runner.",
    { x: 1.0, y: 5.9, w: 11.3, h: 0.4, fontSize: 13.5, color: D.onDark, italic: true });
  s.addNotes("Riesgo de disponibilidad no reportado en etapas anteriores; aparece al cruzar empaquetado con CI.");
}

/* 11 ─ Los 5 P2 */
{ const s = S(); head(s, pptx, "Calidad de código", "Los cinco P2 son de gate, no de código");
  const p2 = [["1", "La cobertura se mide pero no se exige", "La CI genera coverage.xml; no existe --cov-fail-under"],
              ["2", "ruff format fuera del gate", "19 archivos sin formatear con la versión que fija el lockfile"],
              ["3", "Sin separación unitarias / integración", "Las 5 pruebas e2e corren en el mismo lote"],
              ["4", "DRY y complejidad sin gate", "Solo se detectan si alguien audita a mano"],
              ["5", "CVE en pip, alcanzable solo en desarrollo", "Transitiva de pip-audit; no viaja al usuario"]];
  p2.forEach(([n, t, d], i) => {
    const y = 1.85 + i * 0.93;
    card(s, 0.7, y, 11.92, 0.8);
    s.addShape(pptx.ShapeType.ellipse, { x: 0.95, y: y + 0.2, w: 0.4, h: 0.4, fill: { color: D.sev.p2 }, line: { color: D.sev.p2, width: 0 } });
    txt(s, n, { x: 0.95, y: y + 0.28, w: 0.4, h: 0.26, fontSize: 13, bold: true, color: "FFFFFF", align: "center" });
    txt(s, t, { x: 1.55, y: y + 0.13, w: 5.6, h: 0.3, fontSize: 13.5, bold: true, fontFace: D.fontH });
    txt(s, d, { x: 1.55, y: y + 0.44, w: 10.8, h: 0.28, fontSize: 11.5, color: D.inkSoft });
  });
  txt(s, "Una tarde de trabajo cierra los cinco. Todos son de tamaño S.",
    { x: 0.7, y: 6.6, w: 11.9, h: 0.4, fontSize: 13, bold: true, color: D.accentSoft });
  s.addNotes("El caso histórico que los justifica: prune() vivió 14 fases con test verde y cero llamadas.");
}

/* 12 ─ Arquitectura */
{ const s = S(); head(s, pptx, "Arquitectura", "Sana en lo estructural, cara de evolucionar", true);
  const at = [["Acoplamiento", D.sev.p2], ["Cohesión", D.sev.p2], ["Testabilidad", D.sev.ok], ["Resiliencia", D.sev.ok],
              ["Datos", D.sev.p2], ["Observabilidad", D.sev.p2], ["Seguridad", D.sev.ok], ["Evolutividad", D.sev.p1]];
  at.forEach(([n, c], i) => {
    const x = 0.7 + (i % 4) * 1.66, y = 1.95 + Math.floor(i / 4) * 1.05;
    card(s, x, y, 1.5, 0.88, D.darkAlt);
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.62, y: y + 0.14, w: 0.26, h: 0.26, fill: { color: c }, line: { color: c, width: 0 } });
    txt(s, n, { x: x + 0.06, y: y + 0.5, w: 1.38, h: 0.3, fontSize: 10, color: D.onDarkSoft, align: "center" });
  });
  card(s, 7.6, 1.95, 5.02, 2.05, D.darkAlt);
  txt(s, "25 de 40", { x: 7.9, y: 2.15, w: 4.4, h: 0.62, fontSize: 36, bold: true, color: D.sev.p1, fontFace: D.fontH });
  txt(s, "módulos importa app.py — cinco veces más que el siguiente. Toda feature nueva entra por ahí.",
    { x: 7.9, y: 2.82, w: 4.45, h: 1.0, fontSize: 12, color: D.onDarkSoft, lineSpacing: 16 });
  card(s, 0.7, 4.25, 11.92, 1.75, D.darkAlt);
  txt(s, "Y una condición de carrera en el apagado", { x: 1.0, y: 4.45, w: 11.3, h: 0.35, fontSize: 15, bold: true, color: D.onDark, fontFace: D.fontH });
  txt(s, "Application escribe _loop y _sup desde el hilo de asyncio y los lee desde el de Tk sin sincronizar. Si la parada llega antes, la cancelación no se ejecuta. El propio proyecto ya resuelve esto bien en AgentState, con Lock: la inconsistencia del patrón es el defecto.",
    { x: 1.0, y: 4.85, w: 11.3, h: 0.95, fontSize: 12.5, color: D.onDarkSoft, lineSpacing: 17 });
  s.addNotes("0 ciclos de dependencia a nivel de archivo entre 40 módulos y 97 aristas.");
}

/* 13 ─ Falsos positivos */
{ const s = S(); head(s, pptx, "Rigor", "Lo que las herramientas dijeron y no era cierto");
  const fp = [["Ciclo de dependencias", "marcado \"evidencia P1\" por el script", "Verificado a nivel de archivo: 0 ciclos. Artefacto de agrupar por directorio."],
              ["God-module src/vigia_eew", "fan-in 6, fan-out 4, 1.771 LOC", "Reformulado, no descartado: el problema real es app.py con fan-out 25."],
              ["15 pares de co-cambio", "\"fronteras ficticias\"", "Todos son fuente↔su propio test o documento↔documento. Sanos."],
              ["251.255 LOC de Python", "reportado por el inventario", "Son 9.186. El resto es un entorno virtual en el árbol de trabajo."]];
  fp.forEach(([t, w, v], i) => {
    const y = 1.9 + i * 1.15;
    card(s, 0.7, y, 11.92, 1.0);
    txt(s, t, { x: 1.0, y: y + 0.14, w: 3.4, h: 0.3, fontSize: 13.5, bold: true, fontFace: D.fontH });
    txt(s, w, { x: 1.0, y: y + 0.48, w: 3.4, h: 0.35, fontSize: 11, color: D.inkSoft, italic: true });
    s.addShape(pptx.ShapeType.ellipse, { x: 4.6, y: y + 0.35, w: 0.28, h: 0.28, fill: { color: D.accent }, line: { color: D.accent, width: 0 } });
    txt(s, v, { x: 5.05, y: y + 0.28, w: 7.3, h: 0.5, fontSize: 12.5, lineSpacing: 16 });
  });
  txt(s, "Documentados uno a uno para que la próxima auditoría no vuelva a litigarlos.",
    { x: 0.7, y: 6.55, w: 11.9, h: 0.4, fontSize: 12.5, color: D.inkSoft, italic: true });
  s.addNotes("Un hallazgo sin verificar es ruido. Verificarlos y descartarlos es parte del trabajo.");
}

/* 14 ─ Gaps */
{ const s = S(); head(s, pptx, "Honestidad", "Lo que no se pudo medir, y por qué", true);
  const g = [["Cobertura de pruebas", "El proyecto exige Python ≥3.11; el entorno solo tenía 3.10 y no podía descargar otro"],
             ["Gitleaks · Trivy · Semgrep", "Binarios y rulesets desde dominios bloqueados. Sustituidos donde fue posible"],
             ["Base de datos OSV", "api.osv.dev devuelve 403. Se usó la base de PyPI, equivalente para paquetes PyPI"],
             ["6 paquetes de macOS y Windows", "No instalables en el entorno de análisis. El repo ya tiene runners para cerrarlo"]];
  g.forEach(([t, d], i) => {
    const y = 1.9 + i * 1.13;
    card(s, 0.7, y, 11.92, 0.98, D.darkAlt);
    s.addShape(pptx.ShapeType.ellipse, { x: 1.0, y: y + 0.35, w: 0.3, h: 0.3, fill: { color: D.sev.na }, line: { color: D.sev.na, width: 0 } });
    txt(s, t, { x: 1.5, y: y + 0.15, w: 3.6, h: 0.3, fontSize: 13.5, bold: true, color: D.onDark, fontFace: D.fontH });
    txt(s, d, { x: 1.5, y: y + 0.5, w: 10.8, h: 0.35, fontSize: 11.5, color: D.onDarkSoft });
  });
  txt(s, "Ninguna cifra fue estimada. Donde faltó herramienta, la dimensión quedó marcada \"no evaluada\".",
    { x: 0.7, y: 6.5, w: 11.9, h: 0.45, fontSize: 13.5, bold: true, color: D.accent });
  s.addNotes("Regla de oro de la metodología: sustituir y documentar el gap, nunca fabricar un resultado.");
}

/* 15 ─ Plan */
{ const s = S(); head(s, pptx, "Plan consolidado", "Qué es bloqueante y qué va en paralelo");
  const seq = [["M0", "Versionar uv.lock", "S · nulo"], ["M1", "Runtime 3.11 → 3.13", "M · medio"],
               ["M2", "Pisos, techos y re-lock", "S · bajo"], ["M3", "Gate de resolución mínima", "S · nulo"]];
  txt(s, "Cadena bloqueante — estrictamente secuencial", { x: 0.7, y: 1.85, w: 11.9, h: 0.32, fontSize: 13, bold: true, color: D.sev.p1 });
  seq.forEach(([n, t, e], i) => {
    const x = 0.7 + i * 3.07;
    card(s, x, 2.25, 2.85, 1.35);
    txt(s, n, { x: x + 0.25, y: 2.42, w: 1.0, h: 0.34, fontSize: 17, bold: true, color: D.sev.p1, fontFace: D.fontH });
    txt(s, t, { x: x + 0.25, y: 2.8, w: 2.4, h: 0.45, fontSize: 12, lineSpacing: 14 });
    txt(s, e, { x: x + 0.25, y: 3.25, w: 2.4, h: 0.25, fontSize: 10.5, color: D.inkSoft });
    if (i < 3) txt(s, "→", { x: x + 2.86, y: 2.75, w: 0.25, h: 0.3, fontSize: 16, bold: true, color: D.inkSoft });
  });
  txt(s, "En paralelo — desde el primer día", { x: 0.7, y: 3.95, w: 11.9, h: 0.32, fontSize: 13, bold: true, color: D.accentSoft });
  const par = [["M4", "Build Linux en contenedor fijado", "M · medio"], ["M5", "Auditar deps de macOS y Windows", "S · nulo"], ["M6", "Decidir la política sobre pystray", "decisión"]];
  par.forEach(([n, t, e], i) => {
    const x = 0.7 + i * 4.07;
    card(s, x, 4.35, 3.75, 1.3);
    txt(s, n, { x: x + 0.25, y: 4.52, w: 1.0, h: 0.32, fontSize: 16, bold: true, color: D.accentSoft, fontFace: D.fontH });
    txt(s, t, { x: x + 0.25, y: 4.88, w: 3.3, h: 0.4, fontSize: 12 });
    txt(s, e, { x: x + 0.25, y: 5.3, w: 3.3, h: 0.25, fontSize: 10.5, color: D.inkSoft });
  });
  txt(s, "El orden importa: requires-python determina qué versiones son resolubles, así que subir el runtime antes de fijar techos evita rehacerlos.",
    { x: 0.7, y: 5.95, w: 11.9, h: 0.45, fontSize: 12.5, color: D.inkSoft, italic: true });
  s.addNotes("Este plan no toca lo que ya tiene dueño en code-audit, arch-eval o el kit SDD.");
}

/* 16 ─ Decisiones humanas */
{ const s = S(); head(s, pptx, "Necesitan una decisión tuya", "Tres cosas que no puedo decidir por defecto", true);
  const dec = [["¿La alerta bajo Wayland bloquea el release?", "Hoy la garantía central del producto no se cumple en el escritorio Linux más común. El diseño existe (ADR-010) y nunca se implementó."],
               ["¿Qué se hace con pystray?", "1.085 días sin publicar, y es quien arrastra Pillow al árbol. Mantener con riesgo aceptado, migrar, o retirar la bandeja donde no funciona."],
               ["¿Se enmienda la constitución a Python 3.13?", "Cambiar una restricción de stack exige enmienda con changelog. Por eso se anotó en vez de editarla."]];
  dec.forEach(([t, d], i) => {
    const y = 1.9 + i * 1.5;
    card(s, 0.7, y, 11.92, 1.32, D.darkAlt);
    s.addShape(pptx.ShapeType.ellipse, { x: 1.0, y: y + 0.44, w: 0.44, h: 0.44, fill: { color: D.accent }, line: { color: D.accent, width: 0 } });
    txt(s, String(i + 1), { x: 1.0, y: y + 0.53, w: 0.44, h: 0.28, fontSize: 14, bold: true, color: "FFFFFF", align: "center" });
    txt(s, t, { x: 1.65, y: y + 0.2, w: 10.6, h: 0.35, fontSize: 15.5, bold: true, color: D.onDark, fontFace: D.fontH });
    txt(s, d, { x: 1.65, y: y + 0.62, w: 10.6, h: 0.6, fontSize: 12, color: D.onDarkSoft, lineSpacing: 16 });
  });
  s.addNotes("Las tres estaban señaladas desde ángulos distintos en las cinco etapas anteriores.");
}

/* 17 ─ Cierre */
{ const s = S();
  titleSlide(s, pptx, "El código está sano.\nEl proceso tiene huecos.",
    "Cero P1 de seguridad. Cero secretos. Cero ciclos. Tipado estricto limpio.");
  txt(s, "Lo que falta no es arreglar código: es hacer que el gate mida lo que ya se sabe medir, y declarar por escrito lo que hoy se promete sin acotar.",
    { x: 0.7, y: 4.9, w: 8.6, h: 1.0, fontSize: 14, color: D.onDarkSoft, lineSpacing: 20 });
  txt(s, "Siguiente paso:  M0 — versionar uv.lock.  Menos de una hora, riesgo nulo, desbloquea todo lo demás.",
    { x: 0.7, y: 6.0, w: 9.6, h: 0.5, fontSize: 13.5, bold: true, color: D.accent });
  s.addNotes("Detalle completo en docs/: 94 artefactos, 0 enlaces rotos, 16 diagramas validados.");
}

pptx.writeFile({ fileName: "/tmp/deck/vigia-eew-evaluacion.pptx" })
  .then(f => console.log("escrito:", f));
