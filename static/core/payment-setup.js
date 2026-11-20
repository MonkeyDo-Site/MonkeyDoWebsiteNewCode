/* Provider-owned card fields only. Never send PAN/CVV, masked CVV or expiry to storage. */
for (const section of document.querySelectorAll('[data-card-setup]')) {
  const form = section.querySelector('[data-card-form]');
  if (!form) continue;
  const status = section.querySelector('[data-card-status]');
  const button = form.querySelector('[data-save-card]');
  const check = form.querySelector('[data-check-card]');
  const confirmedChoice = document.querySelector('#customer-booking-form input[name="payment_consent"]');
  let statusUrl = section.dataset.statusUrl;
  const showSaved = data => {
    status.textContent = `Saved payment method ending in ${data.last_four}. No admission payment has been collected.`;
    const summary = document.querySelector('[data-selected-card]');
    if (summary) summary.textContent = status.textContent;
    button.disabled = true;
    if (confirmedChoice) confirmedChoice.value = data.consent_id;
    form.elements.request_key.value = crypto.randomUUID();
    check.hidden = true;
    section.dispatchEvent(new CustomEvent('card-setup-saved', {bubbles: true}));
  };
  const recover = async () => {
    if (!statusUrl) return false;
    check.hidden = false;
    const response = await fetch(statusUrl, {headers: {'Accept': 'application/json'}});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error();
    const data = await response.json();
    if (response.ok && data.state === 'saved') { showSaved(data); return true; }
    if (response.status === 404) { button.disabled = false; check.hidden = true; return false; }
    button.disabled = true;
    status.textContent = data.error || 'Card setup still needs review. Please call/text 848-238-5147.';
    return false;
  };
  check.addEventListener('click', () => recover().catch(() => {
    status.textContent = 'We could not confirm card setup. Please call/text 848-238-5147.';
  }));
  let hosted;
  try {
    const key = JSON.parse(document.querySelector('#card-tokenization-key').textContent);
    hosted = new window.HostedTokenization(key, {target: '#provider-card-frame'});
  } catch {
    status.textContent = 'Secure card entry is unavailable. Please call/text 848-238-5147.';
  }
  const sync = () => { section.querySelector('[data-new-card]').hidden = form.elements.method.value !== 'new'; };
  form.addEventListener('change', () => {
    sync();
    if (confirmedChoice) confirmedChoice.value = '';
    button.disabled = false;
    statusUrl = '';
    check.hidden = true;
  });
  sync();
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    button.disabled = true;
    status.textContent = 'Saving secure card setup…';
    try {
      const payload = {
        wizard_key: form.elements.wizard_key.value,
        wizard_stage: form.elements.wizard_stage.value,
        policy_version: form.elements.policy_version.value,
        agree_payment: form.elements.agree_payment.checked,
        agree_cancellation: form.elements.agree_cancellation.type === 'hidden' ? form.elements.agree_cancellation.value === '1' : form.elements.agree_cancellation.checked
      };
      if (form.elements.method.value === 'new') {
        if (!hosted) throw new Error();
        const surcharge = await hosted.getSurcharge();
        if (surcharge.surcharge && Number(surcharge.surcharge.value) !== 0) {
          status.textContent = 'The payment provider has an additional surcharge configured. Please contact MonkeyDo before continuing.';
          return;
        }
        const result = await hosted.getNonceToken();
        Object.assign(payload, {
          request_key: form.elements.request_key.value,
          nonce: result.nonce.startsWith('nonce-') ? result.nonce : `nonce-${result.nonce}`,
          expiry_month: result.expiryMonth,
          expiry_year: result.expiryYear,
          retain: form.elements.retain.checked
        });
        statusUrl = `${section.dataset.statusPrefix}${form.elements.request_key.value}/`;
      } else payload.method = form.elements.method.value;
      const response = await fetch(section.dataset.endpoint, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value},
        body: JSON.stringify(payload)
      });
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error();
      const data = await response.json();
      if (response.ok && data.state === 'saved') {
        showSaved(data);
      } else {
        status.textContent = data.error || 'Card setup needs assistance. Please call/text 848-238-5147.';
        if (response.status === 202) { check.hidden = false; button.disabled = true; }
        else button.disabled = false;
      }
    } catch {
      status.textContent = 'We could not confirm card setup. Please call/text 848-238-5147 before trying again.';
      check.hidden = !statusUrl;
      button.disabled = true;
      try { await recover(); } catch { /* Keep unknown setup blocked; no second exchange. */ }
    }
  });
  if (statusUrl) {
    button.disabled = true;
    recover().catch(() => { check.hidden = false; status.textContent = 'Please check card setup before continuing.'; });
  }
}
