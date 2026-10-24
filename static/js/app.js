/**
 * Comportamientos de interfaz (de prototipo/app.js). Los datos y las reglas ya no viven aquí:
 * vienen de MySQL a través de las vistas de Django.
 */

// Cuenta regresiva hasta la fecha indicada en data-hasta (formato ISO con zona horaria)
function iniciarCuentaRegresiva(contenedor) {
  const hasta = new Date(contenedor.dataset.hasta);
  const campos = ['dias', 'horas', 'min', 'seg'].map((k) => contenedor.querySelector(`[data-cd="${k}"]`));
  const p = (n) => String(n).padStart(2, '0');
  const tick = () => {
    let ms = Math.max(0, hasta - Date.now());
    const valores = [Math.floor(ms / 864e5), Math.floor((ms %= 864e5) / 36e5), Math.floor((ms %= 36e5) / 6e4), Math.floor((ms % 6e4) / 1000)];
    campos.forEach((c, i) => { c.textContent = p(valores[i]); });
  };
  tick();
  setInterval(tick, 1000);
}

// Los mensajes de Django se muestran como toast y desaparecen solos
function ocultarToasts() {
  document.querySelectorAll('.toast').forEach((t, i) => {
    setTimeout(() => t.classList.add('oculto'), 4000 + i * 600);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-hasta]').forEach(iniciarCuentaRegresiva);
  ocultarToasts();
});
