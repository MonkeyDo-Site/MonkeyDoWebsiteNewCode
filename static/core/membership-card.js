/* Banquest owns card-number/CVV fields. This form only exchanges its nonce. */
(() => {
  const form = document.querySelector('[data-membership-purchase], [data-membership-card-update]');
  const section = form?.querySelector('[data-membership-card-entry]');
  if (!section) return;
  const field = name => form.elements.namedItem(name);
  const replacement = form.hasAttribute('data-membership-card-update');
  const button = form.querySelector('[data-membership-confirm]');
  const status = section.querySelector('[data-member-card-status]');
  const check = section.querySelector('[data-member-card-check]');
  const frame = section.querySelector('[data-member-new-card]');
  let hosted, saving = false, uncertain = false, savedMethod = '', statusUrl = section.dataset.statusUrl;
  let setupKey = crypto.randomUUID();
  let authorizationExpired = false, previousAuthorization = '';
  let authorizationDeadline = Infinity;
  const address = new URL(location.href);
  address.searchParams.set(replacement ? 'card_key' : 'purchase_key', field('request_key').value);
  history.replaceState(null, '', address);
  function option() {
    if (!Array.from(field('method').options).some(item => item.value === 'new')) field('method').add(new Option('Enter a new card', 'new'));
  }
  function display() {
    option();
    const isNew = field('method').value === 'new' && !field('comped')?.checked && (replacement || field('billing').value === 'monthly' || field('expected_method').value === 'card');
    frame.hidden = !isNew;
    for (const choice of section.querySelectorAll('[name=member_retain]')) {choice.disabled = !isNew; choice.required = isNew && choice.type !== 'checkbox';}
    section.dataset.blocked = uncertain || saving ? '1' : '0';
    if (replacement) button.disabled = uncertain || saving || !field('accepted').checked;
    form.dispatchEvent(new CustomEvent('membership-card-state'));
  }
  function report(message) {status.textContent = message; status.hidden = false;}
  function apply(data) {
    if (!Array.from(field('method').options).some(item => item.value === data.method_id)) field('method').add(new Option(`${data.brand} ending in ${data.last_four}`, data.method_id));
    field('method').value = data.method_id;
    savedMethod = data.method_id;
    authorizationExpired = Boolean(data.authorization_expired);
    authorizationDeadline = data.authorization_seconds_remaining === undefined ? Infinity : Date.now()+Number(data.authorization_seconds_remaining)*1000;
    previousAuthorization = data.authorization_id;
    field('card_authorization').value = data.offer_fingerprint === field('reviewed').value ? data.authorization_id : '';
    uncertain = false; check.hidden = true;
    saving = false;
    if (data.purchase_recorded) {uncertain = true; report('This membership purchase is already recorded. Open its existing record before another payment.');}
    else if (authorizationExpired && replacement) {uncertain = true; field('accepted').checked = false; report('This card update review expired. Return to the membership and start a fresh card update.');}
    else if (authorizationExpired) {field('accepted').checked = false; report('Card saved. Its review expired. Review the current terms and confirm to authorize this saved card again.');}
    else report(replacement ? 'The card is saved. No payment has been requested.' : 'The membership card is saved. No membership payment has been requested yet.');
    display();
  }
  async function recover() {
    if (!statusUrl) return;
    const response = await fetch(statusUrl, {cache: 'no-store', headers: {'Accept': 'application/json'}});
    const data = await response.json();
    if (response.ok && data.state === 'saved') {
      apply(data);
      form.dispatchEvent(new CustomEvent('membership-card-ready'));
    } else {uncertain = true; check.hidden = false; report(data.error || 'This card setup still needs review.'); display();}
  }
  try {
    hosted = new window.HostedTokenization(JSON.parse(document.querySelector('#membership-card-tokenization-key').textContent), {
      target: '#membership-provider-card-frame', showFieldErrors: true,
      styles: {container:'margin:0;padding:0;min-height:0',cardContainer:'margin:0 8px 0 0',card:'width:100%;box-sizing:border-box',expiryContainer:'margin:0 8px 0 0',cvv2Container:'margin:0',fieldErrors:'color:#9b3650;font-size:12px;margin:4px 0 0'}
    });
  } catch {report('Secure card entry is unavailable. Reload or call/text 848-238-5147 for assistance.');}
  new MutationObserver(display).observe(field('method'), {childList: true});
  form.addEventListener('change', event => {
    if (event.target.name === 'method' || !['member_retain', 'accepted', 'verified_received', 'send_confirmation'].includes(event.target.name)) field('card_authorization').value = '';
    display();
  });
  check.addEventListener('click', () => recover().catch(() => {report('The card setup outcome could not yet be checked. No new exchange or payment was sent.');}));
  form.addEventListener('submit', async event => {
    if(field('method').value===savedMethod&&Date.now()>=authorizationDeadline&&!authorizationExpired){
      event.preventDefault();event.stopImmediatePropagation();authorizationExpired=true;field('accepted').checked=false;
      if(replacement){uncertain=true;report('This card update review expired. Return to the membership and start a fresh card update.');}
      else report('This card review expired. Review the current terms and confirm to authorize this saved card again.');
      display();return;
    }
    const requiresAuthority = section.dataset.requireAuthorization === '1' || field('method').value === savedMethod;
    if (field('method').value !== 'new' && (!requiresAuthority || (field('card_authorization').value && !authorizationExpired))) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (saving || uncertain || !field('accepted').checked || !field('reviewed').value || !form.reportValidity()) return;
    saving = true; display();
    try {
      const purchase = Object.fromEntries(['operation','prior_id','customer','kind','places','months','billing','starts_on','expected_method','credit_amount','request_key','reviewed'].map(name => [name, field(name)?.value || '']));
      purchase.minimum_override = !!field('minimum_override')?.checked;
      purchase.comped = !!field('comped')?.checked;
      purchase.accepted = field('accepted').checked;
      const payload = replacement ? {update: Object.fromEntries(['request_key', 'revision', 'reviewed'].map(name => [name, field(name).value]))} : {purchase};
      if (replacement) payload.update.accepted = field('accepted').checked;
      if (field('method').value === 'new') {
        if (!hosted) throw new Error('Secure card entry is unavailable.');
        const surcharge = await hosted.getSurcharge();
        if (surcharge.surcharge && Number(surcharge.surcharge.value) !== 0) throw new Error('The provider has an additional surcharge configured. Contact MonkeyDo before continuing.');
        const token = await hosted.getNonceToken();
        if (!token || !token.nonce) throw new Error('Complete the secure card number, expiration and security code.');
        const retain = field('member_retain');
        Object.assign(payload, {setup_key: setupKey, nonce: token.nonce.startsWith('nonce-') ? token.nonce : `nonce-${token.nonce}`, expiry_month: token.expiryMonth, expiry_year: token.expiryYear, retention_choice: retain.type === 'checkbox' ? (retain.checked ? 'yes' : 'no') : retain.value});
        statusUrl = `${section.dataset.statusPrefix}${setupKey}/`;
      } else {payload.method = field('method').value; if (authorizationExpired) payload.previous_authorization = previousAuthorization;}
      uncertain = true;
      const response = await fetch(section.dataset.endpoint, {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':field('csrfmiddlewaretoken').value},body:JSON.stringify(payload)});
      const data = await response.json();
      if (response.ok && data.state === 'saved') {
        apply(data);
        if (!data.purchase_recorded) window.setTimeout(() => form.requestSubmit(button), 0);
      } else if (response.status === 202) {check.hidden = false; report(data.error);}
      else {uncertain = false; report(data.error || 'Review the membership and card details before confirming.');}
    } catch (failure) {
      report(uncertain ? 'We could not yet confirm whether the card was saved. Check card setup before another attempt. No membership payment has been requested.' : failure.message || 'Complete the secure card fields before confirming.');
      if (uncertain) check.hidden = false;
    } finally {
      saving = false;
      display();
    }
  }, true);
  display();
  if (statusUrl) {uncertain = true; display(); recover().catch(() => {check.hidden = false; report('Check the existing membership card setup before another attempt.');});}
})();
