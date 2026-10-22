/**
 * Festival de la Leyenda Vallenata — Votación del público y administración
 * Datos simulados en memoria: en producción cada regla marcada «// SERVIDOR:» debe validarse en el backend.
 */

/* ==========================================================================
   0. DATOS Y ESTADO (simulados)
   ========================================================================== */
// Final del Festival: 1 de mayo de 2027 (el Festival va del 28 de abril al 1 de mayo). La hora es de ejemplo.
const FECHA_FINAL = new Date('2027-05-01T20:00:00-05:00');
const PADRON = 25000; // personas habilitadas, base del % de participación

const CATEGORIAS = [
  { id: 'rey', nombre: 'Rey Vallenato', icono: 'ph-crown', desc: 'Acordeoneros en la corona mayor', publicada: true },
  { id: 'acordeonera', nombre: 'Acordeonera Mayor', icono: 'ph-music-notes', desc: 'Las mujeres del fuelle', publicada: true },
  { id: 'inedita', nombre: 'Canción Inédita', icono: 'ph-pen-nib', desc: 'Composiciones nuevas', publicada: true },
  { id: 'piqueria', nombre: 'Piquería Mayor', icono: 'ph-microphone-stage', desc: 'Versos improvisados', publicada: true }
];

const fecha = (isoLocal) => new Date(`${isoLocal}:00-05:00`); // hora de Colombia
const opcion = (id, nombre, detalle, votos) => ({ id, nombre, detalle, votos, publicada: true, estado: 'activa' }); // estado: 'activa' | 'retirada'

// estado: 'prox' (programada) | 'vivo' (abierta) | 'pausada' | 'cerrada'
// limite: votos por persona (RN-01, por defecto 1, pendiente de validación P-03)
// visibilidad: 'cierre' (por defecto, RN-06) | 'ceremonia' | 'vivo' (requiere aprobación de la Fundación, P-05)
const votacion = (datos) => ({ limite: 1, visibilidad: 'cierre', conciliada: null, sello: null, publicada: false, ...datos });

const votaciones = [
  votacion({ id: 'v1', cat: 'rey', titulo: 'Final Rey Vallenato', estado: 'vivo', abre: fecha('2027-05-01T19:00'), cierra: fecha('2027-05-01T23:30'), opciones: [
    opcion('o1', 'Javier Ramos', 'Paseo · "El Amor, Amor"', 3120),
    opcion('o2', 'Edison Dangond', 'Puya · "Pedazo de Acordeón"', 2740),
    opcion('o3', 'Luis Mejía', 'Merengue · "La Gota Fría"', 1985)] }),
  votacion({ id: 'v2', cat: 'acordeonera', titulo: 'Semifinal Acordeonera Mayor', estado: 'vivo', abre: fecha('2027-05-01T14:00'), cierra: fecha('2027-05-01T22:00'), opciones: [
    opcion('o1', 'María Clara Cuello', 'Merengue · "La Gota Fría"', 2210),
    opcion('o2', 'Sofía Daza', 'Son · "Alicia Adorada"', 1890),
    opcion('o3', 'Laura Peñaloza', 'Paseo · "Altos del Rosario"', 1430)] }),
  votacion({ id: 'v3', cat: 'inedita', titulo: 'Canción Inédita · Ronda final', estado: 'prox', abre: fecha('2027-05-01T21:00'), cierra: fecha('2027-05-01T23:59'), opciones: [
    opcion('o1', 'Andrés Oñate', 'Paseo · "Guatapurí"', 0),
    opcion('o2', 'Camila Zuleta', 'Merengue · "Perijá al amanecer"', 0)] }),
  votacion({ id: 'v4', cat: 'piqueria', titulo: 'Piquería Mayor · Cuartos de final', estado: 'cerrada', abre: fecha('2027-04-29T15:00'), cierra: fecha('2027-04-29T21:00'), opciones: [
    opcion('o1', 'Ever Zabaleta', 'Verso libre', 1640),
    opcion('o2', 'Jhon Torres', 'Verso libre', 1405)] })
];

// Cuentas de demostración. rol: 'votante' | 'personal' (el personal no vota, RN-08).
// PENDIENTE P-15: roles del personal; la demo usa uno solo.
const cuentas = [
  { correo: 'votante@example.com', celular: '3001234567', verificado: true, rol: 'votante' },
  { correo: 'personal@example.com', celular: '', verificado: true, rol: 'personal' }
];

const ETIQUETA = {
  prox: ['badge-prox', 'PRÓXIMAMENTE'],
  vivo: ['badge-vivo', 'EN VIVO'],
  pausada: ['badge-pausada', 'PAUSADA'],
  cerrada: ['badge-cerrada', 'CERRADA']
};

const VISIBILIDAD = {
  cierre: ['Al cierre', 'Valor por defecto: se muestran cuando la organización los publica. Mostrarlos en vivo depende de la Fundación (P-05).'],
  ceremonia: ['En la ceremonia', 'Se muestran cuando se publiquen en la ceremonia.'],
  vivo: ['En vivo', 'Pendiente de aprobación de la Fundación (P-05).']
};

const estado = {
  sesion: null,              // { correo, rol } de una cuenta con correo verificado (CU-01, RN-04)
  correoPorVerificar: null,  // cuenta recién creada que espera la verificación del correo
  irADetalle: null,          // votación a la que se vuelve después de iniciar sesión
  filtroCat: null,           // categoría activa en Votaciones (CU-02)
  votacionActual: null,      // votación abierta en Detalle, Opciones y Resultado
  opcionElegida: null,
  pinEsperado: null,
  comprobantes: {},          // { [correo]: { [votacionId]: [comprobante, ...] } } hasta el límite de cada votación
  adminVotacion: 'v1',       // votación elegida en A4
  vpm: 0,
  alertas: [
    { ip: '190.24.18.77', texto: '38 intentos de voto en 2 min', nivel: 'Bloqueada' },
    { ip: '181.55.102.9', texto: '5 cuentas distintas desde la misma IP', nivel: 'En revisión' }
  ],
  auditoria: []              // { fecha, usuario, accion } — RN-05
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const totalVotos = (v) => v.opciones.reduce((s, o) => s + o.votos, 0);
const categoriaDe = (v) => CATEGORIAS.find((c) => c.id === v.cat);
const buscarCuenta = (correo) => cuentas.find((c) => c.correo === correo);
const esPersonal = () => estado.sesion?.rol === 'personal';
const opcionesPublicas = (v) => v.opciones.filter((o) => o.publicada && o.estado === 'activa');
const misComprobantes = (vid) => (estado.sesion && estado.comprobantes[estado.sesion.correo]?.[vid]) || [];
const votosRestantes = (v) => v.limite - misComprobantes(v.id).length;
// RN-06: sin conteos públicos con la votación abierta; al cierre se muestran cuando se publican (A5).
// La visibilidad «en vivo» solo aplica si la Fundación la aprueba (P-05).
const resultadosPublicos = (v) => v.publicada || (v.visibilidad === 'vivo' && v.estado !== 'prox');

// Formato colombiano: 2.234 · 11,2 % · 1 de mayo de 2027, 8:00 p. m.
const fmtNum = (n) => n.toLocaleString('es-CO');
const fmtPct = (n) => `${n.toLocaleString('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
const fmtFecha = (d) => d.toLocaleString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: 'America/Bogota' });
const fmtFechaCorta = (d) => d.toLocaleString('es-CO', { day: 'numeric', month: 'long', hour: 'numeric', minute: '2-digit', timeZone: 'America/Bogota' });

let contadorIds = 0;
const nuevoId = (prefijo) => `${prefijo}n${++contadorIds}`;

const NAV_GRUPO = { 'vista-detalle': 'vista-votaciones', 'vista-opciones': 'vista-votaciones', 'vista-resultado': 'vista-votaciones', 'vista-registro': 'vista-login' };
const VISTAS_ADMIN = ['vista-admin', 'vista-admin-categorias', 'vista-admin-votaciones', 'vista-admin-opciones', 'vista-admin-resultados'];

/* ==========================================================================
   1. NAVEGACIÓN SPA (.vista-modulo) + toast
   ========================================================================== */
const RENDER = {
  'vista-inicio': renderCategorias,
  'vista-categorias': renderCategorias,
  'vista-registro': renderRegistro,
  'vista-login': renderCuenta,
  'vista-votaciones': renderVotaciones,
  'vista-detalle': () => renderDetalle(true),
  'vista-admin': renderPanel,
  'vista-admin-categorias': renderAdminCategorias,
  'vista-admin-votaciones': renderAdminVotaciones,
  'vista-admin-opciones': renderAdminOpciones,
  'vista-admin-resultados': renderAdminResultados
};

function navegarA(idVista) {
  if (!$(idVista)) idVista = 'vista-inicio';
  // RN-05: solo el personal con permiso entra a la administración. SERVIDOR: validar el rol en cada petición.
  if (VISTAS_ADMIN.includes(idVista) && !esPersonal()) {
    toast('Entra con una cuenta del personal para administrar.');
    idVista = 'vista-login';
  }
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

  if (RENDER[idVista]) RENDER[idVista]();
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
   2. INICIO — cuenta regresiva y categorías (CU-02)
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
  const publicadas = CATEGORIAS.filter((c) => c.publicada);
  $('home-categorias').innerHTML = publicadas.map((c) => `
    <button type="button" class="cat-tile" onclick="verCategoria('${c.id}')">
      <span class="cat-ico"><i class="ph-fill ${c.icono}"></i></span>
      <strong>${esc(c.nombre)}</strong>
    </button>`).join('');

  // CU-02: vista Categorías con botón "Ver"
  $('lista-categorias').innerHTML = publicadas.map((c) => `
    <div class="fila">
      <span class="cat-ico"><i class="ph-fill ${c.icono}"></i></span>
      <div class="fila-info"><strong>${esc(c.nombre)}</strong><span>${esc(c.desc)}</span></div>
      <button type="button" class="btn btn-ghost btn-sm" onclick="verCategoria('${c.id}')" aria-label="Ver votaciones de ${esc(c.nombre)}">Ver</button>
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

function renderRegistro() {
  const pendiente = estado.correoPorVerificar;
  $('paso-registro').classList.toggle('hidden', !!pendiente);
  $('paso-verificacion').classList.toggle('hidden', !pendiente);
  if (pendiente) $('verif-correo').textContent = pendiente;
}

function procesarRegistro(e) {
  e.preventDefault();
  const correo = $('reg-correo').value.trim().toLowerCase();
  const celular = $('reg-celular').value.trim();
  const clave = $('reg-clave').value;

  // SERVIDOR: repetir todas estas validaciones y exigir correo único.
  const ok = [
    setError('reg-correo', 'err-reg-correo', !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correo) ? 'Escribe un correo válido.'
      : buscarCuenta(correo) ? 'Ya hay una cuenta con ese correo.' : ''),
    // PENDIENTE P-01: el celular es opcional mientras no se decida el método de identificación.
    setError('reg-celular', 'err-reg-celular', !celular || /^3\d{9}$/.test(celular) ? '' : 'Celular colombiano de 10 dígitos, empieza por 3.'),
    setError('reg-clave', 'err-reg-clave', clave.length >= 8 ? '' : 'Usa al menos 8 caracteres.'),
    setError('reg-datos', 'err-reg-datos', $('reg-datos').checked ? '' : 'Debes autorizar el tratamiento de tus datos.'),
    // RN-08: votan mayores de 18 años.
    setError('reg-edad', 'err-reg-edad', $('reg-edad').checked ? '' : 'Debes ser mayor de 18 años para votar.')
  ].every(Boolean);
  if (!ok) return;

  cuentas.push({ correo, celular, verificado: false, rol: 'votante' }); // SERVIDOR: guardar la contraseña solo como hash
  estado.correoPorVerificar = correo;
  $('form-registro').reset();
  renderRegistro();
  window.scrollTo({ top: 0 });
  toast('Cuenta creada. Verifica tu correo para votar.');
}

// RN-04: solo las cuentas con correo verificado inician sesión para votar.
function simularVerificacion() {
  // PENDIENTE P-01: método de verificación del correo. SERVIDOR: marcar verificado solo al confirmar el enlace o el código.
  const cuenta = buscarCuenta(estado.correoPorVerificar);
  cuenta.verificado = true;
  estado.correoPorVerificar = null;
  renderRegistro();
  iniciarSesion(cuenta);
  toast('Correo verificado. Ya puedes votar.');
  continuarTrasSesion();
}

function volverARegistro() {
  estado.correoPorVerificar = null;
  renderRegistro();
}

function cambiarTabLogin(tab) {
  ['clave', 'otp'].forEach((t) => {
    const activa = t === tab;
    $(`tab-${t}`).setAttribute('aria-selected', activa);
    $(`tab-${t}`).tabIndex = activa ? 0 : -1;
    $(`panel-${t}`).classList.toggle('hidden', !activa);
  });
}

// PENDIENTE P-01 y P-19: ingreso con código por SMS, solo como propuesta.
function enviarOtp() {
  if (!/^3\d{9}$/.test($('otp-celular').value.trim())) {
    toast('Escribe un celular válido primero.');
    return;
  }
  toast('Código enviado. Demo: usa 123456.');
}

function procesarLogin(e, modo) {
  e.preventDefault();
  let cuenta;
  if (modo === 'clave') {
    cuenta = buscarCuenta($('log-correo').value.trim().toLowerCase());
    // SERVIDOR: comparar la contraseña con su hash. Demo: cualquier contraseña de 8 caracteres o más.
    const ok = cuenta && $('log-clave').value.length >= 8;
    if (!setError(null, 'err-log-clave', ok ? '' : 'Correo o contraseña incorrectos.')) return;
  } else {
    // SERVIDOR: código de un solo uso con vencimiento, enviado al celular de una cuenta existente.
    const celular = $('otp-celular').value.trim();
    cuenta = cuentas.find((c) => c.celular && c.celular === celular);
    const ok = cuenta && $('otp-codigo').value === '123456';
    if (!setError('otp-codigo', 'err-log-otp', ok ? '' : 'El celular o el código no coinciden.')) return;
  }
  e.target.reset();
  if (!cuenta.verificado) { // RN-04
    estado.correoPorVerificar = cuenta.correo;
    toast('Primero verifica tu correo.');
    return navegarA('vista-registro');
  }
  iniciarSesion(cuenta);
  toast('Sesión iniciada.');
  continuarTrasSesion();
}

function iniciarSesion(cuenta) {
  estado.sesion = { correo: cuenta.correo, rol: cuenta.rol };
  const chip = $('user-chip');
  chip.textContent = cuenta.correo;
  chip.classList.add('on');
}

function continuarTrasSesion() {
  if (esPersonal()) return navegarA('vista-admin');
  const pendiente = estado.irADetalle;
  estado.irADetalle = null;
  if (pendiente) return abrirDetalle(pendiente);
  navegarA('vista-votaciones');
}

function cerrarSesion() {
  estado.sesion = null;
  const chip = $('user-chip');
  chip.textContent = 'Sin sesión';
  chip.classList.remove('on');
  toast('Sesión cerrada.');
  navegarA('vista-inicio');
}

function renderCuenta() {
  const s = estado.sesion;
  $('cuenta-login').classList.toggle('hidden', !!s);
  $('cuenta-sesion').classList.toggle('hidden', !s);
  if (!s) return;
  $('ses-correo').textContent = s.correo;
  $('ses-rol').textContent = s.rol === 'personal' ? 'Personal de la organización (no vota)' : 'Votante · correo verificado';
  $('btn-ir-panel').classList.toggle('hidden', s.rol !== 'personal');
}

/* ==========================================================================
   4. CATEGORÍAS, VOTACIONES Y DETALLE (CU-02)
   ========================================================================== */
function verCategoria(catId) {
  estado.filtroCat = catId;
  navegarA('vista-votaciones');
}

function quitarFiltro() {
  estado.filtroCat = null;
  renderVotaciones();
}

function resumenVotacion(v) {
  const mios = misComprobantes(v.id).length;
  if (mios) return mios < v.limite && v.estado === 'vivo' ? `Votaste ${mios} de ${v.limite}` : 'Ya votaste · ver comprobante';
  if (v.estado === 'prox') return `Abre el ${fmtFechaCorta(v.abre)}`;
  if (v.estado === 'pausada') return 'Pausada por la organización';
  if (v.estado === 'vivo') {
    const conteo = resultadosPublicos(v) ? ` · ${fmtNum(totalVotos(v))} votos` : ''; // RN-06
    return `Cierra el ${fmtFechaCorta(v.cierra)}${conteo}`;
  }
  return resultadosPublicos(v) ? 'Resultados publicados' : 'Resultados pendientes de publicación';
}

function renderVotaciones() {
  const cat = CATEGORIAS.find((c) => c.id === estado.filtroCat && c.publicada);
  $('filtro-activo').innerHTML = cat
    ? `<span class="filtro-chip">${esc(cat.nombre)}<button type="button" onclick="quitarFiltro()" aria-label="Quitar filtro"><i class="ph ph-x"></i></button></span>`
    : '';

  const lista = votaciones.filter((v) => categoriaDe(v).publicada && (!cat || v.cat === cat.id));
  $('lista-votaciones').innerHTML = lista.length ? lista.map((v) => {
    const [clase, texto] = ETIQUETA[v.estado];
    return `
      <button type="button" class="fila" onclick="abrirDetalle('${v.id}')">
        <div class="fila-info"><strong>${esc(v.titulo)}</strong><span>${resumenVotacion(v)}</span></div>
        <span class="badge ${clase}">${texto}</span>
      </button>`;
  }).join('') : '<p class="muted">No hay votaciones en esta categoría.</p>';
}

function abrirDetalle(id) {
  estado.votacionActual = votaciones.find((x) => x.id === id);
  navegarA('vista-detalle');
}

function textoSesion(v) {
  const s = estado.sesion;
  if (!s) return 'Sin sesión. Inicia sesión con una cuenta verificada para votar.';
  if (s.rol === 'personal') return `${s.correo} · cuenta del personal: no vota.`;
  return `${s.correo} · correo verificado. Usaste ${misComprobantes(v.id).length} de ${v.limite} ${v.limite === 1 ? 'voto' : 'votos'}.`;
}

function renderDetalle(animar) {
  const v = estado.votacionActual;
  const [clase, texto] = ETIQUETA[v.estado];
  const [visibilidad, notaVisibilidad] = VISIBILIDAD[v.visibilidad];
  $('det-titulo').textContent = v.titulo;
  $('det-sub').innerHTML = `${esc(categoriaDe(v).nombre)} <span class="badge ${clase}">${texto}</span>`;
  $('det-abre').textContent = fmtFecha(v.abre);
  $('det-cierra').textContent = fmtFecha(v.cierra);
  $('det-limite').innerHTML = `${v.limite} ${v.limite === 1 ? 'voto' : 'votos'} por persona
    <span class="dd-nota">${v.limite === 1 ? 'Valor por defecto. ' : ''}Regla pendiente de validación (P-03).</span>`;
  $('det-visibilidad').innerHTML = `${visibilidad}<span class="dd-nota">${notaVisibilidad}</span>`;
  $('det-sesion').textContent = textoSesion(v);

  const publicos = resultadosPublicos(v);
  $('det-resultados-card').classList.toggle('hidden', !publicos);
  if (publicos) {
    $('det-favorito').textContent = textoFavorito(v);
    pintarResultados($('det-resultados'), v, animar);
  }

  const s = estado.sesion;
  const botones = [];
  if (v.estado === 'vivo' && (!s || s.rol === 'votante') && votosRestantes(v) > 0) {
    botones.push(`<button type="button" class="btn btn-primary btn-block" onclick="irAOpciones()">${s ? 'Ver opciones y votar' : 'Inicia sesión para votar'}</button>`);
  }
  if (v.estado === 'prox') botones.push('<button type="button" class="btn btn-primary btn-block" disabled>Aún no abre</button>');
  if (v.estado === 'pausada') botones.push('<button type="button" class="btn btn-primary btn-block" disabled>Votación pausada</button>');
  if (misComprobantes(v.id).length) botones.push(`<button type="button" class="btn btn-ghost btn-block" onclick="mostrarResultado(estado.votacionActual)">Ver mi comprobante</button>`);
  $('det-acciones').innerHTML = botones.join('');
}

function irAOpciones() {
  const v = estado.votacionActual;
  // SERVIDOR: RN-03 (abierta y dentro de su horario), RN-04, RN-08 y RN-01 se validan de nuevo al emitir.
  if (v.estado !== 'vivo') return toast('Esta votación no está abierta.');
  if (!estado.sesion) {
    estado.irADetalle = v.id;
    toast('Inicia sesión para votar.');
    return navegarA('vista-login');
  }
  if (esPersonal()) return toast('Las cuentas del personal no votan.');
  if (votosRestantes(v) <= 0) return toast('Ya usaste todos tus votos en esta votación.');
  renderOpciones(v);
  navegarA('vista-opciones');
}

/* ==========================================================================
   5. OPCIONES (CU-03)
   ========================================================================== */
function renderOpciones(v) {
  estado.opcionElegida = null;
  $('op-titulo').textContent = v.titulo;
  // La etiqueta cubre toda la tarjeta (ver .opcion label::after en styles.css) y el botón
  // «Escuchar muestra» queda fuera de ella y por encima: tocar la tarjeta elige la opción.
  $('form-opciones').innerHTML = opcionesPublicas(v).map((o) => `
    <div class="opcion">
      <input type="radio" class="sr" id="op-${o.id}" name="opcion" value="${o.id}" onchange="elegirOpcion('${o.id}')">
      <span class="inicial" aria-hidden="true">${esc(o.nombre[0])}</span>
      <span class="opcion-info">
        <label for="op-${o.id}"><strong>${esc(o.nombre)}</strong><span class="muted">${esc(o.detalle)}</span></label>
        <button type="button" class="btn-muestra" onclick="escucharMuestra(this)"><i class="ph-fill ph-play-circle"></i><span>Escuchar muestra</span></button>
      </span>
      <span class="radio-visual" aria-hidden="true"></span>
    </div>`).join('');
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
function escucharMuestra(btn) {
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
  // PENDIENTE P-01 y P-19: PIN anti-bot por SMS. SERVIDOR: PIN de un solo uso.
  estado.pinEsperado = String(Math.floor(1000 + Math.random() * 9000));
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

  // SERVIDOR: comparar con el PIN de un solo uso (P-19).
  if ($('pin-input').value !== estado.pinEsperado) {
    const inp = $('pin-input');
    inp.classList.remove('mal'); void inp.offsetWidth; inp.classList.add('mal');
    $('err-pin').textContent = 'El PIN no coincide. Inténtalo de nuevo.';
    return;
  }
  // SERVIDOR: RN-03, la votación sigue abierta y dentro de su horario según la hora del servidor.
  if (v.estado !== 'vivo') { // el personal pudo pausarla o cerrarla mientras el panel estaba abierto
    cerrarSheet();
    toast(v.estado === 'pausada' ? 'La votación se pausó antes de emitir tu voto.' : 'La votación cerró antes de emitir tu voto.');
    return abrirDetalle(v.id);
  }
  // SERVIDOR: RN-01, no superar el límite de la votación (pendiente de validación, P-03).
  if (votosRestantes(v) <= 0) {
    cerrarSheet();
    toast('Ya usaste todos tus votos en esta votación.');
    return abrirDetalle(v.id);
  }

  btn.disabled = true;
  btn.textContent = 'Emitiendo…';

  const ahora = new Date();
  const codigo = 'VV-' + Array.from(crypto.getRandomValues(new Uint8Array(4)), (b) => b.toString(16).padStart(2, '0')).join('').toUpperCase();
  const hash = await sha256(`${codigo}|${v.id}|${o.id}|${ahora.toISOString()}`);

  o.votos += 1; // SERVIDOR: RN-02, escritura única y append-only
  const porVotacion = (estado.comprobantes[estado.sesion.correo] ??= {});
  (porVotacion[v.id] ??= []).push({
    codigo, hash, opcionId: o.id,
    fecha: ahora.toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'medium', timeZone: 'America/Bogota' })
  });

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
  const lista = misComprobantes(v.id);
  const c = lista[lista.length - 1];
  const o = v.opciones.find((x) => x.id === c.opcionId);
  $('res-resumen').textContent = `Tu voto por ${o.nombre} quedó guardado en “${v.titulo}”.`;
  $('comp-codigo').textContent = c.codigo;
  $('comp-fecha').textContent = c.fecha;
  $('comp-hash').textContent = c.hash;
  navegarA('vista-resultado');
  renderResultadosComprobante(true);
}

function renderResultadosComprobante(animar) {
  const v = estado.votacionActual;
  const publicos = resultadosPublicos(v); // RN-06
  $('res-visibilidad').textContent = publicos ? textoFavorito(v)
    : v.visibilidad === 'ceremonia' ? 'Los resultados se muestran en la ceremonia.'
    : 'Los resultados se muestran al cierre, cuando la organización los publique.';
  $('res-resultados').classList.toggle('hidden', !publicos);
  if (publicos) pintarResultados($('res-resultados'), v, animar);
}

// Opciones que aparecen en los resultados: las publicadas y activas, y las retiradas que alcanzaron a recibir votos.
const opcionesResultado = (v) => v.opciones.filter((o) => o.votos > 0 || (o.publicada && o.estado === 'activa'));

// RN-07: el voto del público elige al «favorito del público»; es consultivo y no reemplaza al jurado.
// RN-09: si hay empate, no se declara ganador hasta que decida el Comité.
function textoFavorito(v) {
  if (v.estado !== 'cerrada') return 'Conteo parcial: la votación sigue abierta.';
  const orden = opcionesResultado(v).sort((a, b) => b.votos - a.votos);
  if (!orden.length || orden[0].votos === 0) return 'Sin votos registrados.';
  if (orden[1] && orden[1].votos === orden[0].votos) return 'Empate: no se declara favorito del público hasta que decida el Comité.';
  return `Favorito del público: ${orden[0].nombre}.`;
}

function pintarResultados(cont, v, animar) {
  const opciones = opcionesResultado(v);
  const total = totalVotos(v) || 1;
  const propias = misComprobantes(v.id).map((c) => c.opcionId);

  if (animar || cont.children.length !== opciones.length) {
    cont.innerHTML = [...opciones].sort((a, b) => b.votos - a.votos).map((o) => {
      const tuyo = propias.includes(o.id) ? 'tuyo' : '';
      return `
      <div class="barra" data-id="${o.id}">
        <div class="barra-top"><span class="${tuyo}">${esc(o.nombre)}${tuyo ? ' · tu voto' : ''}</span><span class="pct"></span></div>
        <div class="barra-pista"><div class="barra-fill ${tuyo}"></div></div>
      </div>`;
    }).join('');
    cont.offsetWidth; // fuerza reflow para que el ancho se anime desde 0
  }
  opciones.forEach((o) => {
    const fila = cont.querySelector(`[data-id="${o.id}"]`);
    const pct = (o.votos / total) * 100;
    fila.querySelector('.pct').textContent = `${fmtPct(pct)} · ${fmtNum(o.votos)}`;
    fila.querySelector('.barra-fill').style.width = `${pct}%`;
  });
}

/* ==========================================================================
   8. ADMINISTRACIÓN (A1–A5). Solo personal con permiso (RN-05).
   ========================================================================== */
function registrarAuditoria(accion) {
  // SERVIDOR: RN-05, bitácora append-only con usuario, hora del servidor e IP.
  estado.auditoria.unshift({ fecha: new Date(), usuario: estado.sesion.correo, accion });
}

// Confirmación de acciones del personal (panel #confirmar-overlay)
let confirmacionPendiente = null;
let focoPrevioConfirmacion;
function confirmarAccion({ titulo, detalle, boton, peligro }, alConfirmar) {
  confirmacionPendiente = alConfirmar;
  $('conf-titulo').textContent = titulo;
  $('conf-detalle').textContent = detalle;
  const btn = $('conf-aceptar');
  btn.textContent = boton;
  btn.className = `btn ${peligro ? 'btn-danger' : 'btn-primary'} btn-block`;
  focoPrevioConfirmacion = document.activeElement;
  $('confirmar-overlay').classList.remove('hidden');
  setTimeout(() => (peligro ? $('conf-cancelar') : btn).focus(), 120); // en acciones definitivas, el foco va a Cancelar
}

function cerrarConfirmacion() {
  $('confirmar-overlay').classList.add('hidden');
  confirmacionPendiente = null;
  if (focoPrevioConfirmacion && document.contains(focoPrevioConfirmacion)) focoPrevioConfirmacion.focus();
}

async function aceptarConfirmacion() {
  const accion = confirmacionPendiente;
  cerrarConfirmacion();
  if (accion) await accion();
}

/* ---------- A1 · Panel principal ---------- */
function actualizarKpi() {
  // CU-05: monitoreo y KPI (solo personal)
  const total = votaciones.reduce((s, v) => s + totalVotos(v), 0);
  $('kpi-total').textContent = fmtNum(total);
  $('kpi-vpm').textContent = fmtNum(estado.vpm);
  $('kpi-part').textContent = fmtPct(Math.min(100, (total / PADRON) * 100));
}

function renderPanel() {
  actualizarKpi();
  // CU-06: alertas de actividad sospechosa (propuesta, P-19)
  $('alertas').innerHTML = estado.alertas.length ? estado.alertas.map((a) => `
    <div class="alerta"><i class="ph-fill ph-shield-warning" aria-hidden="true"></i>
      <span>IP ${a.ip} · ${a.nivel}<small>${a.texto}</small></span></div>`).join('')
    : '<p class="muted">Sin alertas activas.</p>';
}

/* ---------- A2 · Gestión de categorías (CU-04) ---------- */
function renderAdminCategorias() {
  $('admin-categorias').innerHTML = CATEGORIAS.map((c) => {
    const n = votaciones.filter((v) => v.cat === c.id).length;
    return `
      <div class="fila">
        <span class="cat-ico"><i class="ph-fill ${c.icono}"></i></span>
        <div class="fila-info"><strong>${esc(c.nombre)}</strong><span>${n} ${n === 1 ? 'votación' : 'votaciones'} · ${c.publicada ? 'Publicada' : 'Sin publicar'}</span></div>
        <button type="button" class="switch" id="sw-cat-${c.id}" role="switch" aria-checked="${c.publicada}" aria-label="Publicada: ${esc(c.nombre)}" onclick="alternarCategoria('${c.id}')"></button>
      </div>`;
  }).join('');
}

function alternarCategoria(id) {
  const c = CATEGORIAS.find((x) => x.id === id);
  c.publicada = !c.publicada; // RN-10: se despublica en lugar de eliminarse
  registrarAuditoria(`${c.publicada ? 'Publicó' : 'Despublicó'} la categoría «${c.nombre}».`);
  toast(`${c.nombre}: ${c.publicada ? 'publicada' : 'despublicada'}.`);
  renderAdminCategorias();
  $(`sw-cat-${id}`).focus();
}

function crearCategoria(e) {
  e.preventDefault();
  const nombre = $('cat-nombre').value.trim();
  const repetido = CATEGORIAS.some((c) => c.nombre.toLowerCase() === nombre.toLowerCase());
  // SERVIDOR: nombre único dentro de la edición.
  if (!setError('cat-nombre', 'err-cat-nombre', !nombre ? 'Escribe el nombre.' : repetido ? 'Ya existe una categoría con ese nombre.' : '')) return;
  CATEGORIAS.push({ id: nuevoId('c'), nombre, icono: 'ph-star', desc: $('cat-desc').value.trim() || 'Sin descripción', publicada: false });
  registrarAuditoria(`Creó la categoría «${nombre}» (sin publicar).`);
  e.target.reset();
  toast('Categoría creada. Publícala cuando esté lista.');
  renderAdminCategorias();
}

/* ---------- A3 · Gestión de votaciones (CU-04) ---------- */
const CAMBIOS = {
  abrir: { destino: 'vivo', boton: 'Abrir', pasado: 'Abrió', detalle: 'El público podrá votar desde este momento.' },
  pausar: { destino: 'pausada', boton: 'Pausar', pasado: 'Pausó', detalle: 'Nadie podrá votar hasta que la reanudes. Los votos emitidos se conservan.' },
  reanudar: { destino: 'vivo', boton: 'Reanudar', pasado: 'Reanudó', detalle: 'El público podrá volver a votar.' },
  cerrar: { destino: 'cerrada', boton: 'Cerrar', pasado: 'Cerró', detalle: 'Es definitivo: una votación cerrada no se puede reabrir.' }
};
// Cambios de estado permitidos. Una votación cerrada no se reabre.
const TRANSICIONES = { prox: ['abrir'], vivo: ['pausar', 'cerrar'], pausada: ['reanudar', 'cerrar'], cerrada: [] };

function renderAdminVotaciones() {
  $('vot-categoria').innerHTML = CATEGORIAS.map((c) => `<option value="${c.id}">${esc(c.nombre)}</option>`).join('');
  $('admin-votaciones').innerHTML = votaciones.map((v) => {
    const [clase, texto] = ETIQUETA[v.estado];
    const n = opcionesPublicas(v).length;
    const botones = TRANSICIONES[v.estado].map((k) => `
      <button type="button" class="btn ${k === 'cerrar' ? 'btn-danger' : 'btn-primary'} btn-sm" onclick="pedirCambioEstado('${v.id}','${k}')">${CAMBIOS[k].boton}</button>`).join('');
    return `
      <div class="fila fila-admin">
        <div class="fila-info"><strong>${esc(v.titulo)}</strong><span>${esc(categoriaDe(v).nombre)} · ${n} ${n === 1 ? 'opción publicada' : 'opciones publicadas'} · cierra el ${fmtFechaCorta(v.cierra)}</span></div>
        <span class="badge ${clase}">${texto}</span>
        <div class="fila-acciones">${botones}
          <button type="button" class="btn btn-ghost btn-sm" onclick="gestionarOpciones('${v.id}')">Opciones</button>
        </div>
      </div>`;
  }).join('');
}

function pedirCambioEstado(id, cambio) {
  const v = votaciones.find((x) => x.id === id);
  const c = CAMBIOS[cambio];
  // SERVIDOR: RN-05 (permiso) y transición permitida; RN-03 se aplica con la hora del servidor.
  if (!TRANSICIONES[v.estado].includes(cambio)) return toast('Ese cambio de estado no está permitido.');
  // SERVIDOR: RN-11, no se abre una votación con menos de dos opciones publicadas.
  if (c.destino === 'vivo' && opcionesPublicas(v).length < 2) {
    return toast('No se puede abrir: necesita al menos dos opciones publicadas (RN-11).');
  }
  confirmarAccion({ titulo: `${c.boton} «${v.titulo}»`, detalle: c.detalle, boton: `Sí, ${c.boton.toLowerCase()}`, peligro: cambio === 'cerrar' }, () => {
    v.estado = c.destino;
    registrarAuditoria(`${c.pasado} la votación «${v.titulo}».`);
    toast(`${v.titulo}: ${ETIQUETA[v.estado][1].toLowerCase()}.`);
    renderAdminVotaciones();
  });
}

function crearVotacion(e) {
  e.preventDefault();
  const titulo = $('vot-titulo').value.trim();
  const abre = $('vot-abre').value ? fecha($('vot-abre').value) : null;
  const cierra = $('vot-cierra').value ? fecha($('vot-cierra').value) : null;
  const limite = Number($('vot-limite').value);
  // SERVIDOR: repetir estas validaciones.
  const ok = [
    setError('vot-titulo', 'err-vot-titulo', titulo ? '' : 'Escribe el nombre de la votación.'),
    setError('vot-abre', 'err-vot-abre', abre ? '' : 'Elige la fecha y hora de apertura.'),
    setError('vot-cierra', 'err-vot-cierra', !cierra ? 'Elige la fecha y hora de cierre.'
      : abre && cierra <= abre ? 'El cierre debe ser posterior a la apertura.' : ''),
    setError('vot-limite', 'err-vot-limite', Number.isInteger(limite) && limite >= 1 ? '' : 'El límite debe ser un número entero mayor o igual a 1.')
  ].every(Boolean);
  if (!ok) return;

  votaciones.push(votacion({
    id: nuevoId('v'), cat: $('vot-categoria').value, titulo, estado: 'prox', abre, cierra, limite,
    visibilidad: $('vot-visibilidad').value, opciones: []
  }));
  registrarAuditoria(`Creó la votación «${titulo}» (programada, sin opciones).`);
  e.target.reset();
  toast('Votación creada. Agrega al menos dos opciones antes de abrirla.');
  renderAdminVotaciones();
}

/* ---------- A4 · Gestión de opciones o concursantes (CU-04) ---------- */
function gestionarOpciones(id) {
  estado.adminVotacion = id;
  if (document.body.dataset.vista === 'vista-admin-opciones') renderAdminOpciones();
  else navegarA('vista-admin-opciones');
}

function renderAdminOpciones() {
  const v = votaciones.find((x) => x.id === estado.adminVotacion) || votaciones[0];
  estado.adminVotacion = v.id;
  const cerrada = v.estado === 'cerrada';
  $('adm-op-votacion').innerHTML = votaciones.map((x) => `<option value="${x.id}"${x.id === v.id ? ' selected' : ''}>${esc(x.titulo)}</option>`).join('');
  $('adm-op-estado').textContent = cerrada
    ? 'Votación cerrada: sus opciones ya no se modifican.'
    : `${opcionesPublicas(v).length} publicadas y activas. Para abrir la votación se necesitan al menos dos.`;
  $('admin-opciones').innerHTML = v.opciones.length ? v.opciones.map((o) => {
    const retirada = o.estado === 'retirada';
    const controles = retirada || cerrada ? '' : `
        <button type="button" class="switch" id="sw-op-${o.id}" role="switch" aria-checked="${o.publicada}" aria-label="Publicada: ${esc(o.nombre)}" onclick="alternarOpcion('${o.id}')"></button>
        <div class="fila-acciones"><button type="button" class="btn btn-ghost btn-sm" onclick="pedirRetiroOpcion('${o.id}')">Retirar</button></div>`;
    return `
      <div class="fila fila-admin">
        <span class="inicial" aria-hidden="true">${esc(o.nombre[0])}</span>
        <div class="fila-info"><strong>${esc(o.nombre)}</strong><span>${esc(o.detalle)}<br>${retirada ? 'Retirada' : 'Activa'} · ${o.publicada ? 'Publicada' : 'Sin publicar'}</span></div>
        ${controles}
      </div>`;
  }).join('') : '<p class="muted">Esta votación aún no tiene opciones.</p>';
  $('bloque-nueva-opcion').classList.toggle('hidden', cerrada);
}

const votacionAdmin = () => votaciones.find((x) => x.id === estado.adminVotacion);

function alternarOpcion(oid) {
  const v = votacionAdmin();
  const o = v.opciones.find((x) => x.id === oid);
  o.publicada = !o.publicada;
  registrarAuditoria(`${o.publicada ? 'Publicó' : 'Despublicó'} la opción «${o.nombre}» en «${v.titulo}».`);
  toast(`${o.nombre}: ${o.publicada ? 'publicada' : 'despublicada'}.`);
  renderAdminOpciones();
  $(`sw-op-${oid}`).focus();
}

function pedirRetiroOpcion(oid) {
  const v = votacionAdmin();
  const o = v.opciones.find((x) => x.id === oid);
  confirmarAccion({
    titulo: `Retirar «${o.nombre}»`,
    detalle: 'Deja de mostrarse al público. Sus votos se conservan: una opción con votos no se elimina.',
    boton: 'Sí, retirar',
    peligro: true
  }, () => {
    o.estado = 'retirada'; // RN-10
    registrarAuditoria(`Retiró la opción «${o.nombre}» de «${v.titulo}».`);
    toast(`${o.nombre}: retirada.`);
    renderAdminOpciones();
  });
}

function crearOpcion(e) {
  e.preventDefault();
  const v = votacionAdmin();
  const nombre = $('nop-nombre').value.trim();
  if (!setError('nop-nombre', 'err-nop-nombre', nombre ? '' : 'Escribe el nombre.')) return;
  v.opciones.push({ ...opcion(nuevoId('o'), nombre, $('nop-detalle').value.trim() || 'Sin detalle', 0), publicada: false });
  registrarAuditoria(`Agregó la opción «${nombre}» a «${v.titulo}» (sin publicar).`);
  e.target.reset();
  toast('Opción agregada. Publícala cuando esté lista.');
  renderAdminOpciones();
}

/* ---------- A5 · Resultados y auditoría (CU-05, CU-06) ---------- */
const PASOS = {
  conciliar: { boton: 'Conciliar conteo', pasado: 'Concilió', detalle: 'Compara el conteo con los votos registrados. Demo: siempre coincide.' },
  sellar: { boton: 'Sellar resultados', pasado: 'Selló', detalle: 'Genera un hash SHA-256 de los resultados. Después del sello no cambian.' },
  publicar: { boton: 'Publicar resultados', pasado: 'Publicó', detalle: 'Los resultados quedarán visibles para el público. Pendiente P-06: falta definir quién autoriza publicar.' }
};

function pasosPublicacion(v) {
  const pasos = [
    ['Conciliada', v.conciliada && `${fmtNum(v.conciliada.total)} votos, sin diferencias`],
    ['Sellada', v.sello && `Sello ${v.sello.slice(0, 16)}…`],
    ['Publicada', v.publicada && 'Visible para el público']
  ];
  const siguiente = !v.conciliada ? 'conciliar' : !v.sello ? 'sellar' : !v.publicada ? 'publicar' : null;
  return `
    <ol class="pasos">${pasos.map(([nombre, hecho]) => `
      <li class="${hecho ? 'hecho' : ''}"><i class="${hecho ? 'ph-fill ph-check-circle' : 'ph ph-circle'}" aria-hidden="true"></i>
        <span>${nombre}${hecho ? `<small>${hecho}</small>` : ' · pendiente'}</span></li>`).join('')}
    </ol>
    ${siguiente ? `<button type="button" class="btn btn-primary btn-block" style="margin-top:1rem" onclick="pedirPaso('${v.id}','${siguiente}')">${PASOS[siguiente].boton}</button>` : ''}`;
}

function renderAdminResultados() {
  const lista = votaciones.filter((v) => v.estado !== 'prox');
  $('admin-resultados').innerHTML = lista.map((v) => {
    const [clase, texto] = ETIQUETA[v.estado];
    const nota = v.estado === 'cerrada' ? textoFavorito(v)
      : resultadosPublicos(v) ? 'Visible para el público (en vivo, P-05).'
      : 'Conteo interno: el público no lo ve mientras esté abierta (RN-06).';
    return `
      <div class="card">
        <div class="resultado-cab"><strong>${esc(v.titulo)}</strong><span class="badge ${clase}">${texto}</span></div>
        <p class="muted" style="margin:0.25rem 0 0.75rem"><span id="adm-total-${v.id}">${fmtNum(totalVotos(v))}</span> votos · ${esc(nota)}</p>
        <div id="adm-res-${v.id}"></div>
        ${v.estado === 'cerrada' ? pasosPublicacion(v) : ''}
      </div>`;
  }).join('') || '<p class="muted">Todavía no hay votaciones abiertas ni cerradas.</p>';
  lista.forEach((v) => pintarResultados($(`adm-res-${v.id}`), v, true));

  $('admin-auditoria').innerHTML = estado.auditoria.length ? estado.auditoria.map((a) => `
    <div class="fila"><div class="fila-info"><strong>${esc(a.accion)}</strong><span>${fmtFecha(a.fecha)} · ${esc(a.usuario)}</span></div></div>`).join('')
    : '<p class="muted">Aún no hay acciones registradas.</p>';
}

function actualizarResultadosAdmin() {
  votaciones.filter((v) => v.estado === 'vivo' && $(`adm-res-${v.id}`)).forEach((v) => {
    $(`adm-total-${v.id}`).textContent = fmtNum(totalVotos(v));
    pintarResultados($(`adm-res-${v.id}`), v, false);
  });
}

function pedirPaso(id, paso) {
  const v = votaciones.find((x) => x.id === id);
  const p = PASOS[paso];
  const empate = paso === 'publicar' && textoFavorito(v).startsWith('Empate')
    ? ' Hay empate: no se declarará favorito del público hasta que decida el Comité (RN-09).' : '';
  confirmarAccion({ titulo: `${p.boton}: «${v.titulo}»`, detalle: p.detalle + empate, boton: `Sí, ${p.boton.split(' ')[0].toLowerCase()}`, peligro: false }, async () => {
    if (paso === 'conciliar') v.conciliada = { total: totalVotos(v), fecha: new Date() }; // SERVIDOR: comparar con la tabla de votos
    if (paso === 'sellar') v.sello = await sha256(JSON.stringify({ id: v.id, votos: v.opciones.map((o) => [o.id, o.votos]), total: v.conciliada.total })); // SERVIDOR: firmar y guardar el sello
    if (paso === 'publicar') v.publicada = true; // SERVIDOR: PENDIENTE P-06, quién autoriza publicar
    registrarAuditoria(`${p.pasado} los resultados de «${v.titulo}».`);
    toast(`${v.titulo}: ${p.pasado.toLowerCase()}.`);
    renderAdminResultados();
  });
}

/* ==========================================================================
   9. SIMULACIÓN EN VIVO (votos entrantes y KPI)
   ========================================================================== */
function simularVotosEntrantes() {
  let nuevos = 0;
  votaciones.filter((v) => v.estado === 'vivo').forEach((v) => {
    const activas = opcionesPublicas(v);
    if (!activas.length) return;
    const o = activas[Math.floor(Math.random() * activas.length)];
    const n = Math.floor(Math.random() * 6) + 1;
    o.votos += n; nuevos += n;
  });
  estado.vpm = Math.round(nuevos * 24 * (0.8 + Math.random() * 0.4)); // 2,5 s → por minuto
  const vista = document.body.dataset.vista;
  const v = estado.votacionActual;
  if (vista === 'vista-admin') actualizarKpi();
  if (vista === 'vista-admin-resultados') actualizarResultadosAdmin();
  // Solo se actualizan los resultados que el público puede ver (RN-06, P-05)
  if (vista === 'vista-detalle' && resultadosPublicos(v)) pintarResultados($('det-resultados'), v, false);
  if (vista === 'vista-resultado' && resultadosPublicos(v)) pintarResultados($('res-resultados'), v, false);
}

/* ==========================================================================
   10. ARRANQUE
   ========================================================================== */
document.addEventListener('DOMContentLoaded', () => {
  renderCategorias();
  tickCuentaRegresiva();
  setInterval(tickCuentaRegresiva, 1000);
  setInterval(simularVotosEntrantes, 2500);

  // Solo vistas "seguras" por hash; detalle, opciones y resultado exigen estado previo.
  // Las de administración pasan por el control de navegarA (RN-05).
  const hash = location.hash.replace('#', '');
  const permitidas = ['vista-inicio', 'vista-registro', 'vista-login', 'vista-categorias', 'vista-votaciones', ...VISTAS_ADMIN];
  navegarA(permitidas.includes(hash) ? hash : 'vista-inicio');

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!$('confirmar-overlay').classList.contains('hidden')) cerrarConfirmacion();
    else if (!$('sheet-overlay').classList.contains('hidden')) cerrarSheet();
  });
});
