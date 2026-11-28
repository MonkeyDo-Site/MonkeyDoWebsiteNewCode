(() => {
  'use strict';
  const form = document.querySelector('[data-paid-visit-receipt]');
  if (!form) return;
  const tender = form.elements.tender;
  const bank = form.querySelector('[data-paid-visit-bank]');
  const verification = form.querySelector('[data-paid-visit-receipt-label]');
  function update() {
    const zelle = tender.value === 'zelle';
    bank.hidden = !zelle;
    if (zelle && !form.elements.received_on.value) form.elements.received_on.value = form.elements.received_on.max;
    bank.querySelectorAll('input').forEach(input => {
      input.disabled = !zelle;
      input.required = zelle;
    });
    verification.textContent = tender.value === 'gift_card'
      ? 'I physically checked the gift card and verified that this amount was received.'
      : zelle ? 'I checked the bank and verified that this Zelle payment was received.'
        : 'I verified that this exact payment was actually received.';
  }
  tender.addEventListener('change', update);
  update();
})();
