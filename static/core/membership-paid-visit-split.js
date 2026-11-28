(() => {
  const form = document.querySelector('[data-paid-visit-split]');
  if (!form) return;
  const field = name => form.elements.namedItem('paid-visit-split-' + name);
  const button = form.querySelector('[data-split-confirm]');
  const quote = form.querySelector('[data-split-quote]');
  const error = form.querySelector('[data-split-error]');
  const label = form.querySelector('[data-split-received-label]');
  let timer, sequence = 0;
  function controls() {
    const zelle = field('tender').value === 'zelle';
    form.querySelectorAll('[data-split-zelle]').forEach(box => {
      box.hidden = !zelle;
      box.querySelectorAll('input').forEach(input => { input.disabled = !zelle; });
    });
    label.textContent = zelle
      ? 'I verified this exact Zelle transfer in the bank account. It has not already been recorded elsewhere.'
      : field('tender').value === 'gift_card'
        ? 'I verified the physical gift card and applied exactly the amount shown to this membership.'
        : 'I verified the exact cash/check amount shown was received and has not already been recorded.';
  }
  async function update() {
    const current = ++sequence, data = new FormData(form);
    data.set('action', 'paid_visit_split_review'); data.set('format', 'json');
    try {
      const response = await fetch(location.href, {method: 'POST', body: data, credentials: 'same-origin'});
      if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
        throw new Error('The payment could not be reviewed. Refresh the page and try again.');
      }
      const result = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Review the split-payment details.');
      quote.innerHTML = result.html; field('reviewed').value = result.fingerprint;
      button.textContent = `Record ${result.tender_label || result.tender} and request card — $${result.card_total}`;
      button.disabled = false; error.hidden = true;
    } catch (failure) {
      if (current !== sequence) return;
      field('reviewed').value = ''; button.disabled = true;
      error.textContent = failure.message || 'Could not review this payment. Please try again.';
      error.hidden = false;
    }
  }
  function changed(event) {
    if (!event.target.matches('[data-paid-visit-split-input]')) return;
    ++sequence; field('reviewed').value = ''; button.disabled = true;
    field('verified_received').checked = false; field('card_authorized').checked = false;
    controls(); clearTimeout(timer); timer = setTimeout(update, 200);
  }
  form.addEventListener('input', changed); form.addEventListener('change', changed);
  form.addEventListener('submit', event => {
    if (event.submitter?.value === 'paid_visit_split_review') return;
    if (!field('reviewed').value || !field('verified_received').checked || !field('card_authorized').checked) {
      event.preventDefault(); error.textContent = 'Review the current amounts, verify the received payment and confirm the customer authorizes the remaining card amount.';
      error.hidden = false;
    }
  });
  controls();
  if (field('manual_amount').value && !field('reviewed').value) {
    field('verified_received').checked = false; field('card_authorized').checked = false;
    update();
  }
})();
