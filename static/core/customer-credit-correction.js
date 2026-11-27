/* Read-only review; a final explicit POST appends the owner correction. */
(() => {
  const form = document.querySelector('[data-credit-correction]'); if (!form) return;
  const field = name => form.elements[name], button = form.querySelector('[data-correction-confirm]'), error = form.querySelector('[data-correction-error]'), retry = form.querySelector('[data-correction-retry]');
  const original = form.querySelector('[data-correction-original]');
  const visible = () => { original.hidden = field('kind').value !== 'restore'; if (original.hidden) field('original').value = ''; };
  visible();
  const selection = () => JSON.stringify([field('kind').value, field('value').value, field('original').value]);
  let generation = 0, timer, last = selection();
  button.disabled = !field('reviewed').value;
  const preview = async () => {
    const current = ++generation, data = new FormData(form); data.set('action', 'credit_correction_preview');
    try {
      const response = await fetch(location.href, {method:'POST', body:data, headers:{'X-CSRFToken':field('csrfmiddlewaretoken').value, Accept:'application/json'}, cache:'no-store'});
      const result = await response.json(); if (current !== generation) return;
      if (!response.ok) throw new Error(result.error || 'Review the credit correction.');
      form.querySelector('[data-correction-review]').innerHTML = result.html;
      field('reviewed').value = result.fingerprint;
      button.textContent = `${result.kind === 'restore' ? 'Restore' : 'Remove'} customer credit — $${result.amount}`;
      error.hidden = true; retry.hidden = true; button.disabled = false;
    } catch (failure) {
      if (current !== generation) return;
      error.textContent = failure instanceof SyntaxError || failure instanceof TypeError ? 'The credit review could not be loaded. Please try again.' : failure.message;
      error.hidden = false; retry.hidden = false; button.disabled = true;
    }
  };
  const changed = () => {
    visible(); const next = selection(); if (next === last) return;
    last = next; ++generation; field('reviewed').value = ''; button.disabled = true; retry.hidden = true; clearTimeout(timer);
    if (field('value').value && (field('kind').value !== 'restore' || field('original').value)) timer = setTimeout(preview, 180);
  };
  form.addEventListener('input', changed); form.addEventListener('change', changed);
  retry.addEventListener('click', () => { button.disabled = true; preview(); });
  form.addEventListener('submit', event => { if (button.disabled) event.preventDefault(); });
})();
