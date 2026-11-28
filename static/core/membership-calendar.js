(() => {
  const form = document.querySelector('[data-calendar-correction]');
  if (!form) return;
  const reviewed = form.querySelector('[name="calendar-reviewed"]');
  const accepted = form.querySelector('[name="calendar-customer_confirmed"]');
  const ownerApproved = form.querySelector('[name="calendar-owner_approved"]');
  const acknowledgment = form.querySelector('[data-calendar-acknowledgment]');
  const button = form.querySelector('[data-calendar-confirm]');
  const quote = form.querySelector('[data-calendar-quote]');
  const error = form.querySelector('[data-calendar-error]');
  const inputs = [...form.querySelectorAll('[data-calendar-input]')];
  const snapshot = () => JSON.stringify(inputs.map(input => [input.name, input.value]));
  let lastInputs = snapshot();
  let timer, sequence = 0;
  async function update() {
    const current = ++sequence, data = new FormData(form);
    data.set('action', 'calendar_review'); data.set('format', 'json');
    try {
      const response = await fetch(location.href, {method: 'POST', body: data, credentials: 'same-origin'});
      if (!(response.headers.get('Content-Type') || '').includes('application/json')) {
        throw new Error('The dates could not be reviewed. Refresh the page and try again.');
      }
      const result = await response.json();
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Review the corrected dates.');
      quote.innerHTML = result.html; reviewed.value = result.fingerprint;
      ownerApproved.value = result.owner_approved ? 'True' : '';
      acknowledgment.textContent = result.acknowledgment;
      accepted.checked = false; accepted.disabled = false;
      button.disabled = false; error.hidden = true;
    } catch (failure) {
      if (current !== sequence) return;
      button.disabled = true; reviewed.value = ''; ownerApproved.value = '';
      accepted.checked = false; accepted.disabled = true;
      error.textContent = failure.message || 'Could not refresh the dates. Please try again.';
      error.hidden = false;
    }
  }
  function changed(event) {
    if (!event.target.matches('[data-calendar-input]')) return;
    const currentInputs = snapshot();
    if (currentInputs === lastInputs) return;
    lastInputs = currentInputs;
    ++sequence; reviewed.value = ''; ownerApproved.value = ''; accepted.checked = false; button.disabled = true;
    accepted.disabled = true;
    clearTimeout(timer); timer = setTimeout(update, 200);
  }
  form.addEventListener('input', changed); form.addEventListener('change', changed);
  form.addEventListener('submit', event => {
    if (event.submitter?.value === 'calendar_review') return;
    if (!reviewed.value || !accepted.checked) {
      event.preventDefault(); error.textContent = 'Review the current dates and confirm the customer agreed.'; error.hidden = false;
    }
  });
  accepted.disabled = !reviewed.value;
})();
