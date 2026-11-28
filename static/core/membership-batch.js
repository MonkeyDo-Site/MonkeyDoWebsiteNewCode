(() => {
  const form = document.querySelector('[data-renewal-batch]');
  if (!form) return;
  const quote = form.querySelector('[data-batch-quote]');
  const error = form.querySelector('[data-batch-error]');
  const button = form.querySelector('[data-batch-confirm]');
  const reviewed = form.querySelector('[name="reviewed"]');
  const accepted = form.querySelector('[name="accepted"]');
  const verified = form.querySelector('[name="verified_received"]');
  let timer, sequence = 0;
  function cards() {
    const bank = form.querySelector('[data-batch-bank]');
    if (bank) bank.hidden = form.querySelector('[name="tender"]').value !== 'zelle';
    const label = form.querySelector('[data-batch-verified-label]');
    if (label) label.textContent = form.querySelector('[name="tender"]').value === 'zelle'
      ? 'I verified the full transfer shown in the business bank account.'
      : 'I verified that the full payment shown was actually received.';
    form.querySelectorAll('.renewal-batch-row').forEach(row => {
      const monthly = row.querySelector('[name$="-billing"]').value === 'monthly';
      row.querySelector('[data-renewal-options]').hidden = !row.querySelector('[name$="-renew"]').checked;
      row.querySelector('[data-batch-card]').hidden = !monthly;
    });
  }
  async function update() {
    const current = ++sequence;
    const data = new FormData(form);
    data.set('action', 'review'); data.set('format', 'json');
    try {
      const response = await fetch(form.getAttribute('action') || location.href, {method: 'POST', body: data, credentials: 'same-origin'});
      let result;
      try { result = await response.json(); }
      catch { throw new Error('Could not refresh the total. Please try again.'); }
      if (current !== sequence) return;
      if (!response.ok) throw new Error(result.error || 'Please review the renewal details.');
      quote.innerHTML = result.html; reviewed.value = result.fingerprint;
      button.textContent = result.button; button.disabled = false;
      error.textContent = ''; error.hidden = true;
    } catch (failure) {
      if (current !== sequence) return;
      reviewed.value = ''; button.disabled = true;
      error.textContent = failure.message || 'Could not refresh the total. Please try again.';
      error.hidden = false;
    }
  }
  function changed(event) {
    if (!event.target.matches('[data-batch-input]')) return;
    ++sequence; reviewed.value = ''; accepted.checked = false; verified.checked = false;
    button.disabled = true; cards(); clearTimeout(timer); timer = setTimeout(update, 200);
  }
  form.addEventListener('click', event => {
    const split = event.target.closest('[data-batch-split]');
    if (!split) return;
    const total = form.querySelector('[name="renewals-TOTAL_FORMS"]');
    const index = Number(total.value);
    if (index >= 100) return;
    const row = split.closest('.renewal-batch-row');
    const copy = row.cloneNode(true);
    copy.querySelectorAll('[name], [id], label[for]').forEach(field => {
      ['name', 'id', 'for'].forEach(attr => {
        if (field.hasAttribute(attr)) field.setAttribute(attr, field.getAttribute(attr).replace(/renewals-\d+-/g, `renewals-${index}-`));
      });
    });
    row.querySelector('[name$="-renew"]').checked = true;
    const count = row.querySelector('[name$="-places"]');
    count.value = Math.max(1, Number(count.value) - 1);
    copy.querySelector('[name$="-places"]').value = '1';
    const selected = copy.querySelector('[name$="-renew"]');
    selected.checked = true;
    row.after(copy); total.value = String(index + 1);
    changed({target: selected});
  });
  form.addEventListener('change', changed);
  form.addEventListener('input', changed);
  form.addEventListener('submit', event => {
    if (event.submitter?.value !== 'confirm') return;
    if (!reviewed.value || !accepted.checked || !verified.checked) {
      event.preventDefault(); error.textContent = 'Accept the reviewed terms and verify the full received payment before confirming.'; error.hidden = false;
    }
  });
  cards();
})();
