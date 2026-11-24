/* Bring server-returned validation into view without moving while normal inputs update. */
(() => {
  let lastError;
  const reveal = () => {
    const error = [...document.querySelectorAll('.errorlist, [role="alert"]')]
      .find(node => node.textContent.trim() && node.getClientRects().length && !node.closest('[hidden], dialog:not([open])'));
    if (!error || error === lastError) return;
    lastError = error;
    error.setAttribute('tabindex', '-1');
    error.focus({preventScroll: true});
    error.scrollIntoView({block: 'center', behavior: 'instant'});
  };
  requestAnimationFrame(reveal);
  new MutationObserver(() => requestAnimationFrame(reveal)).observe(document.querySelector('main') || document.body,
    {childList: true, subtree: true, attributes: true, attributeFilter: ['role']});
  // Let the page scroll normally; wheel movement must never change a focused number.
  document.addEventListener('wheel', event => {
    if (event.target instanceof HTMLInputElement && event.target.type === 'number' && document.activeElement === event.target) event.target.blur();
  }, {passive: true, capture: true});
})();
