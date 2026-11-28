/* Hosted fields produce a nonce; only the separately confirmed form requests payment. */
(() => {
  const form = document.querySelector('[data-recovery-card-form]');
  const section = form?.querySelector('[data-recovery-card-section]');
  if (!section) return;
  const field = name => form.elements.namedItem(name);
  const button = form.querySelector('button[value=paid_visit_card_recover]');
  const frame = section.querySelector('[data-recovery-new-card]');
  const status = section.querySelector('[data-recovery-card-status]');
  const check = section.querySelector('[data-recovery-card-check]');
  const choice = field('card_choice');
  let saving = false, uncertain = false, hosted;
  const setupKey = section.dataset.setupKey || crypto.randomUUID();
  let statusUrl = section.dataset.statusUrl || '';
  function report(message) {status.textContent = message; status.hidden = !message;}
  function display() {
    const isNew = choice.value === 'new';
    frame.hidden = !isNew;
    for (const input of frame.querySelectorAll('input')) {input.disabled = !isNew || saving || uncertain; input.required = isNew;}
    choice.disabled = saving || uncertain;
    button.disabled = saving || uncertain || !field('confirmed').checked || !choice.value;
    button.hidden = uncertain;
    field('confirmed').closest('label').hidden = uncertain;
    button.textContent = `${isNew ? 'Save and request card payment' : 'Request card payment'} · $${form.dataset.amount}`;
  }
  function apply(data) {
    saving = false;
    if (!data.recovery_choice) {
      uncertain = true; check.hidden = false;
      report(data.error || 'The card is saved. Review the existing membership payment before another request.');
      display(); return false;
    }
    let option = Array.from(choice.options).find(item => item.value === data.recovery_choice);
    if (!option) {option = new Option(`${data.brand} ending in ${data.last_four}`, data.recovery_choice); choice.add(option);}
    choice.value = option.value; uncertain = false; check.hidden = true;
    if (data.authorization_expired) field('confirmed').checked = false;
    report(data.authorization_expired ? 'Card saved. Confirm its selection again before requesting payment.' : 'Card saved. No new payment has been requested yet.');
    display(); return !data.authorization_expired;
  }
  async function recover() {
    if (!statusUrl) return;
    const response = await fetch(statusUrl, {cache:'no-store', headers:{'Accept':'application/json'}});
    const data = await response.json();
    if (response.ok && data.state === 'saved') apply(data);
    else {uncertain = true; check.hidden = false; report(data.error || 'Check the existing card setup before another attempt.'); display();}
  }
  try {
    hosted = new window.HostedTokenization(JSON.parse(document.querySelector('#recovery-card-tokenization-key').textContent), {
      target:'#recovery-provider-card-frame', showFieldErrors:true,
      styles:{container:'margin:0;padding:0;min-height:0',cardContainer:'margin:0 8px 0 0',card:'width:100%;box-sizing:border-box',expiryContainer:'margin:0 8px 0 0',cvv2Container:'margin:0',fieldErrors:'color:#9b3650;font-size:12px;margin:4px 0 0'}
    });
  } catch {report('Secure new-card entry is unavailable. Select an already saved card or call/text 848-238-5147.');}
  form.addEventListener('change', display);
  check.addEventListener('click', () => recover().catch(() => {report('The existing setup could not yet be checked. No new exchange or payment was sent.');}));
  form.addEventListener('submit', async event => {
    if (choice.value !== 'new' && !saving && !uncertain) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (saving || uncertain || !field('confirmed').checked || !form.reportValidity()) return;
    // Read the explicit retention selection before disabling the hosted controls.
    const retain = field('member_retain').value;
    saving = true; display();
    try {
      if (!hosted) throw new Error('Secure new-card entry is unavailable.');
      const surcharge = await hosted.getSurcharge();
      if (surcharge.surcharge && Number(surcharge.surcharge.value) !== 0) throw new Error('The provider has an additional surcharge configured. Contact MonkeyDo before continuing.');
      const token = await hosted.getNonceToken();
      if (!token?.nonce) throw new Error('Complete the secure card number, expiration and security code.');
      const payload = {confirmed:field('confirmed').checked, storage_key:field('storage_key').value, setup_key:setupKey,
        nonce:token.nonce.startsWith('nonce-') ? token.nonce : `nonce-${token.nonce}`,
        expiry_month:token.expiryMonth, expiry_year:token.expiryYear, retention_choice:retain};
      statusUrl = `${section.dataset.statusPrefix}${setupKey}/`;
      uncertain = true;
      const response = await fetch(section.dataset.endpoint, {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':field('csrfmiddlewaretoken').value},body:JSON.stringify(payload)});
      const data = await response.json();
      if (response.ok && data.state === 'saved') {
        if (apply(data)) window.setTimeout(() => form.requestSubmit(button), 0);
      } else if (response.status === 202) {check.hidden = false; report(data.error);}
      else {uncertain = false; report(data.error || 'Review the card details before continuing.');}
    } catch (failure) {
      report(uncertain ? 'We could not yet confirm whether the card was saved. Check card setup before another attempt. No new payment was requested.' : failure.message);
      if (uncertain) check.hidden = false;
    } finally {saving = false; display();}
  }, true);
  if (statusUrl) {uncertain = true; check.hidden = false; recover().catch(() => report('Check the existing card setup before another attempt.'));}
  display();
})();
