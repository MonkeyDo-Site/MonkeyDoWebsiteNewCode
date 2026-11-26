/* Card fields belong to Banquest. Never read or store their raw values. */
for (const section of document.querySelectorAll('[data-card-setup]')) {
  const form = section.querySelector('[data-card-form]');
  if (!form) continue;
  const status = section.querySelector('[data-card-status]');
  const replacement = section.dataset.singleReplace === '1';
  const single = section.dataset.singleConfirm === '1' || replacement;
  const actionLabel = replacement ? 'Save and use this card' : 'Confirm booking';
  const confirmationForm = single ? document.querySelector('#customer-booking-form') : null;
  const button = single ? document.querySelector('[data-confirm-booking]') : document.querySelector('[data-payment-save]') || form.querySelector('[data-save-card]');
  const confirm = document.querySelector('[data-confirm-booking]');
  const publicStatus = document.querySelector('[data-public-card-status]');
  const check = form.querySelector('[data-check-card]');
  const confirmedChoice = document.querySelector('#customer-booking-form input[name="payment_consent"]');
  let statusUrl = section.dataset.statusUrl;
  let uncertain = false;
  let confirmRequested = false;
  let finishing = false;
  const processing = (active, label = actionLabel) => {
    if (!single) return;
    button.querySelector('[data-confirm-label]').textContent = label;
    button.querySelector('.processing-dots').hidden = !active;
    button.setAttribute('aria-busy', String(active));
    form.inert = active;
  };
  const finish = () => {
    if (!single || !confirmRequested) return;
    if (!confirmationForm.reportValidity()) {
      confirmRequested = false;
      processing(false);
      button.disabled = false;
      return;
    }
    finishing = true;
    processing(true, replacement ? 'Updating booking card' : 'Confirming booking');
    button.disabled = true;
    // A ready saved card may finish inside this form's submit event. A second
    // requestSubmit in the same event is ignored by browsers; submit on the next task.
    window.setTimeout(() => confirmationForm.requestSubmit(), 0);
  };
  const report = message => {
    const target = publicStatus || status;
    if (!target) return;
    const error = !['Your card is saved', 'Save your', 'Saving', 'Card will', 'Your card will', 'Confirming'].some(prefix => message.startsWith(prefix));
    target.textContent = single && error ? (replacement ? 'The booking card has not been changed. ' : 'Your booking is not confirmed. ') + message : message;
    if (single && error && uncertain) {
      target.append(' ', check);
      check.hidden = false;
    }
    target.classList.toggle('card-error', error);
    target.setAttribute('role', error ? 'alert' : 'status');
    if (single && error) {
      confirmRequested = false;
      processing(false);
      target.setAttribute('tabindex', '-1');
      target.focus({preventScroll: true});
      target.scrollIntoView({block: 'center', behavior: 'instant'});
    }
  };
  const invalidate = () => {
    if (confirmedChoice) confirmedChoice.value = '';
    if (confirm) confirm.disabled = true;
    section.dataset.ready = '0';
    const summary = document.querySelector('[data-selected-card]');
    if (summary) summary.hidden = true;
    if (confirm) confirm.classList.remove('confirm-ready', 'confirm-attention');
  };
  const showSaved = data => {
    report(single ? (confirmRequested ? (replacement ? 'Confirming this booking’s card selection…' : 'Confirming your booking… Your booking is not confirmed yet.') : (replacement ? 'Your card is saved. Click Save and use this card to finish updating this booking.' : 'Your card is saved. Click Confirm booking to finish your reservation.')) : 'Your card is saved. Click Confirm booking to finish your reservation.');
    const summary = document.querySelector('[data-selected-card]');
    if (summary) {
      summary.textContent = `Saved payment method ending in ${data.last_four}. No admission payment has been collected.`;
      summary.hidden = false;
    }
    button.disabled = true;
    if (confirmedChoice) confirmedChoice.value = data.consent_id;
    if (confirm && !single) {
      confirm.disabled = false;
      confirm.classList.add('confirm-ready', 'confirm-attention');
      confirm.focus({preventScroll: true});
      const bounds = confirm.getBoundingClientRect();
      if (bounds.top < 0 || bounds.bottom > window.innerHeight) {
        confirm.scrollIntoView({block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
      }
    }
    form.elements.request_key.value = crypto.randomUUID();
    check.hidden = true;
    uncertain = false;
    section.dataset.ready = '1';
    section.dispatchEvent(new CustomEvent('card-setup-saved', {bubbles: true}));
    if (single) {
      processing(false);
      button.disabled = false;
      finish();
    }
  };
  const recover = async () => {
    if (!statusUrl) return false;
    check.hidden = single && !check.closest('[role="alert"]');
    const response = await fetch(statusUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error();
    const data = await response.json();
    if (response.ok && data.state === 'saved') { showSaved(data); return true; }
    if (response.status === 404) { uncertain = false; button.disabled = false; check.hidden = true; return false; }
    uncertain = true;
    invalidate();
    button.disabled = true;
    report(data.error || 'Card setup still needs review. Please call/text 848-238-5147.');
    return false;
  };
  check.addEventListener('click', event => {
    event.preventDefault();
    // Saved-card selection has no new token exchange to query. Reload its durable session choice.
    if (!statusUrl) { window.location.reload(); return; }
    recover().catch(() => {
      report(single ? "We couldn't confirm your card selection for this booking," : 'Card setup could not yet be confirmed. Please check again or call/text 848-238-5147.');
    });
  });
  let hosted;
  try {
    const key = JSON.parse(document.querySelector('#card-tokenization-key').textContent);
    // Keep Banquest's own responsive field layout. Container-only flex overrides
    // detached the default input sizing and expiry/CVV alignment in PR #34.
    hosted = new window.HostedTokenization(key, {target: '#provider-card-frame', showFieldErrors: true, styles: {container:'margin:0;padding:0;min-height:0',cardContainer:'margin:0 8px 0 0',card:'width:100%;box-sizing:border-box',expiryContainer:'margin:0 8px 0 0',cvv2Container:'margin:0',fieldErrors:'color:#9b3650;font-size:12px;margin:4px 0 0'}});
  } catch {
    report('Secure card entry is unavailable. Please reload this page or call/text 848-238-5147.');
  }
  const sync = () => { const isNew = form.elements.method.value === 'new'; section.querySelector('[data-new-card]').hidden = !isNew; for (const choice of form.querySelectorAll('[name=retain]')) choice.disabled = !isNew; };
  form.addEventListener('change', () => {
    sync();
    // A potentially accepted provider request must be checked, never exchanged again.
    if (uncertain) return;
    invalidate();
    button.disabled = false;
    statusUrl = '';
    check.hidden = true;
    report(publicStatus?.dataset.idleMessage || 'Save your selected card and policies before confirming your booking.');
  });
  sync();
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (uncertain || !form.reportValidity()) return;
    invalidate();
    button.disabled = true;
    processing(true, 'Processing');
    report(single ? (replacement ? 'Saving your card… The booking card has not been changed yet.' : 'Saving your card… Your booking is not confirmed yet.') : 'Saving secure card setup…');
    try {
      const payload = {
        wizard_key: form.elements.wizard_key.value,
        wizard_stage: form.elements.wizard_stage.value,
        policy_version: form.elements.policy_version.value,
        agree_payment: form.elements.agree_payment.type === 'hidden' ? form.elements.agree_payment.value === '1' : form.elements.agree_payment.checked,
        agree_cancellation: form.elements.agree_cancellation.type === 'hidden' ? form.elements.agree_cancellation.value === '1' : form.elements.agree_cancellation.checked
      };
      if (form.elements.method.value === 'new') {
        if (!hosted) { report('Secure card entry is unavailable. Reload this page before entering your card.'); button.disabled = false; return; }
        const surcharge = await hosted.getSurcharge();
        if (surcharge.surcharge && Number(surcharge.surcharge.value) !== 0) {
          report('The payment provider has an additional surcharge configured. Please contact MonkeyDo before continuing.');
          button.disabled = false; return;
        }
        const result = await hosted.getNonceToken();
        if (!result || typeof result.nonce !== 'string' || !result.nonce) throw new Error('card entry');
        Object.assign(payload, {
          request_key: form.elements.request_key.value,
          nonce: result.nonce.startsWith('nonce-') ? result.nonce : `nonce-${result.nonce}`,
          expiry_month: result.expiryMonth,
          expiry_year: result.expiryYear,
          retain: form.elements.retain.type === 'checkbox' ? form.elements.retain.checked : form.elements.retain.value === 'yes',
          ...(form.elements.retain.type !== 'checkbox' ? {retention_choice: form.elements.retain.value} : {})
        });
        statusUrl = `${section.dataset.statusPrefix}${form.elements.request_key.value}/`;
      } else payload.method = form.elements.method.value;
      uncertain = true;
      const response = await fetch(section.dataset.endpoint, {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': form.elements.csrfmiddlewaretoken.value},
        body: JSON.stringify(payload)
      });
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error();
      const data = await response.json();
      if (response.ok && data.state === 'saved') showSaved(data);
      else {
        report(data.error || 'Card setup needs assistance. Please call/text 848-238-5147.');
        if (response.status === 202) { check.hidden = !statusUrl; button.disabled = true; }
        else { uncertain = false; button.disabled = false; }
      }
    } catch {
      if (!uncertain) {
        report('Please check the card number, expiration date and security code in the secure fields. Complete any missing information, or enter another card, then try again.');
        button.disabled = false;
      } else {
        report(single ? "We couldn't confirm your card selection for this booking," : 'We could not yet confirm whether your card was saved. Use Check card setup before trying another card, or call/text 848-238-5147.');
        check.hidden = false;
        button.disabled = true;
        try { await recover(); } catch { /* Never repeat an uncertain exchange. */ }
      }
    }
  });
  if (single) {
    confirmationForm.addEventListener('submit', event => {
      if (finishing) return;
      event.preventDefault();
      if (confirmRequested || uncertain) return;
      if (!confirmationForm.reportValidity()) return;
      if (section.dataset.ready !== '1' && !form.reportValidity()) return;
      confirmRequested = true;
      if (section.dataset.ready === '1') finish();
      else form.requestSubmit();
    });
  }
  if (section.dataset.ready === '1') {
    form.elements.request_key.value = crypto.randomUUID();
    if (confirm) { confirm.disabled = false; confirm.classList.add('confirm-ready'); }
    button.disabled = !single;
  } else if (statusUrl) {
    button.disabled = true;
    uncertain = true;
    recover().catch(() => { check.hidden = false; report(single ? "We couldn't confirm your card selection for this booking," : 'Please check card setup before continuing.'); });
  }
}
