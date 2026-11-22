const checkpoint = document.querySelector('[data-booking-history]');
if (checkpoint?.dataset.flow && checkpoint?.dataset.step) {
  const url = new URL(window.location.href);
  url.searchParams.set('step', checkpoint.dataset.step);
  url.searchParams.set('flow', checkpoint.dataset.flow);
  window.history.replaceState(null, '', url);
}
// Revalidate session state when a browser restores a cached sensitive form.
window.addEventListener('pageshow', event => {
  if (event.persisted && document.querySelector('[name=wizard_key]')) window.location.reload();
});
for (const form of document.querySelectorAll('[data-waiver-choices]')) {
  const sign = form.querySelector('[name=sign_now]');
  const next = form.querySelector('[data-waiver-continue]');
  const sync = () => {
    form.querySelector('[data-sign-waiver]').disabled = !sign.checked;
    if (next) next.disabled = sign.checked;
  };
  sign.addEventListener('change', sync);
  sync();
}
