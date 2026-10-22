/**
 * Festival de la Leyenda Vallenata — Votación del público y administración
 * Datos simulados en memoria: en producción cada regla marcada "SERVIDOR" debe validarse en backend.
 */

/* ==========================================================================
   0. DATOS Y ESTADO (simulados)
   ========================================================================== */
const FECHA_FINAL = new Date('2026-11-28T20:00:00-05:00');
const PADRON = 25000; // personas habilitadas, base del % de participación

const CATEGORIAS = [
  { id: 'rey', nombre: 'Rey Vallenato', icono: 'ph-crown', desc: 'Acordeoneros en la corona mayor' },
  { id: 'acordeonera', nombre: 'Acordeonera', icono: 'ph-music-notes', desc: 'Las mujeres del fuelle' },
  { id: 'inedita', nombre: 'Canción Inédita', icono: 'ph-pen-nib', desc: 'Composiciones nuevas' },
  { id: 'piqueria', nombre: 'Piqueria', icono: 'ph-microphone-stage', desc: 'Versos improvisados' }
];

// estado: 'vivo' | 'prox' | 'cerrada'
const votaciones = [
  { id: 'v1', cat: 'rey', titulo: 'Final Rey Vallenato', estado: 'vivo', opciones: [
    { id: 'o1', nombre: 'Javier Ramos', detalle: 'Paseo · "El Amor, Amor"', votos: 3120 },
    { id: 'o2', nombre: 'Edison Dangond', detalle: 'Puya · "Pedazo de Acordeón"', votos: 2740 },
    { id: 'o3', nombre: 'Luis Mejía', detalle: 'Merengue · "La Gota Fría"', votos: 1985 }] },
  { id: 'v2', cat: 'acordeonera', titulo: 'Semifinal Acordeonera', estado: 'vivo', opciones: [
    { id: 'o1', nombre: 'María Clara Cuello', detalle: 'Merengue · "La Gota Fría"', votos: 2210 },
    { id: 'o2', nombre: 'Sofía Daza', detalle: 'Son · "Alicia Adorada"', votos: 1890 },
    { id: 'o3', nombre: 'Laura Peñaloza', detalle: 'Paseo · "Altos del Rosario"', votos: 1430 }] },
  { id: 'v3', cat: 'inedita', titulo: 'Canción Inédita · Ronda final', estado: 'prox', opciones: [
    { id: 'o1', nombre: 'Andrés Oñate', detalle: 'Paseo · "Guatapurí"', votos: 0 },
    { id: 'o2', nombre: 'Camila Zuleta', detalle: 'Merengue · "Perijá al amanecer"', votos: 0 }] },
  { id: 'v4', cat: 'piqueria', titulo: 'Piqueria · Cuartos de final', estado: 'cerrada', opciones: [
    { id: 'o1', nombre: 'Ever Zabaleta', detalle: 'Verso libre', votos: 1640 },
    { id: 'o2', nombre: 'Jhon Torres', detalle: 'Verso libre', votos: 1405 }] }
];

const ETIQUETA = { vivo: ['badge-vivo', 'EN VIVO'], prox: ['badge-prox', 'PRÓXIMAMENTE'], cerrada: ['badge-cerrada', 'CERRADA'] };

const estado = {
  sesion: null,            // { correo } tras login/registro (CU-01)
  filtroCat: null,         // categoría activa en Votaciones (CU-02)
  votacionActual: null,    // votación abierta en Opciones (CU-03)
  opcionElegida: null,
  pinEsperado: null,
  votados: {},             // { [votacionId]: comprobante } — una persona, un voto (SERVIDOR)
  vpm: 0,
  alertas: [
    { ip: '190.24.18.77', texto: '38 intentos de voto en 2 min', nivel: 'Bloqueada' },
    { ip: '181.55.102.9', texto: '5 cuentas distintas desde la misma IP', nivel: 'En revisión' }
  ]
};

const $ = (id) => document.getElementById(id);
const totalVotos = (v) => v.opciones.reduce((s, o) => s + o.votos, 0);
const NAV_GRUPO = { 'vista-opciones': 'vista-votaciones', 'vista-resultado': 'vista-votaciones', 'vista-registro': 'vista-login' };

/* ==========================================================================
   1. NAVEGACIÓN SPA (.vista-modulo) + toast
   ========================================================================== */
function navegarA(idVista) {
  if (!$(idVista)) idVista = 'vista-inicio';
  document.querySelectorAll('.vista-modulo').forEach((m) => m.classList.remove('active'));
  $(idVista).classList.add('active');
  document.body.dataset.vista = idVista;
  window.scrollTo({ top: 0 });
  history.replaceState(null, '', `#${idVista}`);

  const grupo = NAV_GRUPO[idVista] || idVista;
  document.querySelectorAll('[data-view-target]').forEach((b) => {
    const activo = b.dataset.viewTarget === grupo;
    b.classList.toggle('active', activo);
    if (activo) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });

  if (idVista === 'vista-votaciones') renderVotaciones();
  if (idVista === 'vista-admin') renderAdmin();
}

let toastTimer;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2800);
}

/* ==========================================================================
   2. INICIO — cuenta regresiva y categorías
   ========================================================================== */
function tickCuentaRegresiva() {
  let ms = Math.max(0, FECHA_FINAL - Date.now());
  const p = (n) => String(n).padStart(2, '0');
  const dias = Math.floor(ms / 864e5); ms %= 864e5;
  const horas = Math.floor(ms / 36e5); ms %= 36e5;
  const min = Math.floor(ms / 6e4);
  const seg = Math.floor((ms % 6e4) / 1000);
  $('cd-dias').textContent = p(dias);
  $('cd-horas').textContent = p(horas);
  $('cd-min').textContent = p(min);
  $('cd-seg').textContent = p(seg);
}

function renderCategorias() {
  $('home-categorias').innerHTML = CATEGORIAS.map((c) => `
    <button type="button" class="cat-tile" onclick="verCategoria('${c.id}')">
      <span class="cat-ico"><i class="ph-fill ${c.icono}"></i></span>
      <strong>${c.nombre}</strong>
    </button>`).join('');

  // CU-02: vista Categorías con botón "Ver"
  $('lista-categorias').innerHTML = CATEGORIAS.map((c) => `
    <div class="fila">
      <span class="cat-ico"><i class="ph-fill ${c.icono}"></i></span>
      <div class="fila-info"><strong>${c.nombre}</strong><span>${c.desc}</span></div>
      <button type="button" class="btn btn-ghost btn-sm" onclick="verCategoria('${c.id}')" aria-label="Ver votaciones de ${c.nombre}">Ver</button>
    </div>`).join('');
}

/* ==========================================================================
   3. REGISTRO Y LOGIN (CU-01)
   ========================================================================== */
function setError(inputId, errId, msg) {
  const err = $(errId);
  err.textContent = msg || '';
  const inp = $(inputId);
  if (inp) inp.setAttribute('aria-invalid', msg ? 'true' : 'false');
  return !msg;
}

function procesarRegistro(e) {
  e.preventDefault();
  const correo = $('reg-correo').value.trim();
  const celular = $('reg-celular').value.trim();
  const clave = $('reg-clave').value;

  const ok = [
    setError('reg-correo', 'err-reg-correo', /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo) ? '' : 'Escribe un correo válido.'),
    setError('reg-celular', 'err-reg-celular', /^3\d{9}$/.test(celular) ? '' : 'Celular colombiano de 10 dígitos, empieza por 3.'),
    setError('reg-clave', 'err-reg-clave', clave.length >= 8 ? '' : 'Usa al menos 8 caracteres.'),
    setError(null, 'err-reg-habeas', $('reg-habeas').checked ? '' : 'Debes aceptar el tratamiento de datos y confirmar que eres mayor de edad.')
  ].every(Boolean);
  if (!ok) return;

  iniciarSesion(correo);
  $('form-registro').reset();
  toast('Cuenta creada. Ya puedes votar.');
  navegarA('vista-votaciones');
}

function cambiarTabLogin(tab) {
  ['clave', 'otp'].forEach((t) => {
    const activa = t === tab;
    $(`tab-${t}`).setAttribute('aria-selected', activa);
    $(`tab-${t}`).tabIndex = activa ? 0 : -1;
    $(`panel-${t}`).classList.toggle('hidden', !activa);
  });
}

function enviarOtp() {
  if (!/^3\d{9}$/.test($('otp-celular').value.trim())) {
    toast('Escribe un celular válido primero.');
    return;
  }
  toast('Código enviado. Demo: usa 123456.');
}

function procesarLogin(e, modo) {
  e.preventDefault();
  if (modo === 'clave') {
    const correo = $('log-correo').value.trim();
    const ok = correo && $('log-clave').value.length >= 8;
    setError(null, 'err-log-clave', ok ? '' : 'Correo o contraseña incorrectos.');
    if (!ok) return;
    iniciarSesion(correo);
  } else {
    const ok = /^3\d{9}$/.test($('otp-celular').value.trim()) && $('otp-codigo').value === '123456';
    setError('otp-codigo', 'err-log-otp', ok ? '' : 'El celular o el código no coinciden.');
    if (!ok) return;
    iniciarSesion($('otp-celular').value.trim());
  }
  toast('Sesión iniciada.');
  navegarA('vista-votaciones');
}

function iniciarSesion(id) {
  estado.sesion = { id };
  const chip = $('user-chip');
  chip.textContent = id;
  chip.classList.add('on');
}

/* ==========================================================================
   4. CATEGORÍAS Y VOTACIONES DISPONIBLES (CU-02)
   ========================================================================== */
function verCategoria(catId) {
  estado.filtroCat = catId;
  navegarA('vista-votaciones');
}

function quitarFiltro() {
  estado.filtroCat = null;
  renderVotaciones();
}

function renderVotaciones() {
  const cat = CATEGORIAS.find((c) => c.id === estado.filtroCat);
  $('filtro-activo').innerHTML = cat
    ? `<span class="filtro-chip">${cat.nombre}<button type="button" onclick="quitarFiltro()" aria-label="Quitar filtro"><i class="ph ph-x"></i></button></span>`
    : '';

  const lista = votaciones.filter((v) => !cat || v.cat === cat.id);
  $('lista-votaciones').innerHTML = lista.length ? lista.map((v) => {
    const [clase, texto] = ETIQUETA[v.estado];
    const yaVoto = estado.votados[v.id];
    const sub = yaVoto ? 'Ya votaste · ver comprobante' : `${totalVotos(v).toLocaleString('es-CO')} votos`;
    return `
      <button type="button" class="fila" onclick="abrirVotacion('${v.id}')">
        <div class="fila-info"><strong>${v.titulo}</strong><span>${sub}</span></div>
        <span class="badge ${clase}">${texto}</span>
      </button>`;
  }).join('') : '<p class="muted">No hay votaciones en esta categoría.</p>';
}

function abrirVotacion(id) {
  const v = votaciones.find((x) => x.id === id);
  if (v.estado === 'prox') return toast('Esta votación aún no abre.');
  if (v.estado === 'cerrada') return toast('Esta votación ya cerró.');
  if (!estado.sesion) {
    toast('Inicia sesión para votar.');
    return navegarA('vista-login');
  }
  estado.votacionActual = v;
  if (estado.votados[v.id]) return mostrarResultado(v); // una persona, un voto
  renderOpciones(v);
  navegarA('vista-opciones');
}

/* ==========================================================================
   5. OPCIONES ELEGIBLES (CU-03)
   ========================================================================== */
function renderOpciones(v) {
  estado.opcionElegida = null;
  $('op-titulo').textContent = v.titulo;
  $('form-opciones').innerHTML = v.opciones.map((o) => `
    <label class="opcion">
      <span class="inicial" aria-hidden="true">${o.nombre[0]}</span>
      <span class="opcion-info">
        <strong>${o.nombre}</strong>
        <span class="muted">${o.detalle}</span>
        <button type="button" class="btn-muestra" onclick="escucharMuestra(event,this)"><i class="ph-fill ph-play-circle"></i><span>Escuchar muestra</span></button>
      </span>
      <input type="radio" class="sr" name="opcion" value="${o.id}" onchange="elegirOpcion('${o.id}')">
      <span class="radio-visual" aria-hidden="true"></span>
    </label>`).join('');
  actualizarBotonVotar();
}

function elegirOpcion(oid) {
  estado.opcionElegida = estado.votacionActual.opciones.find((o) => o.id === oid);
  actualizarBotonVotar();
}

function actualizarBotonVotar() {
  const btn = $('btn-votar');
  const o = estado.opcionElegida;
  btn.disabled = !o;
  btn.textContent = o ? `Votar por ${o.nombre}` : 'Elige una opción';
}

let muestraTimer;
function escucharMuestra(ev, btn) {
  ev.preventDefault(); ev.stopPropagation(); // el botón vive dentro del <label>: no debe marcar el radio
  const sonando = btn.classList.contains('sonando');
  document.querySelectorAll('.btn-muestra').forEach((b) => {
    b.classList.remove('sonando');
    b.querySelector('i').className = 'ph-fill ph-play-circle';
    b.querySelector('span').textContent = 'Escuchar muestra';
  });
  clearTimeout(muestraTimer);
  if (sonando) return;
  btn.classList.add('sonando');
  btn.querySelector('i').className = 'ph-fill ph-pause-circle';
  btn.querySelector('span').textContent = 'Sonando…';
  muestraTimer = setTimeout(() => { // simulación: 8 s de muestra
    btn.classList.remove('sonando');
    btn.querySelector('i').className = 'ph-fill ph-play-circle';
    btn.querySelector('span').textContent = 'Escuchar muestra';
  }, 8000);
}

/* ==========================================================================
   6. CONFIRMACIÓN IRREVERSIBLE + PIN ANTI-BOT (CU-03 — crítico)
   ========================================================================== */
let focoPrevio;
function pedirConfirmacion(e) {
  e.preventDefault();
  if (!estado.opcionElegida) return;
  estado.pinEsperado = String(Math.floor(1000 + Math.random() * 9000)); // SERVIDOR: PIN de un solo uso por SMS
  $('sheet-detalle').textContent = `Votarás por ${estado.opcionElegida.nombre} en “${estado.votacionActual.titulo}”.`;
  $('pin-demo').textContent = `(Demo: ${estado.pinEsperado})`;
  $('pin-input').value = '';
  $('pin-input').classList.remove('mal');
  $('err-pin').textContent = '';
  $('btn-emitir').disabled = true;
  focoPrevio = document.activeElement;
  $('sheet-overlay').classList.remove('hidden');
  setTimeout(() => $('pin-input').focus(), 120);
}

function cerrarSheet() {
  $('sheet-overlay').classList.add('hidden');
  if (focoPrevio) focoPrevio.focus();
}

function validarPin() {
  const inp = $('pin-input');
  inp.value = inp.value.replace(/\D/g, '').slice(0, 4);
  inp.classList.remove('mal');
  $('err-pin').textContent = '';
  $('btn-emitir').disabled = inp.value.length !== 4; // "Emitir voto" solo con 4 dígitos
}

async function emitirVoto() {
  const v = estado.votacionActual;
  const o = estado.opcionElegida;
  const btn = $('btn-emitir');
  if (btn.disabled) return; // evita doble envío

  if ($('pin-input').value !== estado.pinEsperado) {
    const inp = $('pin-input');
    inp.classList.remove('mal'); void inp.offsetWidth; inp.classList.add('mal');
    $('err-pin').textContent = 'El PIN no coincide. Revisa el SMS e inténtalo de nuevo.';
    return;
  }
  if (v.estado !== 'vivo') { // un admin pudo cerrarla mientras el sheet estaba abierto
    cerrarSheet();
    toast('La votación cerró antes de emitir tu voto.');
    return navegarA('vista-votaciones');
  }

  btn.disabled = true;
  btn.textContent = 'Emitiendo…';

  const ahora = new Date();
  const codigo = 'VV-' + Array.from(crypto.getRandomValues(new Uint8Array(4)), (b) => b.toString(16).padStart(2, '0')).join('').toUpperCase();
  const hash = await sha256(`${codigo}|${v.id}|${o.id}|${ahora.toISOString()}`);

  o.votos += 1; // SERVIDOR: escritura única, append-only
  estado.votados[v.id] = {
    codigo, hash, opcionId: o.id,
    fecha: ahora.toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'medium', timeZone: 'America/Bogota' })
  };

  btn.textContent = 'Emitir voto';
  cerrarSheet();
  mostrarResultado(v);
}

async function sha256(texto) {
  try {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
    return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
  } catch { // contexto no seguro (sin crypto.subtle): hash simulado
    return Array.from(crypto.getRandomValues(new Uint8Array(32)), (b) => b.toString(16).padStart(2, '0')).join('');
  }
}

/* ==========================================================================
   7. RESULTADO Y COMPROBANTE INMUTABLE (CU-03)
   ========================================================================== */
function mostrarResultado(v) {
  estado.votacionActual = v;
  const c = estado.votados[v.id];
  const o = v.opciones.find((x) => x.id === c.opcionId);
  $('res-resumen').textContent = `Tu voto por ${o.nombre} quedó guardado en “${v.titulo}”.`;
  $('comp-codigo').textContent = c.codigo;
  $('comp-fecha').textContent = c.fecha;
  $('comp-hash').textContent = c.hash;
  navegarA('vista-resultado');
  renderTendencia(true);
}

function renderTendencia(animar) {
  const v = estado.votacionActual;
  if (!v || !estado.votados[v.id]) return;
  const total = totalVotos(v) || 1;
  const propia = estado.votados[v.id].opcionId;
  const orden = [...v.opciones].sort((a, b) => b.votos - a.votos);
  const cont = $('tendencia');

  if (animar || cont.children.length !== orden.length) {
    cont.innerHTML = orden.map((o) => `
      <div class="barra" data-id="${o.id}">
        <div class="barra-top"><span class="${o.id === propia ? 'tuyo' : ''}">${o.nombre}${o.id === propia ? ' · tu voto' : ''}</span><span class="pct"></span></div>
        <div class="barra-pista"><div class="barra-fill ${o.id === propia ? 'tuyo' : ''}"></div></div>
      </div>`).join('');
    cont.offsetWidth; // fuerza reflow para que el ancho se anime desde 0
  }
  orden.forEach((o) => {
    const fila = cont.querySelector(`[data-id="${o.id}"]`);
    const pct = (o.votos / total) * 100;
    fila.querySelector('.pct').textContent = `${pct.toFixed(1)}%`;
    fila.querySelector('.barra-fill').style.width = `${pct}%`;
  });
}

/* ==========================================================================
   8. PANEL DE ADMINISTRACIÓN (CU-04 KPIs · CU-05 alertas · CU-06 gestión)
   ========================================================================== */
function renderAdmin() {
  // CU-04: KPIs
  const total = votaciones.reduce((s, v) => s + totalVotos(v), 0);
  $('kpi-total').textContent = total.toLocaleString('es-CO');
  $('kpi-vpm').textContent = estado.vpm;
  $('kpi-part').textContent = `${Math.min(100, (total / PADRON) * 100).toFixed(1)}%`;

  // CU-05: alertas anti-fraude (texto rojo)
  $('alertas').innerHTML = estado.alertas.length ? estado.alertas.map((a) => `
    <div class="alerta"><i class="ph-fill ph-shield-warning" aria-hidden="true"></i>
      <span>IP ${a.ip} · ${a.nivel}<small>${a.texto}</small></span></div>`).join('')
    : '<p class="muted">Sin alertas activas.</p>';

  // CU-06: toggles iOS para abrir/cerrar votaciones
  $('admin-lista').innerHTML = votaciones.map((v) => {
    const [clase, texto] = ETIQUETA[v.estado];
    return `
      <div class="fila">
        <div class="fila-info"><strong>${v.titulo}</strong><span class="badge ${clase}" style="margin-top:0.25rem">${texto}</span></div>
        <button type="button" class="switch" role="switch" aria-checked="${v.estado === 'vivo'}" aria-label="Votación en vivo: ${v.titulo}" onclick="alternarVotacion('${v.id}')"></button>
      </div>`;
  }).join('');
}

function alternarVotacion(id) {
  const v = votaciones.find((x) => x.id === id);
  v.estado = v.estado === 'vivo' ? 'cerrada' : 'vivo'; // SERVIDOR: registrar en bitácora quién y cuándo
  toast(`${v.titulo}: ${v.estado === 'vivo' ? 'abierta' : 'cerrada'}.`);
  renderAdmin();
}

/* ==========================================================================
   9. SIMULACIÓN EN VIVO (votos entrantes, KPIs, tendencia)
   ========================================================================== */
function simularVotosEntrantes() {
  let nuevos = 0;
  votaciones.filter((v) => v.estado === 'vivo').forEach((v) => {
    const o = v.opciones[Math.floor(Math.random() * v.opciones.length)];
    const n = Math.floor(Math.random() * 6) + 1;
    o.votos += n; nuevos += n;
  });
  estado.vpm = Math.round(nuevos * 24 * (0.8 + Math.random() * 0.4)); // 2,5 s → por minuto
  const vista = document.body.dataset.vista;
  if (vista === 'vista-admin') renderAdmin();
  if (vista === 'vista-resultado') renderTendencia(false);
}

/* ==========================================================================
   10. ARRANQUE
   ========================================================================== */
document.addEventListener('DOMContentLoaded', () => {
  renderCategorias();
  tickCuentaRegresiva();
  setInterval(tickCuentaRegresiva, 1000);
  setInterval(simularVotosEntrantes, 2500);

  // Solo vistas "seguras" por hash; opciones/resultado exigen estado previo
  const hash = location.hash.replace('#', '');
  const permitidas = ['vista-inicio', 'vista-registro', 'vista-login', 'vista-categorias', 'vista-votaciones', 'vista-admin'];
  navegarA(permitidas.includes(hash) ? hash : 'vista-inicio');

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('sheet-overlay').classList.contains('hidden')) cerrarSheet();
  });
});
