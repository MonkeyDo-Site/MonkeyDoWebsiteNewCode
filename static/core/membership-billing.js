(() => {
  for (const input of document.querySelectorAll('.renewal-link-copy')) input.addEventListener('focus', () => input.select());
  const form = document.querySelector('[data-installment-payment]');
  if (!form) return;
  const field = name => form.elements.namedItem(name);
  const button = form.querySelector('[data-installment-confirm]');
  const error = form.querySelector('[data-installment-error]');
  let sequence = 0, timer, total = '';
  function display() {
    const tender = field('tender').value;
    form.querySelector('[data-membership-zelle-date]').hidden = tender !== 'zelle';
    form.querySelector('[data-membership-manual]').hidden = tender === 'card';
    form.querySelector('[data-membership-receipt-label]').textContent = tender === 'gift_card'
      ? 'The physical gift card has been presented and verified for this amount.'
      : tender === 'zelle' ? 'I verified this Zelle payment in the business bank account.'
      : 'I confirm this payment was received.';
    button.disabled = !field('reviewed').value || (tender !== 'card' && !field('verified_received').checked);
    button.textContent = tender === 'card' ? `Charge membership card${total ? ' — $' + total : ''}`
      : `Record ${tender.replace('_', ' ')} received${total ? ' — $' + total : ''}`;
    if (!error.hidden && !field('reviewed').value) button.textContent = 'Review payment details first';
  }
  async function preview() {
    const current = ++sequence;
    const data = new FormData(form);
    data.set('action', 'payment_preview');
    if (field('tender').value !== 'zelle') data.set('received_on', '');
    try {
      const response = await fetch(location.href, {method: 'POST', body: data, credentials: 'same-origin', headers: {'X-CSRFToken': field('csrfmiddlewaretoken').value}});
      const result = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Review the current installment before confirming.');
      form.querySelector('[data-installment-quote]').innerHTML = result.html;
      field('reviewed').value = result.fingerprint;
      total = result.total;
      error.hidden = true;
    } catch (failure) {
      if (current !== sequence) return;
      field('reviewed').value = '';
      error.textContent = failure.message || 'The payment amount could not be loaded.';
      error.hidden = false;
    }
    display();
  }
  form.addEventListener('change', event => {
    if (event.target.name === 'verified_received') {display(); return;}
    field('reviewed').value = '';
    field('verified_received').checked = false;
    if (field('tender').value !== 'zelle') field('received_on').value = '';
    total = '';
    ++sequence;
    display();
    clearTimeout(timer);
    timer = setTimeout(preview, 150);
  });
  form.addEventListener('submit', event => {
    if (button.disabled) event.preventDefault();
    else button.setAttribute('aria-busy', 'true');
  });
  // Keep the normal overview compact; opening the controls loads their live amount.
  const details = document.querySelector('[data-membership-billing]');
  details.addEventListener('toggle', () => {if (details.open && !field('reviewed').value) preview();});
  display();
  if (details.open) preview();
})();
